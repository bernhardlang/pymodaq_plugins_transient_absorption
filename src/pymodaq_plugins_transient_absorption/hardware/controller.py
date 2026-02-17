import numpy as np
from dataclasses import dataclass


class MockActuator:

    def __init__(self):
        self._target_value = 0
        self._current_value = 0
    
    def move_at(self, value):
        self._target_value = value
        self._current_value = value

    def get_value(self):
        return self._current_value


class MockDelayLine(MockActuator):

    pass


class MockPolarizer(MockActuator):

    pass


class MockShutter(MockActuator):

    pass


@dataclass
class MockTACamera:

    n_pixels: int = 574
    first_pisel: int = 17
    first_dark_dark: int = 541
    adc_bits: int = 16
    photo_electrons_per_lsb: float = 1e6/(2**16)
    signal: float = 30000
    relative_rms_signal: float = 0.05
    reference: float = 35000
    dark_sig: float = 1000
    rms_dark_sig: float = 5
    dark_reference: float = 1300
    rms_dark_reference: float = 4.5
    absorption: float = 0.01
    bleach: float = 0.03
    excited_state_absorption: float = 0.05
    excited_state_angle : float = np.pi / 2
    excitation_scatter: float = 500
    relative_rms_scatter: float = 0.1
    life_time: float = 1e-10
    decorrelation_time: float = 1e-11
    parallel_polarizer: float = 10 / 180 * np.pi
    parallel_waveplate: float = 15 / 180 * np.pi
    laser_polarization: float = 2 / 180 * np.pi

    def __post_init__(self):
        self.calculate_base_data()

    def calculate_base_data(self):
        n_pix = self.n_pixels
        pixels = np.linspace(0, n_pix - 1, n_pix)
        self.spectrum = np.exp(-((pixels - n_pix / 2) / (n_pix / 3))**4)
        self.gsb = self.bleach * np.exp(-(n_pix / 4 / (n_pix / 8))**2)
        self.esa = \
            self.excited_state_absorption \
            * np.exp(-((pixels - n_pix / 4) / (n_pix / 8))**2)
        self.scatter = \
            self.excitation_scatter * np.exp(-(n_pix / 8 / (n_pix / 8))**2)

    def calculate_scan(delay: float, polarizer_angle: float, excitation: bool,
                       probe: bool):

        signal_photo_electrons = \
            np.random.normal(loc=self.dark_signal, scale=self.rms_dark_signal,
                             size=self.n_pixels) \
            * photo_electrons_per_lsb
        reference_photo_electrons = \
            np.random.normal(loc=self.dark_sig, scale=self.rms_dark_sig,
                             size=self.n_pixels) \
            * photo_electrons_per_lsb

        if excitation:
            signal_photo_electrons += \
                self.excitation_scatter * \
                np.random.normal(loc=1, scale=self.relative_rms_scatter,
                                 size=self.n_pixels) \
                * photo_electrons_per_lsb

        if probe:
            fluct = np.random.normal(loc=1, scale=self.relative_rms_signal)
            signal = self.spectrum * self.signal * fluct
            reference = self.spectrum * self.reference * fluct

            if excitation:
                time_factor = np.exp(-delay / self.life_time)
                anisotropy_factor = np.exp(delay / self.decorrelation_time)

                gsb_amplitude = -self.bleach * time_factor
                bleach = gsb_amplitude * (1 + 0.8 * anisotropy_factor) \
                    * np.cos(polarizer_angle)**2 \
                    + gsb_amplitude * (1 - 0.4 * anisotropy_factor) \
                    * np.sin(polarizer_angle)**2

                esa_amplitude = -self.excited_state_absorption * time_factor
                esa = esa_amplitude * (1 + 0.8 * anisotropy_factor) \
                    * np.cos(polarizer_angle - self.excited_state_angle)**2 \
                    + esa_amplitude * (1 - 0.4 * anisotropy_factor) \
                    * np.sin(polarizer_angle - self.excited_state_angle)**2

                signal *= pow(10, -(bleach + esa))

            signal_photo_electrons += \
                np.random.poisson(signal * photo_electrons_per_lsb)
            reference_photo_electrons += \
                np.random.poisson(reference * photo_electrons_per_lsb)

        signal = signal_photo_electrons / photo_electrons_per_lsb
        reference = reference_photo_electrons / photo_electrons_per_lsb
        signal = np.where(signal < 0, 0, signal)
        reference = np.where(reference < 0, 0, reference)
        max_val = 2**self.adc_bits - 1
        signal = np.where(signal > max_val, max_val, signal)
        reference = np.where(reference > max_val, max_val, reference)
        if self.adc_bits <= 16:
            return signal.astype(np.uint16), reference.astype(np.uint16)
        return signal.astype(np.uint32), reference.astype(np.uint32)

    def calculate_block(delay: float, polarizer_angle: float, excitation: bool,
                        probe: bool, scatter: bool):
        n_pix = self.n_pixels
        data_size = self.n_pixels * 2 * self.scans_per_block

        data = np.empty(data_size)
        dest = 0
        while dest < data_size:
            data[dest:dest+n_pix], data[dest+n_pix:dest+2*n_pix] = \
                calculate_scan(delay, polarizer_angle, excitation, probe)
            dest += 2 * n_pix
            data[dest:dest+n_pix], data[dest+n_pix:dest+2*n_pix] = \
                calculate_scan(delay, polarizer_angle, False, probe)
            dest += 2 * n_pix
            if dest >= data_size or not scatter:
                break
            data[dest:dest+n_pix], data[dest+n_pix:dest+2*n_pix] = \
                calculate_scan(delay, polarizer_angle, excitation, False)
            dest += 2 * n_pix
            data[dest:dest+n_pix], data[dest+n_pix:dest+2*n_pix] = \
                calculate_scan(delay, polarizer_angle, False, False)
            dest += 2 * n_pix

        return data


class MockTAController:

    def __init__(self):
        self.camera = MockTACamera()
        self.delay_line = MockDelayLine()
        self.shutters = [MockShutter() for _ in range(2)]
        self.polarizers = [MockPolarizer() for _ in range(2)]
        self.with_scatter = False
        self._thread = None

    def grab_spectrum(self):
        return self.camera.calculate_block(self.delay_line.get_value(),
                                           self.polarizers[0].get_value(),
                                           self.shutters[0].get_value() > 0,
                                           self.shutters[1].get_value() > 0,
                                           self.with_scatter)

    def start_continuous_grabbing(self, callback):
        if self._thread is None:
            self._callback = callback
            self._stop = False
            self._thread = Thread(target=self.grab_loop)
            self._thread.start()

    def stop_continuous_grabbing(self):
        if self._thread is not None:
            self._stop = True
            self._thread.join()
            self._thread = None

    def grab_loop(self):
        while not self._stop:
            data = self.grab_spectrum()
            self.callback(data)
