from typing import Union, List, Dict
from pymodaq.control_modules.move_utility_classes import DAQ_Move_base, \
    comon_parameters_fun, main, DataActuatorType, DataActuator
from pymodaq_utils.utils import ThreadCommand
from pymodaq_gui.parameter import Parameter
from pymodaq_plugins_transient_absorption.hardware.controller \
    import MockTAController

class DAQ_Move_MockDelayLine(DAQ_Move_base):
    """ Instrument plugin class for an actuator.
    
    Attributes:
    -----------
    controller: object
        The particular object that allow the communication with the hardware,
        in general a python wrapper around the hardware library.

    """
    is_multiaxes = False
    _controller_units: Union[str, List[str]] = 'ps'
    _epsilon: Union[float, List[float]] = 1e-15
    data_actuator_type = DataActuatorType.DataActuator

    params = [
    ] + comon_parameters_fun(is_multiaxes, epsilon=_epsilon)

    def ini_attributes(self):
        self.controller: MockTAController = None

    def get_actuator_value(self):
        """Get the current value from the hardware with scaling conversion.

        Returns
        -------
        float: The position obtained after scaling conversion.
        """
        pos = DataActuator(data=self.controller.delay_line.get_value(),
                           units=self.axis_unit)
        pos = self.get_position_with_scaling(pos)
        return pos

    def close(self):
        """Terminate the communication protocol"""
        pass

    def commit_settings(self, param: Parameter):
        """Apply the consequences of a change of value in the detector settings

        Parameters
        ----------
        param: Parameter
            A given parameter (within detector_settings) whose value has been
            changed by the user
        """
        pass

    def ini_stage(self, controller=None):
        """Actuator communication initialization

        Parameters
        ----------
        controller: (object)
            custom object of a PyMoDAQ plugin (Slave case). None if only one
            actuator by controller (Master case)

        Returns
        -------
        info: str
        initialized: bool
            False if initialization failed otherwise True
        """
        if self.is_master:
            self.controller = MockTAController()
        else:
            self.controller = controller

        info = "Mock delay line initialised"
        return info, True

    def move_abs(self, value: DataActuator):
        """ Move the actuator to the absolute target defined by value

        Parameters
        ----------
        value: (float) value of the absolute target positioning
        """
        value = self.check_bound(value)
        self.target_value = value
        value = self.set_position_with_scaling(value)
        self.controller.delay_line.move_at(value.value(self.axis_unit))
        self.emit_status(ThreadCommand('Update_Status', ['Moved MockDelayLine']))

    def move_rel(self, value: DataActuator):
        """ Move the actuator to the relative target actuator value defined
            by value

        Parameters
        ----------
        value: (float) value of the relative target positioning
        """
        value = self.check_bound(self.current_position + value) \
            - self.current_position
        self.target_value = value + self.current_position
        value = self.set_position_relative_with_scaling(value)

        self.controller.delay_line.move_at(value.value(self.axis_unit))
        self.emit_status(ThreadCommand('Update_Status', ['Moved MockDelayLine']))

    def move_home(self):
        """Call the reference method of the controller"""
        self.emit_status(ThreadCommand('Update_Status',
                                       ['Move Home not implemented']))

    def stop_motion(self):
        """Stop the actuator and emits move_done signal"""
        self.move_done()


if __name__ == '__main__':
    main(__file__)
