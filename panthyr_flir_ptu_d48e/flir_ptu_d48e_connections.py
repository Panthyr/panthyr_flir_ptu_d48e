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
# from typing import Union


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
    import select
    import socket as sckt

    PTU_IP = '192.168.100.190'
    PTU_PORT = 4000
    DEFAULT_TIMEOUT = 0.5

    def __init__(self, ip: str = PTU_IP, port: int = PTU_PORT):
        """__init__ for class

        Args:
            ip (str): IP address of p/t head
            port (int): socket number
        """
        self.ip = ip
        self.port = port
        self.log = initialize_logger()

    def connect(self) -> None:
        try:
            self.socket = self.sckt.create_connection((self.ip, self.port), 5)
        except OSError as e:
            msg = f'Problem setting up socket for pan/tilt head ({self.ip}:{self.port}): {e}'
            print(msg)
            self.log.error(msg, exc_info=True)
            raise
        else:
            self.socket.setsockopt(self.sckt.IPPROTO_TCP, self.sckt.TCP_NODELAY,
                                   1)  # disable Nagle's algorithm
            self._empty_rcv_socket()

    def _empty_rcv_socket(self) -> None:
        while True:
            read, __, __ = self.select.select([self.socket], [], [], 0)
            if len(read) == 0:
                return
            self.socket.recv(1)

    def send_cmd(self,
                 command: str,
                 expect_limit_err: bool = False,
                 timeout: float = DEFAULT_TIMEOUT) -> None:
        """[summary]

        [extended_summary]

        Args:
            command (str): Command to be sent, without CR
            expect_limit_err (bool, optional): if limit errors are allowed,
                such as during axis reset.
                Defaults to False.
            timeout (float, optional): define different expected duration than DEFAULT_TIMEOUT,
                for example for move operations.
                Defaults to DEFAULT_TIMEOUT.
        """
        # TODO: if command in ['RT', 'RP']
        self._empty_rcv_socket()
        self.socket.send(command + '\r')
        time.sleep(0.1)
        reply = self._get_reply(expect_limit_err, timeout)
