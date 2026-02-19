from enum import Enum
from pymodaq_utils.utils import ThreadCommand
from pymodaq_data.data import DataToExport, Axis
from pymodaq_gui.parameter import Parameter
from pymodaq.control_modules.viewer_utility_classes import DAQ_Viewer_base, \
    comon_parameters, main
from pymodaq.utils.data import DataFromPlugins
from pymodaq_plugins_transient_absorption.hardware.controller \
    import MockTAController
from pymodaq_plugins_transient_absorption.daq_viewer_plugins.plugins_1D \
    .daq_1Dviewer_MockTACamera import DAQ_1DViewer_MockTACamera
from pymodaq_plugins_transient_absorption.ta_processor import TAProcessor, \
    StatisticsCondition, TACondition


class DAQ_1DViewer_MockTACameraMixer(DAQ_1DViewer_MockTACamera):
    """ Instrument plugin class for a Lscpcie 1D viewer.
    
    """

    IDLE       = 0
    DARK       = 1
    WHITELIGHT = 2
    TA         = 3

    params = DAQ_1DViewer_MockTACamera.params + [
        { 'title': 'Statistic pixels', 'name': 'statistics', 'type': 'str' },
        { 'title': 'Max. difference rms dark', 'name': 'limit_diff_rms_dark',
          'type': 'float', 'min': 0, 'value': 3 },
        { 'title': 'Max. difference mean dark', 'name': 'limit_diff_mean_dark',
          'type': 'float', 'min': 0, 'value': 3 },
        { 'title': 'Max. attempts dark', 'name': 'max_dark',
          'type': 'int', 'min': 1, 'value': 100 },
        { 'title': 'Max. difference rms whitelight',
          'name': 'limit_diff_rms_white', 'type': 'float', 'min': 0,
          'value': 3 },
        { 'title': 'Max. difference mean whitleight',
          'name': 'limit_diff_mean_white', 'type': 'float', 'min': 0,
          'value': 3 },
        { 'title': 'Max. attempts whitelight', 'name': 'max_white',
          'type': 'int', 'min': 1, 'value': 10 },
        ]

    def ini_attributes(self):
        super().ini_attributes()
        self.ta_processor = TAProcessor()

    def init_data(self):
        ta_condition = \
            TACondition(self.settings['limit_diff_mean_dark'],
                        self.settings['limit_diff_mean_dark'],
                        self.settings['max_dark'],
                        self.settings['limit_diff_rms_white'],
                        self.settings['limit_diff_mean_white'],
                        self.settings['max_white'])
        statistics_pixel = []
        statistics_pixels = \
            [[int(pix) for pix in item.split('-')]
             for item in self.settings['statistics'].split(',')]

        self.ta_processor.set_up(self.n_pixels, ta_condition, statistics_pixels)

    def single_callback(self, raw_data):
        dte, display = self.ta_processor.process_data(raw_data)

        if dte is None:
            return

        if display:
            self.dte_signal_temp.emit(dte)
        else:
            self.dte_signal.emit(dte)


if __name__ == '__main__':
    main(__file__)
