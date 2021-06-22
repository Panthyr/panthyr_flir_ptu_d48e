#! /usr/bin/python3
# coding: utf-8
"""
Module: flir_ptu_d48e_connections.py
Authors: Dieter Vansteenwegen
Institution: VLIZ (Vlaams Institute voor de Zee)
"""

__author__ = "Dieter Vansteenwegen"
__version__ = "0.1b"
__credits__ = "Dieter Vansteenwegen"
__email__ = "dieter.vansteenwegen@vliz.be"
__status__ = "Development"
__project__ = "Panthyr"
__project_link__ = "https://waterhypernet.org/equipment/"

import logging
import time
from typing import Union
import select
import socket as sckt


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


class PTHeadIPReplyTimeout(Exception):
    """Timeout waiting for reply from head"""
    pass


class PTHeadIPIncorrectReply(Exception):
    """Incorrect reply from head"""
    pass


class PTHeadConnection():
    """Base class for connection to the head."""
    pass


class PTHeadIPConnection(PTHeadConnection):
    """IP communication for the flir PTU-D48.

    Provides functions to connect to the pan/tilt head over Ethernet
    """

    PTU_IP = '192.168.100.190'
    PTU_PORT = 4000
    TIMEOUT_SOCKET = 5
    TIMEOUT_DEFAULT = 0.5
    TIMEOUT_TILT = 25
    TIMEOUT_PAN = 32
    TIMEOUT_RST_AXIS = 15

    def __init__(self, ip: str = PTU_IP, port: int = PTU_PORT, timeout: int = TIMEOUT_SOCKET):
        """__init__ for class

        Args:
            ip (str, optional): IP address of p/t head. Defaults to PTU_IP.
            port (int, optional): socket number. Defaults to PTU_PORT.
            timeout (int, optional): timeout for socket connection. Defaults to TIMEOUT_SOCKET.
        """
        self.ip = ip
        self.port = port
        self.timeout = timeout
        self.log = initialize_logger()

    def connect(self) -> None:
        """Set up socket connection"""
        try:
            self.socket = sckt.create_connection((self.ip, self.port), self.timeout)
        except sckt.timeout as e:
            msg = f'Problem setting up socket for pan/tilt head ({self.ip}:{self.port}): {e}'
            self.log.error(msg, exc_info=True)
            raise
        else:
            self.socket.setsockopt(sckt.IPPROTO_TCP, sckt.TCP_NODELAY,
                                   1)  # disable Nagle's algorithm
            self._empty_rcv_socket()

    def _empty_rcv_socket(self) -> None:
        """Empty the receive buffer of the socket."""
        while True:
            read, __, __ = self.select.select([self.socket], [], [], 0)
            if len(read) == 0:
                return
            self.socket.recv(1)

    def send_cmd(self, command: str, timeout: Union[float, None] = None) -> None:
        """Send command and check reply.

        The command is sent over the socket connection.
        Within the timeout window, the socket is read out for the reply.
        The reply is then checked. Axis errors are ignored if command is an axis reset command.
        Exected reply is '*'

        Args:
            command (str): Command to be sent (without <CR>)
            timeout (Union[float, None], optional): override default timeout constants,
                for example for move operations.
                In seconds.
                Defaults to None.
        
        Raises:
            PTHeadIPReplyTimeout: if head does not respond with full line within timeout
            PTHeadIncorrectReply: if the reply is not correct
        """
        command = command.upper()

        self._empty_rcv_socket()
        self._send_raw(command)

        if not timeout:
            timeout = self._get_timeout(command)

        try:
            reply = self._get_reply(timeout)
        except PTHeadIPReplyTimeout as e:
            self.log.error(e, exc_info=True)
            raise

        # expect error messages if command is a reset axis command
        expect_limit_err = command.upper() in ['RP', 'RT']

        try:
            self._check_reply(reply, expect_limit_err)
        except PTHeadIPIncorrectReply:
            self.log.error(f'Incorrect reply for command {command}: {reply}', exc_info=True)
            raise

    def _empty_rcv_socket(self) -> None:
        """Empty the receive buffer of the socket."""
        while True:
            read, __, __ = select.select([self.socket], [], [], 0)
            if len(read) == 0:
                return
            self.socket.recv(1)

    def send_query(self, query: str) -> str:
        pass

    def _send_raw(self, command: str) -> None:
        """Send command over socket

        <CR> character is added at the end of command, and converted to bytes

        Args:
            command (str): command to be sent
        """
        self.socket.send((command + '\r').encode())

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
            return self.TIMEOUT.PAN
        if command[0:2] in ['RT', 'RP']:
            return self.TIMEOUT_RST_AXIS
        return self.TIMEOUT_DEFAULT

    def _get_reply(self, timeout: float) -> str:
        """Get raw reply within timeout.

        Formatting:
            Replies start and end with <LF> (0xA, dec 10).
            Succesfully executed command:
                <LF>*<CR><LF>
            Response to query:
                <LF>*<REPLY><CR><LF>
                    example:
                    <LF>* 23.142857<CR><LF>
            Errors:
                <LF>(!<MSG>)*number of errors<CR><LF>
                    examples:
                    <LF>! Illegal Command Entered<CR><LF>
                    <LF>!T!T*<CR><LF>

        Args:
            timeout (float): reply timeout in seconds 

        Raises:
            PTHeadIPReplyTimeout: full/correct reply not received within timeout

        Returns:
            str: reply, without leading <LF> or ending <CR><LF>
        """
        rx = ''
        orig_timeout = timeout

        while timeout > 0:
            # check if there's data in the buffer
            rx += self._rx_from_socket()

            time.sleep(0.1)
            try:
                if rx[0] == '\n' and rx[-2:] == '\r\n':
                    return rx[1:-2]
            except IndexError:
                # not enough data yet
                pass
            timeout -= 0.1
        raise PTHeadIPReplyTimeout(f'Received [{repr(rx)}] after {orig_timeout}s')

    def _rx_from_socket(self) -> str:
        """Try to read from socket.

        Returns:
            str: received characters. Empty string if none received.
        """
        rx_buffer_readout = ''
        rx_waiting, _, _ = select.select([self.socket], [], [], 0)
        while len(rx_waiting) > 0:
            rx_buffer_readout += self.socket.recv(1).decode()
            rx_waiting, _, _ = select.select([self.socket], [], [], 0)
        return rx_buffer_readout

    def _check_reply(self, reply: str, expect_limit_err: bool):
        """Check reply, raising error if incorrect

        If axis errors are to be expected, first strips '!P' and '!T'.
        Reply should only consist of a '*'. 

        Args:
            reply (str): the reply to be checked
            expect_limit_err (bool): set True if command is an axis reset command

        Raises:
            PTHeadIPIncorrectReply: an incorrect reply was received.
        """

        if expect_limit_err:
            # get rid of '!P' and '!T'
            import re
            reply = re.sub('!T|!P', '', reply)
        if reply != '*':
            raise PTHeadIPIncorrectReply
