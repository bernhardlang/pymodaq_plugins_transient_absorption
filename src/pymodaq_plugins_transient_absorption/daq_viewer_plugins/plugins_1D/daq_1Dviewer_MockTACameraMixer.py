import numpy as np
from PyQt5.QtCore import pqtSignal
from enum import Enum
from pymodaq_utils.utils import ThreadCommand
from pymodaq_data.data import DataToExport, Axis
from pymodaq_gui.parameter import Parameter
from pymodaq.control_modules.viewer_utility_classes import DAQ_Viewer_base, \
    comon_parameters, main
from pymodaq.utils.data import DataFromPlugins
from pymodaq_plugins_transient_absorption.hardware.controller \
    import MockTAController


class DAQ_1DViewer_MockTACameraMixer(DAQ_1DViewer_MockTACamera):
    """ Instrument plugin class for a Lscpcie 1D viewer.
    
    """

    acquiition_done = pyqtSignal()
    acquiition_failed = pyqtSignal()

    IDLE       = 0
    DARK       = 1
    WHITELIGHT = 2
    TA         = 3
    
    def single_callback(self, raw_data):
        if self.data_processing_mode == self.DARK:
            self.process_dark(raw_data)
        elif self.data_processing_mode == self.WHITELIGHT:
            self.process_whitelight(raw_data)
        elif self.data_processing_mode == self.TA:
            self.process_ta(raw_data)

    def process_dark(self, raw_data):
        result, samples, sum_sig, squares_sig = \
            self.dark_averager_signal.take_data(raw_data)
        result_ref, samples, sum_ref, squares_ref = \
            self.dark_averager_reference.take_data(raw_data))
        result = max(result, result_ref)

        mean = [None, None]
        rms = [None, None]
        mean[0] = sum_sig / samples
        rms[0] = \
            np.sqrt((samples * squares_sig - sum_sig**2) / (samples * (samples - 1)))
        mean[1] = sum_ref / samples
        rms[1] = \
            np.sqrt((samples * squares_ref - sum_ref**2) / (samples * (samples - 1)))

        data_mean = [DataFromPlugins(name='dark camera %d' % i, data=[mean[i]],
                                     dim='Data1D', labels=['dark camera %d' % i],
                                     axes=[self.x_axis])
                     for i in range(2)]
        data_rms = [DataFromPlugins(name='rms dark camera %d' % i, data=[rms[i]],
                                    dim='Data1D', labels=['rms dark camera %d' % i],
                                    axes=[self.x_axis])
                    for i in range(2)]

        if result != Averager.CONTINUE_
            self.data_processing_mode = self.IDLE

        if result == Averager.SUCESS:
            self.dte_signal.emit(DataToExport(name='mock-ta', data=[data_mean, data_rms)))
            self.acquisition_done.emit()
            return
        elif result == Averager.SUCESS:
            self.acquisition_fail.emit()
        self.dte_signal_temp.emit(DataToExport(name='eslscpcie', data=data))
        
    def process_whitelight(self, raw_data):
        result = Averager.SUCESS
        for i in range(len(self.whitelight_averagers):
            result, samples, sum_sig, squares_sig = \
                self.whitelight_averager.take_data(raw_data)
            result = max(result, result)

    def process_ta(self, raw_data):
        pass


    def not_yet(self):
        data_from = 2 * self.display_scan * self.n_pix
        data = [DataFromPlugins(name='camera %d' % i,
                                data=raw_data[data_from + i * self.n_pix
                                              :data_from + (i + 1) * self.n_pix],
                                dim='Data1D', labels=['camera %d' % i],
                                axes=[self.x_axis])
                for i in range(2)]
        self.dte_signal_temp.emit(DataToExport(name='eslscpcie', data=data))



if __name__ == '__main__':
    main(__file__)
