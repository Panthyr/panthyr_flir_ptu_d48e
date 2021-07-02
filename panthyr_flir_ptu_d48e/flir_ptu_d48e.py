#! /usr/bin/python3
# coding: utf-8

# Module: flir_ptu_d48e.py
# Authors: Dieter Vansteenwegen
# Institution: VLIZ (Vlaams Institute voor de Zee)

__author__ = 'Dieter Vansteenwegen'
__version__ = '0.1b'
__credits__ = 'Dieter Vansteenwegen'
__email__ = 'dieter.vansteenwegen@vliz.be'
__status__ = 'Development'
__project__ = 'Panthyr'
__project_link__ = 'https://waterhypernet.org/equipment/'

import logging
import time
from .flir_ptu_d48e_connections import PTHeadConnection, PTHeadIPConnection
from typing import Union
from .flir_ptu_d48e_exceptions import PTHeadIncorrectReply, PTHeadNotInitialized, PTHeadReplyTimeout


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
    PAN_CONSTANT_SPEED = 4000  # PS, default: 1000
    PAN_MAX_SPEED = 4000
    TILT_RESET_SPEED = 4000
    TILT_CONSTANT_SPEED = 4000  # TS, default: 1000
    TILT_MAX_SPEED = 4000
    TIMEOUT_DEFAULT = 0.5
    TIMEOUT_TILT = 25
    TIMEOUT_PAN = 32
    TIMEOUT_RST_AXIS = 15
    TIMEOUT_QUERY = 0.5

    def __init__(self,
                 connection: PTHeadIPConnection,
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
        self._conn: PTHeadIPConnection = connection
        self._do_reset: bool = do_reset
        self.has_slipring: bool = has_slipring
        self.initialized: bool = False
        self.debug: int = 0
        self.resolution_pan: float = 0
        self.resolution_tilt: float = 0

    def initialize(self) -> bool:
        """Initialize the pan/tilt

        Sends list of commands and queries status of pan/tilt.

        Returns:
            bool: True if success
        """
        # head needs a bit of time to display welcome message, which we don't want to parse
        time.sleep(0.6)
        # disable host command echo
        self._send_cmd('ED')

        self.initialized = False

        for cmd in self._generate_init_cmd():
            self._send_cmd(cmd)

        self._calculate_resolution()
        self._get_limits()

        self._do_reset = False
        self.initialized = True

        return True

    def _calculate_resolution(self) -> None:
        """Calculate the resolution of steps.

        Results are in degrees per position.
        PR and TR queries return the resolution in arc degrees per position. 
        Divide by 3600 to get degrees per position.
        """
        res_pan_arc = float(self._send_query('PR'))
        self.resolution_pan = res_pan_arc / 3600
        res_tilt_arc = float(self._send_query('TR'))
        self.resolution_tilt = res_tilt_arc / 3600

    def _get_limits(self) -> None:
        # TODO: Check if this is even required.
        # User limits are set by _generate_init_cmd and are not used for pan if
        # unit has slipring...
        pass

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
            f'TU{self.TILT_MAX_SPEED}', f'PS{self.PAN_CONSTANT_SPEED}',
            f'TS{self.TILT_CONSTANT_SPEED}', f'RPS{self.PAN_RESET_SPEED}',
            f'RTS{self.TILT_RESET_SPEED}'
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

    def _send_core(self, command: str, timeout: float) -> str:
        """Basic send function

        Clean up command, send with timeout, return reply

        Args:
            command (str): command or query
            timeout (float): timeout for reply

        Returns:
            str: reply from head
        """
        command = command.upper().strip()

        try:
            return self._conn.send_and_get(command, timeout)
        except PTHeadReplyTimeout:
            self.log.error(f'timeout (>{timeout}) for command {command}')
            raise

    def send_cmd(self, command: str, timeout: Union[float, None] = None) -> None:
        """Sends command, but only if head is initialized

        Args:
            command (str): command to be sent
            timeout (Union[float,None], optional): timeout. Defaults to None.

        Raises:
            HeadNotInitialized: If head is not yet initialized

        Returns:
            None
        """
        if not self.initialized:
            raise PTHeadNotInitialized(
                'Head is not yet initialized, call initialize function first.')
        return self._send_cmd(command, timeout)

    def _send_cmd(self, command: str, timeout: Union[float, None] = None) -> None:
        """Send command to head and check reply

        If required, calculates expected timeout.
        Sends command and waits for reply.
        Expects '*' as reply.
        For axis reset operations, '!T' and '!P' parts of the reply are ignored.

        Args:
            command (str): command to be sent
            timeout (Union[float, None], optional): timeout. 
                If none is given, the timeout constants are used, 
                    depending on type of command. 
                Defaults to None.
        """
        if not timeout:
            timeout = self._get_timeout(command)

        reply = self._send_core(command, timeout)
        if self.debug:
            print(f'reply from command "{command}": "{reply}"')

        # expect error messages if command is a reset axis command
        expect_limit_err = command.upper() in ['RP', 'RT']

        try:
            self._check_cmd_reply(reply, expect_limit_err)
        except PTHeadIncorrectReply:
            self.log.error(f'Incorrect reply "{reply}" for command "{command}"')
            raise

    def _check_cmd_reply(self, reply: str, expect_limit_err: bool):
        """Check reply, raising error if incorrect

        If axis errors are to be expected, first strips '!P' and '!T'. 
        Reply should only consist of a '*'.

        Args:
            reply (str): the reply to be checked
            expect_limit_err (bool): set True if command is an axis reset command

        Raises:
            PTHeadIncorrectReply: an incorrect reply was received.
        """

        if expect_limit_err:
            # get rid of '!P' and '!T'
            import re
            reply = re.sub('!T|!P', '', reply)
        if reply != '*':
            raise PTHeadIncorrectReply

    def _get_timeout(self, command: str) -> float:
        """Get timeout for given command

        Args:
            command (str): command for which the timeout should be chosen

        Returns:
            float: timeout value in seconds
        """
        if command[0:2] == 'TP':
            return self.TIMEOUT_TILT
        if command[0:2] == 'PP':
            return self.TIMEOUT_PAN
        if command[0:2] in ['RT', 'RP']:
            return self.TIMEOUT_RST_AXIS
        return self.TIMEOUT_DEFAULT

    def send_query(self, query: str) -> str:
        """Sends query, but only if head is initialized

        Args:
            query (str): query to be sent

        Raises:
            PTHeadNotInitialized: If head is not yet initialized

        Returns:
            str: stripped reply from head
        """
        if not self.initialized:
            raise PTHeadNotInitialized(
                'Head is not yet initialized, call initialize function first.')
        return self._send_query(query)

    def _send_query(self, query: str) -> str:
        """Send query to head and return (clean) reply

        Uses TIMEOUT_QUERY as timeout.
        Sends query and waits for reply.
        Expects reply followed by '*'.

        Args:
            query (str): query to be sent

        Returns:
            str: clean reply
        """
        reply = self._send_core(query, self.TIMEOUT_QUERY)
        return self._check_query_reply(reply)

    def _check_query_reply(self, reply: str) -> str:
        """Check reply, raising error if incorrect

        Reply should only consist of a '*', a space and then the value.

        Args:
            reply (str): the reply to be checked

        Raises:
            PTHeadIncorrectReply: an incorrect reply was received.

        Resturns:
            str: the raw value
        """
        if reply[:2] != '* ':
            raise PTHeadIncorrectReply
        return reply[2:]

    def show_parameters(self) -> dict:
        """Get voltage and temperatures from head

        Command "O" returns a string as 13.2,99,97,104 where:
            - 13.2 is the supply voltage
            - 99 is the head temperature (in Fahrenheit) 
            - 97 is the pan temperature (in Fahrenheit) 
            - 104 is the tilt temperature (in Fahrenheit) 

        Returns:
            dict: contains elements 'voltage', 'temp_head', 'temp_pan', 'temp_tilt'
                values rounded to one decimal.
        """
        dict_rtn = {}

        dict_rtn['voltage'], *temps = self._send_query('O').split(',')

        def _f_to_c(f: str) -> float:
            c = (float(f) - 32) / 1.8
            return round(c, 1)

        dict_rtn['temp_head'] = _f_to_c(temps[0])  # type: ignore
        dict_rtn['temp_pan'] = _f_to_c(temps[1])  # type: ignore
        dict_rtn['temp_tilt'] = _f_to_c(temps[2])  # type: ignore

        return dict_rtn