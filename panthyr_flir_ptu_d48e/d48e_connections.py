#! /usr/bin/python3
# -*- coding: utf-8 -*-
# Authors: Dieter Vansteenwegen
# Institution: VLIZ (Vlaams Instituut voor de Zee)


__author__ = 'Dieter Vansteenwegen'
__email__ = 'dieter.vansteenwegen@vliz.be'
__project__ = 'Panthyr'
__project_link__ = 'https://waterhypernet.org/equipment/'

import contextlib
import logging
import select
import socket as sckt
import time

from .d48e_exceptions import PTHeadConnectionError, PTHeadReplyTimeout


def initialize_logger() -> logging.Logger:
    """Set up logger

    If the module is ran as a module, name logger accordingly as a sublogger.

    Returns:
        logging.Logger: logger instance
    """
    return logging.getLogger(__name__)


class PTHeadConnection:
    """Base class for connection to the head."""

    pass


class PTHeadIPConnection(PTHeadConnection):
    """IP communication for the flir PTU-D48.

    Provides functions to connect to the pan/tilt head over Ethernet
    """

    PTU_IP = '192.168.100.105'
    PTU_PORT = 4000
    TIMEOUT_SOCKET = 10

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
        self._test_connection()

    def _create_socket(self):
        """Create and configure a socket connection.

        Creates a TCP socket, configures it with TCP_NODELAY enabled
        (contrary to manual recommendation, but prevents network stack hangs),
        and sets socket timeout to 3 seconds.

        Returns:
            socket.socket: configured socket instance

        Raises:
            PTHeadConnectionError: if socket creation or configuration fails
        """
        try:
            sock = sckt.create_connection((self.ip, self.port), self.timeout)
        except (sckt.timeout, OSError):
            msg = f'Problem setting up socket for pan/tilt head ({self.ip}:{self.port})'
            raise PTHeadConnectionError(msg) from None

        # Configure socket
        sock.settimeout(3)
        sock.setsockopt(
            sckt.IPPROTO_TCP,
            sckt.TCP_NODELAY,
            1,
        )  # enable Nagle's algorithm (contrary to what manual recommends!)

        return sock

    def _test_connection(self) -> None:
        """Test that the head is reachable by creating and closing a socket.

        This is called during initialization to validate connectivity.
        The socket is closed after the test.

        Raises:
            PTHeadConnectionError: if the connection cannot be established
        """
        sock = self._create_socket()
        try:
            self._empty_rcv_socket(sock)
            self.log.debug('Connection test successful.')
        finally:
            sock.close()

    def send_and_get(self, command: str, timeout: float) -> str:
        """Send command and get reply over a fresh socket connection.

        For each call, a new socket is created, the command is sent, the reply
        is received within the timeout window, and then the socket is closed.

        Args:
            command (str): Command to be sent (without <CR>)
            timeout (float): timeout for receiving reply, in seconds.
                For move operations, this should be set to a higher value.

        Raises:
            PTHeadReplyTimeout: if head does not respond with full line within timeout
            PTHeadConnectionError: if socket creation or send fails
            PTHeadIncorrectReply: if the reply format is incorrect (checked by higher-level code)

        Returns:
            str: reply from head (without leading <LF> or trailing <CR><LF>)
        """
        sock = self._create_socket()
        try:
            self._empty_rcv_socket(sock)
            self._send_raw(sock, command)
            reply = self._get_reply(sock, timeout)
        except PTHeadReplyTimeout as e:
            self.log.warning(f'Timeout on head command "{command}": {e}')
            raise
        else:
            return reply
        finally:
            sock.close()

    def _empty_rcv_socket(self, sock) -> None:
        """Empty the receive buffer of the socket.

        Args:
            sock: socket object to empty
        """
        read_data = ''

        while True:
            read, _, error = select.select([sock], [], [sock], 0)
            if error:
                self.log.warning(f'Error returned from select for socket: [{error}]')
            if not read:
                break
            try:
                read_data = sock.recv(1024).decode()
            except TimeoutError:
                msg = 'Could not read from socket while emptying the rx buffer.'
                raise PTHeadConnectionError(msg) from None
            if len(read_data) <= 0:
                break
            if 'PAN-TILT' not in read_data:
                self.log.warning(f'Data left in buffer: [{read_data}]')

    def _send_raw(self, sock, command: str) -> None:
        """Send command over socket

        <CR> character is added at the end of command, and converted to bytes

        Args:
            sock: socket object to send through
            command (str): command to be sent
        """

        cmd_bytes = f'{command}\r'.encode()
        msg_len = len(cmd_bytes)

        bytes_sent = 0
        while bytes_sent < msg_len:
            _, _, error = select.select([sock], [], [], 0.5)
            if error:
                err_msg = f'Error checking socket: [{error}]. {sock}'
                raise PTHeadConnectionError(err_msg)
            try:
                sent = sock.send(cmd_bytes[bytes_sent:])
            except BrokenPipeError:
                err_msg = 'Broken pipe error.'
                raise PTHeadConnectionError(err_msg) from None
            if sent == 0:
                err_msg = f'Could not send {cmd_bytes[bytes_sent:]!r}, connection closed.'
                raise PTHeadConnectionError(err_msg)
            bytes_sent += sent
            if bytes_sent < msg_len:
                self.log.info(
                    f'Not everything was sent in one operation ({msg_len - bytes_sent} bytes '
                    f'remaining: {cmd_bytes[bytes_sent:]!r})',
                )

    def _get_reply(self, sock, timeout: float) -> str:
        """Get raw reply within timeout.

        Formatting:
            Replies start and end with <LF> (0xA, dec 10).
            Successfully executed command:
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
            sock: socket object to read from
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
            rx += self._rx_from_socket(sock)

            time.sleep(0.01)
            with contextlib.suppress(IndexError):
                if rx[0] == '\n' and rx[-2:] == '\r\n':
                    return rx[1:-2]
            timeout -= 0.01
        err_msg = f'Received [{repr(rx)}] after {orig_timeout}s'
        raise PTHeadReplyTimeout(err_msg)

    def _rx_from_socket(self, sock) -> str:
        """Try to read from socket.

        Args:
            sock: socket object to read from

        Returns:
            str: received characters. Empty string if none received.
        """
        rx_buffer_readout = ''
        rx_waiting, _, _ = select.select([sock], [], [], 0)
        while len(rx_waiting) > 0:
            rx_buffer_readout += sock.recv(1).decode()
            rx_waiting, _, _ = select.select([sock], [], [], 0)
            time.sleep(0.01)
        return rx_buffer_readout
