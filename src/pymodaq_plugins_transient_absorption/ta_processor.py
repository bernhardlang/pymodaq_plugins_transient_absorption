import numpy as np
from dataclasses import dataclass
from PyQt5.QtCore import QObject, pyqtSignal
from pymodaq_plugins_transient_absorption.averager import Averager, \
    AveragerFactory


@dataclass
class StatisticsCondition:

    pixel_from: int
    pixel_to: int
    limit_diff_rms: float = None
    limit_diff_mean: float = None
    max_attempts: int = 0


@dataclass
class TACondition:

    limit_diff_mean_dark: float
    limit_diff_mean_dark: float
    max_dark: int
    limit_diff_rms_white: float
    limit_diff_mean_white: float
    max_white: int


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
        self.dark_condition = \
            StatisticsCondition(0, n_pix, cond.limit_diff_rms_dark,
                                cond.limit_diff_mean_dark,
                                cond.max_dark)
        self.whitelight_conditions = \
            [StatisticsCondition(pix[0], pix[1], cond.limit_diff_rms_dark,
                                 cond.limit_diff_mean_dark, cond.max_dark)
             for pix in statistic_ranges]
        self.whitelight_conditions.append(StatisticsCondition(0, n_pix))

        self.dark_averager = \
            [AveragerFactory.make(self.dark_condition, 2 * n_pix),
             AveragerFactory.make(self.dark_condition, 2 * n_pix, n_pix)]
        self.ta_averager = AveragerFactory.make(StatisticsCondition(0, n_pix), 0)
        self.data_processing_mode = self.DARK

    def process_data(self, raw_data):
        current = None
        if self.data_processing_mode == self.DARK:
            result, dte = self.process_dark(raw_data)
            if result == Averager.SUCCESS:
                self.whitelight_averagers = \
                    [self.averager_factory\
                     .make_averager(cond, 2 * self.n_pix, self.n_pix,
                                    self.dark_averager[1])
                     for cond in self.statistic_conditions]
                av.dark = self.dark_averager[1].mean
            self.dark_signal = self.dark_averager[0].mean
            self.dark_reference = self.dark_averager[1].mean

        elif self.data_processing_mode == self.WHITELIGHT:
            result, dte = self.process_whitelight(raw_data)
            if result == Averager.SUCCESS:
                self.whitelight = \
                    [av.mean for av in self.whitelight_averagers[:-2]]
                self.rms_whitelight = \
                    [av.rms for av in self.whitelight_averagers[:-2]]
                self.ta_whitelight_averager = \
                    self.averager_factory\
                     .make_averager(self.statistic_conditions[-1],
                                    2 * self.n_pix, self.n_pix)
                self.ta_averager = \
                    self.averager_factory\
                     .make_averager(self.ta_cond, 2 * self.n_pix, self.n_pix)

        elif self.data_processing_mode == self.TA:
            result, dte = self.process_ta(raw_data)
        else:
            return None, False

        if result != Averager.CONTINUE:
            self.data_processing_mode = self.IDLE

        if result == Averager.SUCCESS:
            return dte, False

        if result == Averager.FAIL:
            self.acquisition_fail.emit()
        return dte, True

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

        dte = DataToExport(name='dark', data=[mean, rms])
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
                for i,av in self.whitelight_averagers[-2:]]
        rms = [DataFromPlugins(name='rms dark camera %d' % i, data=[av.rms],
                               dim='Data1D', labels=['rms dark camera %d' % i],
                               axes=[self.x_axis])
               for i,av in self.whitelight_averagers[-2:]]

        dte = DataToExport(name='whitelight', data=[mean, rms])
        return result, dte

    def check_whitelight(self, data):
        pass

    def process_ta(self, raw_data):
        n_pic = self.n_pix
        ta = None
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
