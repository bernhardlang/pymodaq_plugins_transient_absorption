import numpy as np
from enum import Enum
from pymodaq_utils.utils import ThreadCommand
from pymodaq_data.data import DataToExport, Axis
from pymodaq_gui.parameter import Parameter
from pymodaq.control_modules.viewer_utility_classes import DAQ_Viewer_base, \
    comon_parameters, main
from pymodaq.utils.data import DataFromPlugins
from pymodaq_plugins_transient_absorption.hardware.controller \
    import MockTAController


class DAQ_1DViewer_MockTACamera(DAQ_Viewer_base):
    """ Instrument plugin class for a Lscpcie 1D viewer.
    
    """
    # first pixel, used pixels, first dark pixel, dark pixels
    params = comon_parameters+[
        { 'title': 'Number of pixels', 'name': 'n_pixels', 'type': 'int',
          'value': 574, },
        { 'title': 'Number of acquisitions per block', 'name': 'acq_per_block',
          'type': 'int', 'min': 1, 'max': 250, 'value': 250 },
        { 'title': 'Clear reads', 'name': 'clear_reads',
          'type': 'int', 'min': 0, 'max': 250, 'value': 4 },
        { 'title': 'Number of blocks', 'name': 'n_blocks',
          'type': 'int', 'min': 1, 'max': 100, 'value': 1 },
        { 'title': 'Trigger mode', 'name': 'trigger_mode', 'type': 'list',
          'limits': ["Free running", "S1", "S2", "S1&S2"], 'value': 'S1' },
        { 'title': 'Average', 'name': 'average', 'type': 'bool',
          'value': True },
        { 'title': 'Displayed scan', 'name': 'displayed_scan', 'type': 'int',
          'min': -1, 'value': 0 },
        ]

    live_mode_available = True

    def ini_attributes(self):
        self.controller: MockTAContrller
        self.x_axis = None
        self.live = False
        self.acquisition_counter = 0

    def commit_settings(self, param: Parameter):
        if param('name') == 'n_pixels':
            self.n_pix = param.value()

    def make_x_axis(self):
        self.n_pix = self.settings['n_pixels']
        data_x_axis = np.linspace(0, self.n_pix - 1, self.n_pix)
        self.x_axis = Axis(data=data_x_axis, label='pixels', units='', index=0)

    def ini_detector(self, controller=None):
        """Detector communication initialization

        Parameters
        ----------
        controller: (object)
            custom object of a PyMoDAQ plugin (Slave case). None if only
            one actuator/detector by controller (Master case)

        Returns
        -------
        info: str
        initialized: bool
            False if initialization failed otherwise True
        """
        self.controller = MockTAController() if self.is_master else controller

        self.make_x_axis()
        data = [DataFromPlugins(name='camera %d' % i,
                                data=[np.zeros(self.n_pix) for _ in range(2)],
                                dim='Data1D', labels=['camera %d' % i],
                                axes=[self.x_axis])
                for i in range(2)]
        self.dte_signal_temp.emit(DataToExport(name='mock_lsc', data=data))

        return "Mock Line Scan Camera plugin initialised", True

    def close(self):
        pass

    def grab_data(self, Naverage=1, **kwargs):
        """Start a grab from the detector

        Parameters
        ----------
        Naverage: int
            Number of hardware averaging (if hardware averaging is possible,
            self.hardware_averaging should be set to
            True in class preamble and you should code this implementation)
        kwargs: dict
            others optionals arguments
        """
        if 'live' in kwargs:
            if kwargs['live']:
                self.live = True
                self.acquisition_counter = 0
                if self.settings['average']:
                    callback = self.average_callback
                else:
                    callback = self.single_callback
                    self.display_scan = self.settings['displayed_scan']
                self.controller.start_continuous_grabbing(callback)
            else:
                self.live = False
                self.controller.stop_continuous_grabbing()
            return

        self.controller.grab(self.callback)

    def single_callback(self, raw_data):
        data_from = self.display_scan * self.n_pix + self.first_used_pix
        data_to = self.display_scan * self.n_pix + self.last_used_pix
        data = [DataFromPlugins(name='camera %d' % i,
                                data=raw_data[data_from:data_to], dim='Data1D',
                                labels=['camera %d' % i], axes=[self.x_axis])
                for i in range(2)]
        self.dte_signal.emit(DataToExport(name='eslscpcie', data=data))

    def average_callback(self, raw_data):
        sum_data = [np.zeros(self.n_pix) for _ in range(2)]
        squares_data = [np.zeros(self.n_pix) for _ in range(2)]
        sum_dark = [0, 0]
        squares_dark = [0, 0]
        valid_scans = \
            self.settings['acq_per_block'] - self.settings['clear_reads']
        src_pos = self.settings['clear_reads'] * self.n_pix * 2
        for _ in range(valid_scans):
            for i in range(2):
                raw = \
                    raw_data[src_pos:src_pos + self.n_pix].astype(np.float64)
                sum_data[i] += raw
                squares_data[i] += raw**2
                src_pos += self.n_pix

        data = [DataFromPlugins(name='camera %d' % i,
                                data=sum_data[i] / valid_scans, dim='Data1D',
                                labels=['camera %d' % i], axes=[self.x_axis])
                for i in range(2)]
        rms = [DataFromPlugins(name='rms %d' % i,
                               data=np.sqrt((valid_scans * squares_data[i]
                                             - sum_data[i]**2)
                                            / (valid_scans * (valid_scans - 1))),
                               dim='Data1D', labels=['rms %d' % i],
                               axes=[self.x_axis])
                for i in range(2)]
        self.dte_signal.emit(DataToExport(name='mock lsc', data=data + rms))

    def stop(self):
        self.controller.stop_continuous_grabbing()
        return ''


if __name__ == '__main__':
    main(__file__)
