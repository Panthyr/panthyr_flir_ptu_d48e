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
    DEFAULT_TIMEOUT = 0.4

    def __init__(self, ip: str, port: int = 4000):
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

    def send_cmd(self, command: str, expect_limit_err: bool = False) -> None:
        # TODO: if command in ['RT', 'RP']
        self.socket.send(command)
