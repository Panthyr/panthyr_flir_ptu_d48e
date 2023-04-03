#! /usr/bin/python3
# -*- coding: utf-8 -*-
# Authors: Dieter Vansteenwegen
# Institution: VLIZ (Vlaams Instituut voor de Zee)

__author__ = 'Dieter Vansteenwegen'
__email__ = 'dieter.vansteenwegen@vliz.be'
__project__ = 'Panthyr'
__project_link__ = 'https://waterhypernet.org/equipment/'

import logging
import time
import select
import socket as sckt
from .d48e_exceptions import PTHeadReplyTimeout


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


class PTHeadConnection():
    """Base class for connection to the head."""
    pass


class PTHeadIPConnection(PTHeadConnection):
    """IP communication for the flir PTU-D48.

    Provides functions to connect to the pan/tilt head over Ethernet
    """

    PTU_IP = '192.168.100.105'
    PTU_PORT = 4000
    TIMEOUT_SOCKET = 5

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
        self._log = initialize_logger()
        self.connect()

    def connect(self) -> None:
        """Set up socket connection."""
        try:
            self.socket = sckt.create_connection((self.ip, self.port), self.timeout)
        except (sckt.timeout, OSError) as e:
            msg = f'Problem setting up socket for pan/tilt head ({self.ip}:{self.port})'
            raise PTHeadReplyTimeout(msg) from e
        else:
            self.socket.setsockopt(sckt.IPPROTO_TCP, sckt.TCP_NODELAY,
                                   1)  # disable Nagle's algorithm
            self._empty_rcv_socket()

    def send_and_get(self, command: str, timeout: float, is_retry: bool = False) -> str:
        """Send command and check reply.

        The command is sent over the socket connection.
        Within the timeout window, the socket is read out for the reply.
        The reply is then checked. Axis errors are ignored if command is an axis reset command.
        Expected reply is '*'

        If the reply is not correct, a second attempt is made by calling this function again, with 
            is_retry = True.

        Args:
            command (str): Command to be sent (without <CR>)
            timeout (float): override default timeout constants,
                for example for move operations.
                In seconds.
            is_retry (bool): set to True if this is the second attempt to send command                 

        Raises:
            PTHeadReplyTimeout: if head does not respond with full line within timeout
            PTHeadIncorrectReply: if the reply is not correct

        Returns:
            str: reply from head
        """

        self._empty_rcv_socket()
        self._send_raw(command)

        try:
            reply = self._get_reply(timeout)
        except PTHeadReplyTimeout as e:
            if is_retry:
                msg: str = f'{str(e)} for command "{command}"'
                self._log.error(msg)
                raise
            else:
                self.send_and_get(command=command, timeout=timeout, is_retry=True)

        return reply

    def _empty_rcv_socket(self) -> None:
        """Empty the receive buffer of the socket."""
        while True:
            read, __, __ = select.select([self.socket], [], [], 0)
            if len(read) == 0:
                return
            self.socket.recv(1)

    def _send_raw(self, command: str) -> None:
        """Send command over socket

        <CR> character is added at the end of command, and converted to bytes

        Args:
            command (str): command to be sent
        """
        self.socket.send((command + '\r').encode())

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

            time.sleep(0.01)
            try:
                if rx[0] == '\n' and rx[-2:] == '\r\n':
                    return rx[1:-2]
            except IndexError:
                # not enough data yet
                pass
            timeout -= 0.01
        raise PTHeadReplyTimeout(f'Received [{repr(rx)}] after {orig_timeout}s')

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
            time.sleep(0.01)
        return rx_buffer_readout
