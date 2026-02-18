import numpy as np
from dataclasses import dataclass
from threading import Thread

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
    dark_signal: float = 1000
    rms_dark_signal: float = 5
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
    scans_per_block: int = 250

    def __post_init__(self):
        self.calculate_base_data()

    def calculate_base_data(self):
        n_pix = self.n_pixels
        pixels = np.linspace(0, n_pix - 1, n_pix)
        self.whitelight = np.exp(-((pixels - n_pix / 2) / (n_pix / 3))**4)
        self.gsb = np.exp(-((pixels - n_pix / 4) / (n_pix / 8))**2)
        self.esa = np.exp(-((pixels - 3 * n_pix / 4) / (n_pix / 8))**2)
        self.scatter = np.exp(-((pixels - n_pix / 4) / (n_pix / 16))**2)

    def calculate_scan(self, delay: float, polarizer_angle: float,
                       excitation: bool, probe: bool):

        # dark
        signal_photo_electrons = \
            np.random.normal(loc=self.dark_signal, scale=self.rms_dark_signal,
                             size=self.n_pixels) \
            * self.photo_electrons_per_lsb
        reference_photo_electrons = \
            np.random.normal(loc=self.dark_reference, scale=self.rms_dark_signal,
                             size=self.n_pixels) \
            * self.photo_electrons_per_lsb

        if excitation:
            # scatter
            signal_photo_electrons += \
                self.excitation_scatter * \
                np.random.normal(loc=1, scale=self.relative_rms_scatter) \
                * self.scatter * self.photo_electrons_per_lsb

        if probe:
            fluct_I0 = np.random.normal(loc=1, scale=self.relative_rms_signal)
            signal = self.whitelight * self.signal * fluct_I0
            reference = self.whitelight * self.reference * fluct_I0

            if excitation:
                time_factor = np.exp(-delay / self.life_time)
                anisotropy_factor = np.exp(delay / self.decorrelation_time)

                gsb_amplitude = -self.bleach * time_factor
                bleach = gsb_amplitude * (1 + 0.8 * anisotropy_factor) \
                    * np.cos(polarizer_angle)**2 \
                    + gsb_amplitude * (1 - 0.4 * anisotropy_factor) \
                    * np.sin(polarizer_angle)**2

                esa_amplitude = self.excited_state_absorption * time_factor
                esa = esa_amplitude * (1 + 0.8 * anisotropy_factor) \
                    * np.cos(polarizer_angle - self.excited_state_angle)**2 \
                    + esa_amplitude * (1 - 0.4 * anisotropy_factor) \
                    * np.sin(polarizer_angle - self.excited_state_angle)**2

                absorption = bleach * self.gsb + esa * self.esa
                signal *= np.power(10, -absorption)

            signal_photo_electrons += \
                np.random.poisson(signal * self.photo_electrons_per_lsb)
            reference_photo_electrons += \
                np.random.poisson(reference * self.photo_electrons_per_lsb)

        signal = signal_photo_electrons / self.photo_electrons_per_lsb
        reference = reference_photo_electrons / self.photo_electrons_per_lsb
        signal = np.where(signal < 0, 0, signal)
        reference = np.where(reference < 0, 0, reference)
        max_val = 2**self.adc_bits - 1
        signal = np.where(signal > max_val, max_val, signal)
        reference = np.where(reference > max_val, max_val, reference)
        if self.adc_bits <= 16:
            return signal.astype(np.uint16), reference.astype(np.uint16)
        return signal.astype(np.uint32), reference.astype(np.uint32)

    def calculate_block(self, delay: float, polarizer_angle: float,
                        excitation: bool, probe: bool, scatter: bool):
        n_pix = self.n_pixels
        data_size = self.n_pixels * 2 * self.scans_per_block

        data = np.empty(data_size, dtype=np.uint16)
        dest = 0
        while dest < data_size:
            data[dest:dest+n_pix], data[dest+n_pix:dest+2*n_pix] = \
                 self.calculate_scan(delay, polarizer_angle, excitation, probe)
            dest += 2 * n_pix
            data[dest:dest+n_pix], data[dest+n_pix:dest+2*n_pix] = \
                self.calculate_scan(delay, polarizer_angle, False, probe)
            dest += 2 * n_pix
            if not scatter:
                continue
            if dest >= data_size:
                break
            data[dest:dest+n_pix], data[dest+n_pix:dest+2*n_pix] = \
                self.calculate_scan(delay, polarizer_angle, excitation, False)
            dest += 2 * n_pix
            data[dest:dest+n_pix], data[dest+n_pix:dest+2*n_pix] = \
                self.calculate_scan(delay, polarizer_angle, False, False)
            dest += 2 * n_pix

        return data


class MockTAController:

    polarizer_names = ['Polarizer', 'Lambda/2']
    shutter_names = ['Excitation', 'Probe']

    def __init__(self):
        self.camera = MockTACamera()
        self.delay_line = MockDelayLine()
        self.shutters = { name: MockShutter() for name in self.shutter_names }
        self.polarizers = \
            { name: MockPolarizer() for name in self.polarizer_names }
        self.with_scatter = False
        self._thread = None

    def get_polarizer_value(self, axis):
        return self.polarizers[axis].get_value()

    def set_polarizer_value(self, axis, value):
        self.polarizers[axis].set_value(value)

    def get_delay_value(self):
        return self.delay_line.get_value()

    def set_delay_value(selfvalue):
        self.delay_line.set_value(value)

    def get_shutter_value(self, shutter):
        return self.shutters[axis].get_value()

    def set_shutter_value(self, shutter, value):
        self.shutters[axis].set_value(value)

    def grab_spectrum(self):
        return self.camera\
            .calculate_block(self.delay_line.get_value(),
                             self.polarizers['Polarizer'].get_value(),
                             self.shutters['Excitation'].get_value() > 0,
                             self.shutters['Probe'].get_value() > 0,
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
            self._callback(data)


if __name__ == '__main__':
    import matplotlib.pyplot as plt
    camera = MockTACamera()

    plt.plot(camera.whitelight)
    plt.plot(camera.gsb)
    plt.plot(camera.esa)
    plt.plot(camera.scatter)
    plt.legend(['whitelight', 'GSB', 'ESA', 'scatter'])
    plt.show()
    
    sig_p, ref_p = camera.calculate_scan(delay=0, polarizer_angle=0,
                                         excitation=True, probe=True)
    plt.plot(sig_p)
    plt.plot(ref_p)
    plt.title('Pumped')
    plt.show()

    sig_0, ref_0 = camera.calculate_scan(delay=0, polarizer_angle=0,
                                         excitation=False, probe=True)
    plt.plot(sig_0)
    plt.plot(ref_0)
    plt.title('Unpumped')
    plt.show()

    sig_s, ref_s = camera.calculate_scan(delay=0, polarizer_angle=0,
                                         excitation=True, probe=False)
    plt.plot(sig_s)
    plt.plot(ref_s)
    plt.title('Scatter')
    plt.show()

    sig_d, ref_d = camera.calculate_scan(delay=0, polarizer_angle=0,
                                         excitation=False, probe=False)
    plt.plot(sig_d)
    plt.plot(ref_d)
    plt.title('Dark')
    plt.show()

    sig_p = sig_p - sig_d.astype(float)
    sig_0 = sig_0 - sig_d.astype(float)
    ref_p = ref_p - ref_d.astype(float)
    ref_0 = ref_0 - ref_d.astype(float)
    plt.plot(sig_p)
    plt.plot(sig_0)
    plt.show()
    
    ta = -np.log10((sig_p * ref_0) / (sig_0 * ref_p))
    plt.plot(ta)
    plt.title('TA')
    plt.show()
