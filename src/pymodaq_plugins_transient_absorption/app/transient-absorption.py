import numpy as np
import csv, time
from qtpy.QtCore import QByteArray, QSettings, QTimer
from qtpy.QtGui import QKeySequence
from qtpy.QtWidgets import QMainWindow, QWidget, QApplication, QProgressBar, \
    QFileDialog, QLabel, QGridLayout, QVBoxLayout
from pyqtgraph import GraphicsLayoutWidget, PlotDataItem, FillBetweenItem
from pyqtgraph import PlotItem, PlotDataItem, ViewBox
from pyqtgraph import GraphicsWidget, PlotWidget
from pymodaq.control_modules.daq_viewer import DAQ_Viewer
from pymodaq.utils.data import DataToExport, DataFromPlugins
from pymodaq_gui.utils.custom_app import CustomApp
from pymodaq_gui.plotting.data_viewers.viewer1D import Viewer1D
from pymodaq_gui.utils.dock import DockArea, Dock
from pymodaq_gui.utils.main_window import MainWindow
from pymodaq_plugins_stresing.daq_viewer_plugins.plugins_1D.daq_1Dviewer_Lscpcie\
    import DAQ_1DViewer_Lscpcie, MeasurementState
from pymodaq_plugins_stresing.averager import Averager


RAW             = 0
WITH_BACKGROUND = 1
DIFFERENCE      = 2
TA              = 3


IGNORE_DATA     = 1 # to plugin??
TAKE_BACKGROUND = 2
ACQUIRE_DATA    = 0

class StatusWidget(QWidget):

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)

        layout = QVBoxLayout()
        grid = QGridLayout()
        self.status_label, row = self.add_entry("state", grid, 0)
        self.samples_label, row = self.add_entry("samples", grid, row, "0")
        self.sig_back_scale_label, row = \
            self.add_entry("signal background", grid, row, "1.0")
        self.ref_back_scale_label, row = \
            self.add_entry("reference background", grid, row, "1.0")

        layout.addLayout(grid)
        layout.addStretch()
        self.setLayout(layout)

    def add_entry(self, name, layout, row, text=None):
        layout.addWidget(QLabel(name), row, 0)
        entry = QLabel("" if text is None else text)
        layout.addWidget(entry, row, 1)
        return entry, row+1

    def set_state(self, state):
        self.status_label.setText(str(state))
        
    def set_samples(self, samples):
        self.samples_label.setText(str(samples))

    def set_scaling(self, signal, reference):
        self.sig_back_scale_label.setText(str(signal))
        self.ref_back_scale_label.setText(str(reference))


class TAApp(CustomApp):

    measurement_modes = { 'Raw': RAW, 'Background Subtracted': WITH_BACKGROUND,
                          'Difference': DIFFERENCE, 'Transient Absorption': TA }

    params = [{'name': 'averaging', 'title': 'Averaging',
               'type': 'int', 'min': 1, 'max': 1000, 'value': 1,
               'tip': 'Software Averaging'},
              {'name': 'measurement_mode', 'title': 'Measurement Mode',
               'type': 'list', 'limits': list(measurement_modes.keys()),
               'tip': 'Measurement Mode'},
              {'name': 'pump_shutter', 'title': 'Pump Shutter Open',
               'type': 'bool', 'value': True},
              {'name': 'probe_shutter', 'title': 'Probe Shutter Open',
               'type': 'bool', 'value': True},
              ]

    def __init__(self, parent: DockArea, plugin):
        super().__init__(parent)

        self.plugin = plugin
        self.setup_ui()

        # keep screen geometry between runs, should be integrated into
        # PyMoDAQ settings. Tends anyway to get kind of messy because Qt and
        # pyqtgraph don't handle the matter very consistently.
        settings = QSettings("chiphy", "transient-absorption")
        geometry = settings.value("geometry", QByteArray())
        self.mainwindow.restoreGeometry(geometry)
        state = settings.value("dockarea", None)
        if state is not None:
            try:
                self.dockarea.restoreState(state)
            except: # pyqtgraph's state restoring is not very fail safe
                # erease inconsistent settings in case pyqtgraph trips
                settings.setValue("dockarea", None)

        # Retrieve spacing of first column in case the user has made it fully
        # visible in a previous run of the program.
        header = settings.value("settings-header-0", None)
        if header is not None:
            self._settings_tree.widget.header().resizeSection(0, int(header))

        self.measurement_mode = RAW
        self.measurement_state = MeasurementState.IDLE
        self.acquiring = False
        self.adjust_actions()
        self.adjust_parameters()

    def setup_docks(self):
        # left column: essential parameters at top, small plots for dark and
        # reference signals
        # main area for current data

        # top left, essential parameters
        self.docks['settings'] = Dock('Application Settings')
        self.dockarea.addDock(self.docks['settings'])
        self.docks['settings'].addWidget(self.settings_tree)

        self.docks['stats'] = Dock('Stats')
        self.dockarea.addDock(self.docks['stats'], 'bottom',
                              self.docks['settings'])
        self.status_widget = StatusWidget()
        self.docks['stats'].addWidget(self.status_widget)
    
        # main area with spectrum plot
        upper_spectrum_dock = Dock('Signal')
        self.docks['upper_spectrum'] = \
            self.dockarea.addDock(upper_spectrum_dock, "right",
                                  self.docks['settings'])
        upper_spectrum_widget = QWidget()
        self.upper_spectrum_viewer = Viewer1D(upper_spectrum_widget)
        self.upper_spectrum_viewer.toolbar.hide()
        upper_spectrum_dock.addWidget(upper_spectrum_widget)

        lower_spectrum_dock = Dock('Reference')
        self.docks['lower_spectrum'] = \
            self.dockarea.addDock(lower_spectrum_dock, "bottom",
                                  self.docks['upper_spectrum'])
        lower_spectrum_widget = QWidget()
        self.lower_spectrum_viewer = Viewer1D(lower_spectrum_widget)
        self.lower_spectrum_viewer.toolbar.hide()
        lower_spectrum_dock.addWidget(lower_spectrum_widget)

        # plot for whitelight
        whitelight_dock = Dock('Whitelight')
        self.docks['whitelight'] = \
            self.dockarea.addDock(whitelight_dock, "bottom",
                                  self.docks['stats'])
        whitelight_widget = QWidget()
        self.whitelight_viewer = Viewer1D(whitelight_widget)
        self.whitelight_viewer.toolbar.hide()

        whitelight_dock.addWidget(whitelight_widget)

        # separate window with raw detector data
        self.daq_viewer_area = DockArea()
        self.detector = \
            DAQ_Viewer(self.daq_viewer_area, title=self.plugin, init_h5=False)
        self.detector.daq_type = 'DAQ1D'
        self.detector.detector = self.plugin
        self.detector.init_hardware()
        
        #shutter = self.settings.child('pump_shutter').value()
        #self.detector.settings.child('detector_settings',
        #                             'pump_open').setValue(shutter)
        #shutter = self.settings.child('probe_shutter').value()
        #self.detector.settings.child('detector_settings',
        #                             'probe_open').setValue(shutter)

        self.mainwindow.set_shutdown_callback(self.quit_function)
        self.detector.grab_status.connect(self.mainwindow.disable_close)

    def setup_actions(self):
        self.add_action('acquire', 'Acquire', 'spectrumAnalyzer',
                        "Acquire", checkable=False, toolbar=self.toolbar)
        self.add_action('save', 'Save', 'SaveAs', "Save current data",
                        checkable=False, toolbar=self.toolbar)        
        self.add_action('show', 'Show/hide', 'read2', "Show Hide DAQViewer",
                        checkable=True, toolbar=self.toolbar)

    def connect_things(self):
        self.quit_action.triggered.connect(self.mainwindow.close)
        self.connect_action('save', self.save_current_data)
        self.connect_action('show', self.show_detector)
        self.connect_action('acquire', self.start_acquiring)
        self.detector.grab_done_signal.connect(self.take_data)

    def setup_menu(self):
        file_menu = self.mainwindow.menuBar().addMenu('File')
        self.affect_to('save', file_menu)

        file_menu.addSeparator()
        self.quit_action = file_menu.addAction("Quit", QKeySequence('Ctrl+Q'))

    def value_changed(self, param):
        # <<-- param widget should be readonly during measurement
        if param.name() == "averaging":
            self.detector.settings.child('main_settings', 'Naverage') \
                                         .setValue(param.value())
            self.have_background = False
            self.adjust_actions()

        elif param.name() == "measurement_mode":
            self.measurement_mode = self.measurement_modes[param.value()]

        elif param.name() == "pump_shutter":
            self.detector.settings.child('detector_settings',
                                         'pump_open').setValue(param.value())

        elif param.name() == "probe_shutter":
            self.detector.settings.child('detector_settings',
                                         'probe_open').setValue(param.value())

        self.adjust_operation()
        self.adjust_actions()

    def adjust_operation(self):
        """Stop acquisition if background / reference is missing but needed"""
        pass

    def adjust_actions(self):
        """Disable actions which need other actions to be performed first.
        A reference can only be taken when a background has been measured.
        Acquisition in absorption mode needs a reference (and therefore also
        a background).
        """
        pass

    def adjust_parameters(self):
        """Hide parameters which are not needed in current measurment mode."""
        pass
        #for child in self.scan_params:
        #    if child in self.visible_params[self.scan_mode]:
        #        self.settings.child(child).show()
        #    else:
        #        self.settings.child(child).hide()

    def show_detector(self, status):
        self.daq_viewer_area.setVisible(status)

    def set_measurement_state(self, state):
        self.measurement_state = state
        self.detector.settings.child('detector_settings', 'measurement_state')\
                              .setValue(state.value)
        self.status_widget.set_state(state)
        
    def start_acquiring(self):
        """Start acquisition"""

        if self.acquiring: # rather stop it
            self.stop_acquiring()
            return

        if self.measurement_mode >= WITH_BACKGROUND:
            self.set_measurement_state(MeasurementState.PREPARE_BACKGROUND)
            self.set_sĥutters({'pump': False, 'probe': False})
        else:
            self.set_measurement_state(MeasurementState.RECORD_RAW_DATA)

        self.acquiring = True
        self.detector.grab() # just go
        return

        # ignore this for now
        result = QFileDialog.getSaveFileName(caption="Save Data", dir=".",
                                             filter="*.csv")
        if result is None:
            return

        # <<-- unclear: where does init of param values happen?
        
        #self.detector.settings.child('detector_settings', 'integration_time') \
        #    .setValue(self._settings_tree.value("integration_time") * 1000)
        
        # determine number of significant digits according to
        # error = sqrt(Naverage) assuming the best case with
        # error(Naverage=1) is 1
        n_average = \
            self.detector.settings.child('main_settings', 'Naverage').value()
        if n_average > 1:
            self.format_string = \
                '\t{val:.%df}' % (int(np.log10(np.sqrt(n_average))) + 1)
        else:
            self.format_string = '\t{val:.0f}'

        # write wavelengths into file
        self.data_file = open(result[0], "wt")
        self.data_file.write('0\t0')
        for wl in self.detector.controller.wavelengths:
            self.data_file.write('\t%.1f' % wl)
        self.data_file.write('\n')

        # background (time delay -1) and reference (time delay -2) if needed
        if self.measurement_mode >= WITH_BACKGROUND:
            self.write_spectrum(-1, 0, self.background)
            if self.measurement_mode == ABSORPTION:
                self.write_spectrum(-2, 0, self.reference)

        # calculate schedule, only linear for the moment, ignore lin-log
        # QTimer counts in milliseconds
        scan_end = self.settings['scan_end'] * 1000
        linear_step = self.settings['linear_step'] * 1000
        n_measurements = int(scan_end / linear_step) + 1
        self.scheduled_measurement_times = \
            np.linspace(0, scan_end, n_measurements) \
            - self.settings['integration_time'] * 1000 - 20

        # and go
        self.current_time_index = 0
        self.system_start_time = None
        self.detector.snap()

    def set_sĥutters(self, shutter_states):
        changed = False
        if 'pump' in shutter_states:
            self.detector.settings.child('detector_settings', 'pump_open') \
                .setValue(shutter_states['pump'])
            changed = True
        if 'probe' in shutter_states:
            self.detector.settings.child('detector_settings', 'probe_open') \
                .setValue(shutter_states['pump'])
            changed = True
        if changed:
            QTimer.singleShot(100, self.shutter_ready)

    def shutter_ready(self):
        print("got shutter ready")
        if self.measurement_state == MeasurementState.PREPARE_BACKGROUND:
            self.set_measurement_state(MeasurementState.TAKE_BACKGROUND)
        elif self.measurement_state == MeasurementState.PREPARE_TA:
            self.set_measurement_state(MeasurementState.BACKGROUND_SUBTRACTED)

    def background_failed(self):
        QMessageBox.critical()
        self.stop_acquiring()

    def whitelight_ready(self):
        self.measurement_state = PREPARE_NORMAL
        self.set_sĥutters({'pump': True, 'probe': True})

    def take_data(self, data: DataToExport):
        samples = data.get_data_from_name('samples')[0][0]
        self.status_widget.set_samples(samples)
        scalings = data.get_data_from_name('scalings')
        if scalings is not None:
            self.status_widget.set_scaling(scalings[0][0], scalings[1][0])

        if self.measurement_state == MeasurementState.TAKE_BACKGROUND:
            mean = data.get_data_from_name('mean')
            self.upper_spectrum_viewer.show_data(mean)
            rms = data.get_data_from_name('rms')
            self.lower_spectrum_viewer.show_data(rms)

            background = data.get_data_from_name('background')
            if background is not None:
                self.whitelight_viewer.show_data(background)
                print("got background ready")
                self.set_measurement_state(MeasurementState.PREPARE_TA)
                self.set_sĥutters({'pump': True, 'probe': True})

            QApplication.processEvents()
            return

        if self.measurement_state == MeasurementState.RECORD_RAW_DATA \
           or self.measurement_state == MeasurementState.BACKGROUND_SUBTRACTED:
            mean = data.get_data_from_name('mean')
            self.upper_spectrum_viewer.show_data(mean)
            rms = data.get_data_from_name('rms')
            self.lower_spectrum_viewer.show_data(rms)
            #dfp = DataFromPlugins(name='whitelight',
            #                      data=[whitelight_data[0]], dim='Data1D',
            #                            labels=['reference'])
            #self.whitelight_spectrum_viewer.show_data(dfp)
            QApplication.processEvents()
            return

    def write_spectrum(self, t1, t2, spectrum):
        """Writes a single spectrum to file.
        The first two columns contain the system time at data retrieval
        and the time stamp returned by the avaspec library, respectively.
        """
        self.data_file.write('%d\t%d'
                             % (int(np.floor(t1 + 0.5)),
                                int(np.floor(t2 + 0.5))))
        if self.measurement_mode == ABSORPTION and t1 != -1:
            # To save space in the data file, absorption data are stored as
            # integer numbers. 1 LSB is 1µOD.
            for value in spectrum:
                self.data_file.write('\t%d' % (value * 1000 + 0.5))
        else:
            for value in spectrum:
                self.data_file.write(self.format_string.format(val = value))
        self.data_file.write('\n')

    def stop_acquiring(self):
        self.acquiring = False
        self.set_measurement_state(MeasurementState.IDLE)
        self.detector.stop_grab()

    def save_current_data(self):
        """Save dat currently displayed on the main plot."""
        if not hasattr(self, 'current_data'):
            return
        result = QFileDialog.getSaveFileName(caption="Save Data", dir=".",
                                             filter="*.csv")
        if result is None or not len(result[0]):
            return
        wavelengths = self.detector.controller.wavelengths
        with open(result[0], "wt") as csv_file:
            writer = csv.writer(csv_file, delimiter='\t',
                                quotechar='|', quoting=csv.QUOTE_MINIMAL)
            for i,wl in enumerate(wavelengths):
                writer.writerow([wl, self.current_data[i]])

    def quit_function(self):
        self.clean_up()
        self.mainwindow.close()

    def clean_up(self):
        self.detector.quit_fun()
        QApplication.processEvents()
        settings = QSettings("chiphy", "transient-absorption")
        settings.setValue("geometry", self.mainwindow.saveGeometry())
        settings.setValue("dockarea", self.dockarea.saveState())
        settings.setValue("settings-header-0",
                          self._settings_tree.widget.header().sectionSize(0))


def main():
    import sys
    from pymodaq_gui.utils.utils import mkQApp
    from qtpy.QtCore import pyqtRemoveInputHook

    if len(sys.argv) > 1:
        if sys.argv[1] == '--simulate':
            plugin = "LscpcieDebug"
        elif len(sys.argv) > 2 and sys.argv[1] == '--plugin':
            plugin=sys.argv[2]
            del sys.argv[2]
            del sys.argv[1]
        else:
            raise RuntimeError("command line argument error")
    else:
        plugin='Lscpcie'

    app = mkQApp(plugin)
    pyqtRemoveInputHook() # needed for using pdb inside the qt eventloop

    mainwindow = MainWindow()
    dockarea = DockArea()
    mainwindow.setCentralWidget(dockarea)

    prog = TAApp(dockarea, plugin=plugin)
    mainwindow.application = prog # not very clean, could be done by event filter
    mainwindow.show()

    app.exec()


if __name__ == '__main__':
    main()
