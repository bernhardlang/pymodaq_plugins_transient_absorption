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
        current = None
        if self.data_processing_mode == self.DARK:
            result, mean, rms = self.process_dark(raw_data)
            if result == Averager.SUCCESS:
                self.whitelight_averagers
                = [self.averager_factory.make_averager(cond, dark_averager[1])
                   for cond in self.statistic_conditions]
                    av.dark = self.dark_averager[1].mean
            self.dark_signal = self.dark_averager[0].mean
            self.dark_reference = self.dark_averager[1].mean

        elif self.data_processing_mode == self.WHITELIGHT:
            result, mean, rms = self.process_whitelight(raw_data)
            if result == Averager.SUCCESS:
                self.whitelight = [av.mean for av in self.whitelight_averagers[:-2]]
                self.rms_whitelight = [av.rms for av in self.whitelight_averagers[:-2]]

        elif self.data_processing_mode == self.TA:
            result, mean, rms, current = self.process_ta(raw_data)
        else:
            return

        if result != Averager.CONTINUE_
            self.data_processing_mode = self.IDLE

        if result == Averager.SUCESS:
            self.dte_signal.emit(DataToExport(name='mock-ta', data=[mean, rms)))
            self.acquisition_done.emit()
            return

        self.dte_signal_temp.emit(DataToExport(name='mock-ta', data=[data, rms]))
        if result == Averager.FAIL:
            self.acquisition_fail.emit()

    def process_dark(self, raw_data):
        result = Averager.SUCESSS
        for av in self.dark_averagers:
            result = max(result, av.take_data(raw_data))

        mean = [DataFromPlugins(name='dark camera %d' % i, data=[av.mean],
                                dim='Data1D', labels=['dark camera %d' % i],
                                axes=[self.x_axis])
                for i,av in self.dark_averagers]
        rms = [DataFromPlugins(name='rms dark camera %d' % i, data=[av.rms],
                               dim='Data1D', labels=['rms dark camera %d' % i],
                               axes=[self.x_axis])
               for i,av in self.dark_averagers]

        return result, mean, rms
        
    def process_whitelight(self, raw_data):
        result = Averager.SUCESSS
        for av in self.whitelight_averagers:
            result = max(result, av.take_data(raw_data))

        mean = [DataFromPlugins(name='dark camera %d' % i, data=[av.mean],
                                dim='Data1D', labels=['dark camera %d' % i],
                                axes=[self.x_axis])
                for i,av in self.whitelight_averagers[-2:]
        rms = [DataFromPlugins(name='rms dark camera %d' % i, data=[av.rms],
                               dim='Data1D', labels=['rms dark camera %d' % i],
                               axes=[self.x_axis])
               for i,av in self.whitelight_averagers[-2:]

        return result, mean, rms

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
