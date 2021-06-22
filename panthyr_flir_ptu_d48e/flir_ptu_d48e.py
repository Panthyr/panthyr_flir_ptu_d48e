#! /usr/bin/python3
# coding: utf-8
"""
Module: flir_ptu_d48e.py
Authors: Dieter Vansteenwegen
Institution: VLIZ (Vlaams Institute voor de Zee)
"""

__author__ = 'Dieter Vansteenwegen'
__version__ = '0.1b'
__credits__ = 'Dieter Vansteenwegen'
__email__ = 'dieter.vansteenwegen@vliz.be'
__status__ = 'Development'
__project__ = 'Panthyr'
__project_link__ = 'https://waterhypernet.org/equipment/'

import logging
import time
from .flir_ptu_d48e_connections import PTHeadConnection


def initialize_logger() -> logging.Logger:
    """Set up logger

    If the module is ran as a module, name logger accordingly as a sublogger.

    Returns:
        logging.Logger: logger instance
    """
    if __name__ == '__main__':
        return logging.getLogger('{}'.format(__name__))
    else:
        return logging.getLogger('__main__.{}'.format(__name__))


class HeadNotInitialized(Exception):
    pass


class HeadCommandError(Exception):
    pass


class PTHead():
    """
    Main control for the FLIR PTU-D48 pan/tilt head.

    Product information page:
    https://www.flir.eu/products/ptu-d48e/?model=D48E-SS-SS-000-SS

    The basic ASCII command syntax is <command><parameter><delimiter>, where:

    - <command> is the actual command
    - <parameter> is an alphanumeric value
    - <delimiter> Valid delimiter characters can be either [SPACE] or [ENTER].
    - A successfully executed command returns * <CR><LF>
    - A successfully executed query displays <N>* <QueryResult><CR><LF>
    - A failed command displays ! <ErrorMessage><CR><LF>

    When in auto stepping mode, the step size is changed dynamically.
    Units are processed as if eight step mode is selected.

    Conventions:

    - pan: rotation of the head in the same plan as its base
    - tilt: rotation of the head on the horizontal plane of its base
    - pan_position: a specific angle of pan, referenced to the forward direction
        of its base (180 degrees from connector)
        (in steps, negative=CCW seen from top)
    - tilt_position: a specific angle of tilt, referenced to the base of
        the head (in steps, negative is front pointing down)
    - Heading: a specific angle of pan, referenced to the forward direction of
        its base (180 degrees from connector)
        (-180 to 180 degrees, negative=CCW seen from top)
    - Elevation: a specific angle of tilt, referenced to the base
        of the head (-90 to +30 degrees, negative is front pointing down)


    """

    PAN_RESET_SPEED = 4000
    PAN_CONSTANT_SPEED = 3000  # PS, default: 1000
    PAN_MAX_SPEED = 4000
    TILE_RESET_SPEED = 4000
    TILT_CONSTANT_SPEED = 3000  # TS, default: 1000
    TILT_MAX_SPEED = 4000

    def __init__(self,
                 connection: PTHeadConnection,
                 do_reset: bool = True,
                 has_slipring: bool = True) -> None:
        """__init__ for class

        Args:
            connection (pthead_connection): communication to the device
            do_reset (bool, optional): reset both axes. Defaults to True.
            has_slipring (bool, optional): True for models with slipring
                to enable continuous rotation. Defaults to True.

        """

        self.log = initialize_logger()
        self._conn = connection
        self._do_reset = do_reset
        self.has_slipring = has_slipring
        self.initialized = False

    def initialize(self) -> bool:
        """Initialize the pan/tilt

        Sends list of commands and queries status of pan/tilt.

        Returns:
            bool: True if success
        """
        # disable host command echo
        self._conn.send_cmd('ED')
        time.sleep(0.6)

        self.initialized = False

        for cmd in self._generate_init_cmd():
            try:
                self._conn.send_cmd(cmd)
            except HeadCommandError() as e:
                msg = f'Command {cmd} gave reply {e}, head not initialized.'
                self.log.error(msg, exc_info=True)
                raise

        self._calculate_resolution()
        self._get_limits()

        self._do_reset = False
        self.initialized = True

        return True

    def _generate_init_cmd(self) -> list:
        """Generate list of commands for head initialization.

        Commands to be send depend on the following:
            - Head has slipring (enable continuous rotation)
            - Reset was requested

        Commands used during initialization:
        [General config]
        ED = disable host command echo
        RD = disable _do_reset on boot
        FT = terse ASCII feedback mode
        CEC = enable encoder correction mode

        [Pan axis]
        PUxxx = pan max speed
        PSxxx = pan desired speed
        PHL = pan hold power mode: low
        PML = pan move power mode: low
        RPSxxx = pan _do_reset speed
        PA1500 = pan acceleration

        [Tilt axis]
        TUxxx = tilt maximum speed
        TSxxx = desired tilt speed
        THL = tilt hold power mode: low
        TML = tilt move power mode: low
        RTSxxx = _do_reset tilt speed
        TA1500 = tilt acceleration

        [Stepping and axis _do_reset]
        WTA = tilt auto step  (!!! needs axis _do_reset after this command)
        WPA = pan auto step  (!!! needs axis _do_reset after this command)
        RT = _do_reset tilt axis
        RP =  _do_reset pan axis

        [Limits or continuous rotation]
        PNU-27067 = pan user minimum limit -174 degrees
        PXU27067 = pan user maximum limit 174 degrees
        TNU-27999 = tilt user minimum limit -90 degrees
        TXU9333 = tilt user maximum limit 30 degrees
        LU = enforce user limits
        PCE = pan continuous enable (does not need limits disabled)

        Returns:
            list: list of commands
        """

        init_cmds = [
            'FT', 'PHL', 'THR', 'PML', 'TMH', 'CEC', 'PA2000', 'TA2000', f'PU{self.PAN_MAX_SPEED}',
            f'TU{self.TILT_MAX_SPEED}'
            f'PS{self.PAN_CONSTANT_SPEED}'
            f'TS{self.TILT_CONSTANT_SPEED}'
            f'RPS{self.PAN_RESET_SPEED}'
            f'RTS{self.TILE_RESET_SPEED}'
        ]

        if self._do_reset:
            # axis reset and calibration cmds
            init_cmds.extend(['WTA', 'WPA', 'RT', 'RP', 'RD'])

        # Add commands for either user limits or continuous rotation
        # These should be executed last
        if self.has_slipring:
            init_cmds.extend(['PCE'])
        else:
            init_cmds.extend(['TNU-27999', 'TXU9333', 'PNU-27067', 'PXU27067', 'LU'])

        self.log.debug(f'Commands generated for init: {init_cmds}')

        return init_cmds

        def _calculate_resolution() -> None:
            pass

        def _get_limits() -> None:
            pass
