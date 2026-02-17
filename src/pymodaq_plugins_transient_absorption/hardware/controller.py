import numpy as np
from dataclasses import dataclass


class MockDelayLine:

    pass


class MockPolarizer:

    pass


class MockShutter:

    pass


@dataclass
class MockTAController:

    n_pixels: int = 574
    first_pisel: int = 17
    first_dark_dark: int = 541
    photo_electrons_per_lsb: float = 1e6/(2**16)
    signal: float = 30000
    relative_rms_signal: float = 0.05
    reference: float = 35000
    relative_rms_reference: float = 0,05
    dark_sig: float = 1000
    rms_dark_sig: float = 5
    dark_reference: float = 1300
    rms_dark_reference: float = 0 4.5
    absorption: float = 0.01
    bleach: float = 0.03
    excited_state_absorption: float = 0.05
    excitation_scatter: float = 500
    relative_rms_scatter: float = 0.1
    life_time: float = 1e-10
    anisotropy: float = 0.4
    decorrelation_time: float = 1e-11
    parallel_polarizer: float = 10
    parallel_waveplate: float = 15
    laser_polarization: float = 2

    def __post_init__(self):
        self.calculate_base_data()
        self.delay_line = MockDelayLine()
        self.shutters = [MockShutter() for _ in range(2)]
        self.polarizer = [MockPolarizer() for _ in range(2)]

    def calculate_base_data(self):
        pixels = np.linspace(0, self.n_pixels - 1, self.n_pixels)
        self.spectrum = np.exp(-((pixels - n_pixels / 2) / (n_pixels / 3))**4)
        self.gsb = self.bleach * np.exp(-(n_pixels / 4 / (n_pixels / 8))**2)
        self.esa = \
            self.excited_state_absorption \
            * np.exp(-((pixels - n_pixels / 4) / (n_pixels / 8))**2)
        self.scatter = \
            self.exitation_scatter * np.exp(-(n_pixels / 8 / (n_pixels / 8))**2)

    def grab_spectrum(self):
        time_factor = np.exp(-self.delay_line.time / self.life_time)
        aniotropy_factor = \
            np.exp(-self.delay_line.time / self.decorrelation_time) *
        polariation_intensity = \
            np.cos(self.laser_polarization / 180 * np.pi)**2 \
            * np.cos((self.poarizer[0].angle - self.parallel_polarizer) / 180 * np.pi)**2 \
            * np.cos((self.poarizer[1].angle - self.parallel_polarizer) / 90 * np.pi)**2

    def start_continuous_grabbing(self):
        pass

    def stop_continuous_grabbing(self):
        pass

    def grab_loop(self):
        pass

