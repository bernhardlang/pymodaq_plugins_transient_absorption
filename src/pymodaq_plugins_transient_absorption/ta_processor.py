import numpy as np
from dataclasses import dataclass
from PyQt5.QtCore import QObject, pyqtSignal
from pymodaq.utils.data import DataFromPlugins, DataToExport, Axis
from pymodaq_plugins_transient_absorption.averager import Averager, \
    AveragerFactory


@dataclass
class StatisticsCondition:

    pixel_from: int
    pixel_to: int
    limit_diff_rms: float = 0
    limit_diff_mean: float = 0
    min_samples: int = 0
    max_attempts: int = 0


@dataclass
class TACondition:

    limit_diff_rms_dark: float
    limit_diff_mean_dark: float
    min_dark: int
    max_dark_attempts: int
    limit_diff_rms_white: float
    limit_diff_mean_white: float
    min_white: int
    max_white_attempts: int


class TAProcessor(QObject):
    """ 
    """

    acquisition_done = pyqtSignal()
    acquisition_failed = pyqtSignal()

    IDLE       = 0
    DARK       = 1
    WHITELIGHT = 2
    TA         = 3

    def set_up(self, n_pix, cond: TACondition, statistic_ranges: []):
        self.n_pix = n_pix
        data_x_axis = np.linspace(0, self.n_pix - 1, self.n_pix)
        self.x_axis = Axis(data=data_x_axis, label='pixels', units='', index=0)
        self.dark_condition = \
            StatisticsCondition(0, n_pix, cond.limit_diff_rms_dark,
                                cond.limit_diff_mean_dark,
                                cond.min_dark, cond.max_dark_attempts)
        self.whitelight_conditions = \
            [StatisticsCondition(pix[0], pix[1], cond.limit_diff_rms_dark,
                                 cond.limit_diff_mean_dark, cond.min_white,
                                 cond.max_white_attempts)
             for pix in statistic_ranges]
        self.whitelight_conditions.append(StatisticsCondition(0, n_pix))

        self.dark_averagers = \
            [AveragerFactory.make(self.dark_condition, 2 * n_pix),
             AveragerFactory.make(self.dark_condition, 2 * n_pix, n_pix)]
        self.whitelight_averagers = []
        self.ta_averager = AveragerFactory.make(StatisticsCondition(0, n_pix), 0)
        self.data_processing_mode = self.DARK

    def reset(self):
        for av in self.dark_averagers + self.whitelight_averagers:
            av.reset()
        self.data_processing_mode = self.DARK
        self.clear_accumulation()

    def clear_accumulation(self):
        self.ta_averager.reset()
        self.ta_whitelight_averager.reset()

    def process_data(self, raw_data):
        current = None
        if self.data_processing_mode == self.DARK:
            result, dte = self.process_dark(raw_data)
            if result == Averager.SUCCESS:
                self.whitelight_averagers = \
                    [AveragerFactory.make(cond, 2 * self.n_pix, self.n_pix)
                     for cond in self.whitelight_conditions]
            self.dark_signal = self.dark_averagers[0].mean
            self.dark_reference = self.dark_averagers[1].mean

        elif self.data_processing_mode == self.WHITELIGHT:
            result, dte = self.process_whitelight(raw_data)
            if result == Averager.SUCCESS:
                self.whitelight = \
                    [av.mean for av in self.whitelight_averagers[:-2]]
                self.rms_whitelight = \
                    [av.rms for av in self.whitelight_averagers[:-2]]
                self.ta_whitelight_averager = \
                    AveragerFactory.make(self.whitelight_conditions[-1],
                                         2 * self.n_pix, self.n_pix)
                self.ta_averager = \
                    AveragerFactory.make(self.ta_cond, 2 * self.n_pix,
                                         self.n_pix)

        elif self.data_processing_mode == self.TA:
            result, dte = self.process_ta(raw_data)

        else: # IDLE, do nothing
            return None, False

        if result != Averager.CONTINUE:
            self.data_processing_mode = self.IDLE

        if result == Averager.SUCCESS:
            self.acquisition_done.emit()
            return dte, True # store

        if result == Averager.FAIL:
            self.acquisition_fail.emit()

        return dte, False # display only

    def process_dark(self, raw_data):
        result = Averager.SUCCESS
        for av in self.dark_averagers:
            result = max(result, av.take_data(raw_data))

        mean = [DataFromPlugins(name='dark camera %d' % i, data=[av.mean],
                                dim='Data1D', labels=['dark camera %d' % i],
                                axes=[self.x_axis])
                for i,av in enumerate(self.dark_averagers)]
        rms = [DataFromPlugins(name='rms dark camera %d' % i, data=[av.rms],
                               dim='Data1D', labels=['rms dark camera %d' % i],
                               axes=[self.x_axis])
               for i,av in enumerate(self.dark_averagers)]

        dte = DataToExport(name='dark', data=mean + rms)
        return result, dte

    def subtrackt_dark(self, raw_data):
        pass

    def process_whitelight(self, raw_data):
        src = 0
        while src < len(raw_data):
            dark_subtracted = \
                self.subtrackt_dark(raw_data[src:src + self.item_size])
            result = Averager.SUCESSS
            for av in self.whitelight_averagers:
                result = max(result, av.take_data(dark_subtracted))
            if result == Averager.SUCESSS:
                break

        mean = [DataFromPlugins(name='dark camera %d' % i, data=[av.mean],
                                dim='Data1D', labels=['dark camera %d' % i],
                                axes=[self.x_axis])
                for i,av in enumerate(self.whitelight_averagers[-2:])]
        rms = [DataFromPlugins(name='rms dark camera %d' % i, data=[av.rms],
                               dim='Data1D', labels=['rms dark camera %d' % i],
                               axes=[self.x_axis])
               for i,av in enumerate(self.whitelight_averagers[-2:])]

        dte = DataToExport(name='whitelight', data=[mean, rms])
        return result, dte

    def check_whitelight(self, data):
        pass

    def process_ta(self, raw_data):
        n_pic = self.n_pix
        ta = None
        src = 0
        while src < len(raw_data):
            data = self.subtrackt_dark(raw_data[src:src + self.item_size])
            self.ta_whitelight_averager.take_data(data)
            if self.check_whitelight(dark_subtracted):
                if self.with_scatter:
                    data[:n_pix] -= data[4*n_pix:5*n_pix]
                counter = data[:n_pix] * data[3*n_pix:4*n_pix]
                denominator = data[n_pix:2*n_pix] * data[2*n_pix:3*n_pix]
                condition = counter > 0 and denominator > 0
                ta = np.where(condition, -np.log10(counter / denominator), 0)
                result = self.ta_averager.take_data(ta)
                if result == Averager.SUCCESS:
                    break

        white = DataFromPlugins(name='whitelight',
                                data=[self.ta_whitleight_averager.mean],
                                dim='Data1D', labels=['whitelight'],
                                axes=[self.x_axis])

        if ta is None:
            data = [white]
        else:
            mean = DataFromPlugins(name='TA', data=[self.ta_averager.mean],
                                   dim='Data1D', labels=['TA'],
                                   axes=[self.x_axis])
            rms = DataFromPlugins(name='rms TA', data=[self.ta_averager.rms],
                                  dim='Data1D', labels=['rms TA'],
                                  axes=[self.x_axis])
            ta = DataFromPlugins(name='current', data=[ta], dim='Data1D',
                                 labels=['current'], axes=[self.x_axis])
            data = [mean, rms, ta, white]

        return result, DataToExport(name='ta', data=data)
