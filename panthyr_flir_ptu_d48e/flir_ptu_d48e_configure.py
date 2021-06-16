# coding: utf-8
"""Socket control for the FLIR PTU-D48 pan/tilt head.

Project: Hypermaq
Dieter Vansteenwegen, VLIZ Belgium
Copyright?

Version for Python 3
"""
import socket
import select
import getopt
from time import sleep
import sys  # only for line number in exception display

"""Define constants."""

"""Define variables."""

class pthead(object):
    """Pan/tilt head PTU-D48 from FLIR."""

    def __init__(self, ip = '192.168.100.105'):
        """Init."""
        self.ip = ip

    def setup_socket(self):
        print('Opening socket...')
        try:
            self.s = socket.create_connection((self.ip, 4000),5)  # create the socket object
            self.s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1 ) # disable Nagle's algorithm
            self.__empty_rcv_socket(self.s)
        except Exception as e:
            message = "Problem setting up socket for pan/tilt head with ip {}: {}".format(self.ip, e)
            print(message)
            return "ERROR (SETUP_SOCKET) " + message
        return True

    def __empty_rcv_socket(self, socket):
        """Uses select.select to check if there's data in the receive buffer on [socket] and clears it."""
        while True:
            sleep(0.01)
            read, __, __ = select.select([socket],[],[], 0)
            if len(read)==0: 
                return True
            socket.recv(1)


    def configure(self, reset=True):
        """Configures the head.

        Commands:
        FD  # factory defaults
        LU  # User limits
        PCE  # continuous pan enable (fails if slipring not installed)
        R  # reset
        WTA  # tilt auto step mode
        WPA  # pan auto step mode
        CEC  # encoder correction
        TB0  # tilt base speed
        PB0  # pan base speed
        PA2000  # pan acceleration
        TA2000  # tilt acceleration
        TU4000  # tilt max speed
        PU4000  # pan max speed
        FT  # Terse feedback
        ED  # disable host command echo
        PS4000  # pan speed
        TS4000 # tilt speed
        RPS4000  # (reset pan speed, 4000)
        RTS4000  # (Reset tilt speed, 4000)
        RT  # reset tilt
        RP  # reset pan
        RD  # disable reset on power up
        PNU-27067  # pan user minimum limit -174 degrees
        PXU27067  # pan user maximum limit 174 degrees
        TNU-27999  # tilt user minimum limit -90 degrees
        TXU9333  # tils user maximum limit 30 degrees
        # NMS  # static IP mode
        # NI192.168.100.105  # set IP
        DS  # default save

        Returns TRUE if successful, error message if not.
        """

        config_commands = [
        # 'LU',  # user limits (not needed if continuous rotation)
        'PCE',  # continuous pan enable (fails if slipring not installed)
        'R',  # reset
        'WTA',  # tilt auto step mode
        'WPA',  # pan auto step mode
        'CEC',  # encoder correction
        'TB0',  # tilt base speed
        'PB0',  # pan base speed
        'PA2000',  # pan acceleration
        'TA2000',  # tilt acceleration
        'TU4000',   # tilt max speed
        'PU4000',  # pan max speed
        'PS4000',  # pan speed
        'TS4000', # tilt speed
        'RPS4000',  # (reset pan speed, 4000)
        'RTS4000',  # (Reset tilt speed, 4000)
        'RT',  # reset tilt
        'RP',  # reset pan
        'RD',  # disable reset on power up
        'PNU-27067',  # pan user minimum limit -174 degrees
        'PXU27067',  # pan user maximum limit 174 degrees
        'TNU-27999',  # tilt user minimum limit -90 degrees
        'TXU9333',  # tils user maximum limit 30 degrees
        'DS',  # default save
        # 'NI192.168.100.105',  # set IP
        # 'NMS',  # static IP mode
        # # 'DS',  # default save
        ]

        try:
            sleep(0.6)
            self.s.send('DF'.encode() + "\r".encode())
            timer = 20
            print('\nReturning head to factory defaults.')
            while timer >= 0:
                print('\rWaiting for reset... [{:02}]'.format(timer), end = '')
                timer -= 1
                sleep(1)
            print('\n')
            self.s.close()
            self.setup_socket()
            self.s.send('FT'.encode() + "\r".encode())
            self.s.send('ED'.encode() + "\r".encode())
            for i in config_commands:
                self.__empty_rcv_socket(self.s)
                print('\r' + ' ' * 30, end='')
                print('\rSending command {}'.format(i), end = '')
                self.s.send(i.encode() + "\r".encode())  # send the command
                if i in ['R','RT', 'RP', 'FD']:
                    reply = self.__await_reply(25,expect_limit_error=True)
                else:
                    reply = self.__await_reply(3)
                if reply != "OK": raise Exception("Problem while executing command {}: {}".format(i, repr(reply)))
            print('\r\n')
            return "OK"

        except Exception as e:
            print('\r\n')
            print(e)
            return "ERROR (INITIALIZE): {}".format(e)

    def __await_reply(self, amount=4, expect_limit_error=False):
        r"""Waits for a fully formed reply.

        Checks the receive buffer for amount seconds, waiting for line starting with "\n*" and ending with "\r\n"
        If reply is more than 5 characters, the reply (minus leading space) is returned.
        If expect_limit_error is True (used when doing axis reset commands), expected line starts with "\n!" and ends with "\r\n"
        Returns OK if response is as expected, or received response if not.
        """
        socket_rx_buffer_str = ""
        amount = amount * 10  # amount is in seconds, but we're going to work in 0.1 second steps

        while amount:  # if timeout has not been passed
            read, __, __ = select.select([self.s],[],[], 0)
            while len(read) > 0:
                socket_rx_buffer_str += self.s.recv(1).decode()  # read the buffer, character by character
                if not expect_limit_error and socket_rx_buffer_str[:2] == "\n*" and socket_rx_buffer_str[-2:] == "\r\n":
                    # for non axis-reset/calib commands, reply should have these start and endings
                    if len(socket_rx_buffer_str) < 5:  # if there's no reply (to a query)
                        return "OK"
                    else:
                        return socket_rx_buffer_str[3: -2]  # return the reply

                if expect_limit_error and socket_rx_buffer_str[:2] == "\n!" and socket_rx_buffer_str[-2:] == "\r\n":
                    # for axis-reset/calib commands, these start/endings are expected
                    return "OK"
                read, __, __ = select.select([self.s],[],[], 0)
            amount -= 1
            sleep(0.1)

        message = "received unexpected answer: {}".format(socket_rx_buffer_str[3: -2])
        return ("ERROR (AWAIT_REPLY): " + message)

    def send_command(self, command, timeout=3):
        """Sends command with argument. Waits for response. Returns True/False if success/fail."""
        self.__empty_rcv_socket(self.s)
        import pdb
        pdb.set_trace()
        self.s.send(command.encode() + "\r".encode())  # send the command
        sleep(0.1)  # needed pause for reply
        reply = self.__await_reply(timeout)  # for default commands (non-movement/reset), a timeout of 3 seconds is presumed
        if reply == "OK":  # no valid response received
            return "OK"
        else:
            return "ERROR (SEND_COMMAND) with send_command: {}".format(reply)


"""Main loop."""

if __name__ == "__main__":
    opts, arg = getopt.getopt(sys.argv[1:], '',[])  # returns a list with each option,argument combination
    if len(arg) != 1:  # no valid arguments have been provided
        print('Please provide current IP address of head as option (example: "python ./flir_configure.py 192.168.100.198")')
        exit()
    p = pthead(arg[0])
    p.setup_socket()
    print('\r\nConfiguring head with ip {}'.format(arg[0]))
    reply = p.configure()
    if reply == 'OK':
        print('Configuration succesful. Please open a browser to {} and: \
            -> change the IP mode to static \
            -> set the IP to 192.168.100.105 \
            -> save this as default settings (click "Set" then "Save")\
            -> restart the head \
            -> open the head webfront again at 192.168.100.105 to verify the changes.'.format(arg[0]))
    else:
        print('Problem during configuration: {}'.format(reply))
