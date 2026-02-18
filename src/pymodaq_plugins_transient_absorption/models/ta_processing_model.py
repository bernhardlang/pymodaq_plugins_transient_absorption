import numpy as np

from pymodaq_plugins_datamixer.extensions.utils.model import DataMixerModel
from pymodaq_data.data import DataToExport, DataWithAxes
from pymodaq_gui.parameter import Parameter


class DataMixerModelFit(DataMixerModel):
    params = [

    ]

    def ini_model(self):
        pass

    def update_settings(self, param: Parameter):
        pass

    def process_dte(self, dte: DataToExport):
        dte_processed = DataToExport('computed')
        #dwa = dte.get_data_from_full_name('Spectrum - ROI_00/Hlineout_ROI_00').deepcopy()

        dwa = DataWithAxes()
        dte_processed.append(dwa)
        #do nothing
        #dte_processed.append(dwa.fit(gaussian_fit, self.get_guess(dwa)))

        return dte_processed

