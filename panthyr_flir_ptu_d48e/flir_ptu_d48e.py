#! /usr/bin/python
# coding: utf-8
"""Socket control for the FLIR PTU-D48 pan/tilt head.

Project: Hypermaq
Dieter Vansteenwegen, VLIZ Belgium
Copyright?

Connection is a socket client to the head.
The basic ASCII query syntax is <command><delimiter>.
The basic ASCII command syntax is <command><parameter><delimiter>, where:
- <command> is the actual command
- <parameter> is an alphanumeric value
- <delimiter> Valid delimiter characters can be either [SPACE] or [ENTER].
- A successfully executed command returns * <CR><LF>
- A successfully executed query displays <N>* <QueryResult><CR><LF>
- A failed command displays ! <ErrorMessage><CR><LF>
When the unit is in auto stepping mode, the step size is changed dynamically. Units are processed as if eight step mode is selected.

Conventions:
Pan: rotation of the head in the same plan as its base
Tilt: rotation of the head towards or away from the horizontal plane of its base
pan_position: a specific angle of pan, referenced to the forward direction of its base (180 degrees from connector) (in steps, negative=CCW seen from top)
tilt_position: a specific angle of tilt, referenced to the base of the head (in steps, negative is front pointing down)
Heading: a specific angle of pan, referenced to the forward direction of its base (180 degrees from connector) (-180 to 180 degrees, negative=CCW seen from top)
Elevation: a specific angle of tilt, referenced to the base of the head (-90 to +30 degrees, negative is front pointing down)

TODO:
Adjust holding power, checking current consumption
"""


import logging
import socket
import select
from time import sleep
import sys  # only for line number in exception display

"""Define constants."""
ptu_port = 4000
ptu_ip = "192.168.100.105"
pan_constant_speed = 3000  # PS, max: ?, default: 1000
tilt_constant_speed = 3000  # TS max: ?, default: 1000
pan_max_speed = 4000
tilt_max_speed = 4000
pan_reset_speed = 4000
tilt_reset_speed = 4000


"""Define variables."""
all_clear = "False"  # set to True after succesful initialization and calibration procedure
pan_resolution = 0  # intial setting of 0 prohibits angular calculations
tilt_resolution = 0  # intial setting of 0 prohibits angular calculations
pan_position_north = 0  # offset between True North and pan position 0
tilt_position_level = 0  # offset between level and tilt position 0
tilt_low_limit = 1  # setting this to position 1 limits the head to > 0
tilt_high_limit = 1  # setting this to position 1 limits the head to < 0
pan_low_limit = 1  # setting this to position 1 limits the head to > 0
pan_high_limit = 1  # setting this to position 1 limits the head to < 0
true_north_offset = 0  # heading in degrees when pan is set to position 0. Values: 0 <= x < 360. 90 means head is pointing East.
level_offset = 0.00  # elevation in degrees when tilt is set to position 0. Values: +/-90. -90 means pointing down. (head coordinate system)

log = logging.getLogger("__main__.{}".format(__name__))

class pthead(object):
    """Pan/tilt head PTU-D48 from FLIR."""

    def __init__(self, reset=True):
        """Init."""

    def __empty_rcv_socket(self, socket):
        """Uses select.select to check if there's data in the receive buffer on [socket] and clears it."""
        while True:
            read, __, __ = select.select([socket],[],[], 0)
            if len(read)==0: 
                return True
            socket.recv(1)

    def setup_socket(self):
        global s
        try:
            s = socket.create_connection((ptu_ip, ptu_port),5)  # create the socket object
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1 ) # disable Nagle's algorithm
            self.__empty_rcv_socket(s)
        except Exception, e:
            message = "Problem setting up socket for pan/tilt head: {}".format(e)
            log.error(message, exc_info = True)
            return False
        
        return True

    def initialize(self, reset=True):
        """Initializes the head.

        Commands:
        ED = disable host command echo
        PCE = pan continuous enable, needs limits disables according to manual, but 
        RD = disable reset on boot
        FT = terse ASCII feedback mode
        CEC = enable encoder correction mode
        PHL = pan low hold power mode
        THL = tilt low hold power mode
        PML = pan low move power mode
        TML = tilt low move power mode
        PU = maximum pan speed
        TU = maximum tilt speed
        PS = desired pan speed
        TS = desired tilt speed
        RPS = reset pan speed
        RTS = reset tilt speed
        PA1500 = pan acceleration
        TA1500 = tilt acceleration
        WTA = tilt auto step  (!!! needs axis reset after this command)
        WPA = pan auto step  (!!! needs axis reset after this command)
        RT = reset tilt axis
        RP =  reset pan axis
        PNU-27067 = pan user minimum limit -174 degrees
        PXU27067 = pan user maximum limit 174 degrees
        TNU-27999 = tilt user minimum limit -90 degrees
        TXU9333 = tilt user maximum limit 30 degrees
        LU = enforce user limits

        Returns "OK" if successful, error message if not.
        """
        global all_clear
        global s

        initialization_commands = ["FT", "PHL", "THR", "PML", "TMH", "CEC", "PA2000", "TA2000",
        "PU{}".format(pan_max_speed), 
        "TU{}".format(tilt_max_speed), 
        "PS{}".format(pan_constant_speed), 
        "TS{}".format(tilt_constant_speed),
        "RPS{}".format(pan_reset_speed),
        "RTS{}".format(tilt_reset_speed),]
        axis_reset_commands = ["RT", "RP"]  # these will need a longer timeout

        if reset:
            initialization_commands.extend(["WTA", "WPA", "RT", "RP", "RD"])  # add reset and calibration commands to be executed
        initialization_commands.extend(["TNU-27999", "TXU9333", "PNU-27067", "PXU27067", "LU"])  # limit settings need to be done after axis resets have been done, so put these at the end of the list

        try:
            s.send("ED\r")  # disable host command echo
            sleep(0.6)
            for i in initialization_commands:
                self.__empty_rcv_socket(s)
                s.send(i + "\r")  # send the command
                if i in axis_reset_commands:  # axis reset/calib commands will trigger !t or !p errors and need more time
                    reply = self.__await_reply(25, True)
                else:
                    reply = self.__await_reply(3)

                if reply <> "OK": raise Exception("Problem while executing command {}".format(i))
                    
            if not self.__calculate_resolution():  # try to calculate the ratio angle/step
                raise Exception("Cannot calculate resolution")
            if not self.__get_limits():  # try to get movement limits
                raise Exception("Cannot get limits")

            all_clear = True
            return "OK"

        except Exception, e:
            all_clear = False  # no further movement unless a succesful reset has been performed
            log.error("{}".format(e), exc_info= True)
            return "ERROR (INITIALIZE): {}".format(e)

    def __await_reply(self, amount=3, expect_limit_error=False):
        r"""Waits for a fully formed reply.

        Checks the receive buffer for amount seconds, waiting for line starting with "\n*" and ending with "\r\n"
        If reply is more than 5 characters, the reply (minus leading space) is returned.
        If expect_limit_error is True (used when doing axis reset commands), expected line starts with "\n!" and ends with "\r\n"
        Returns OK if response is as expected, or received response if not.
        """
        global s
        socket_rx_buffer_str = ""
        amount = amount * 10  # amount is in seconds, but we're going to work in 0.1 second steps

        while amount:  # if timeout has not been passed
            read, __, __ = select.select([s],[],[], 0)
            while len(read) > 0:
                socket_rx_buffer_str += s.recv(1)  # read the buffer, character by character
                if not expect_limit_error and socket_rx_buffer_str[:2] == "\n*" and socket_rx_buffer_str[-2:] == "\r\n":
                    # for non axis-reset/calib commands, reply should have these start and endings
                    if len(socket_rx_buffer_str) < 5:  # if there's no reply (to a query)
                        return "OK"
                    else:
                        return socket_rx_buffer_str[3: -2]  # return the reply

                if expect_limit_error and socket_rx_buffer_str[:2] == "\n!" and socket_rx_buffer_str[-2:] == "\r\n":
                    # for axis-reset/calib commands, these start/endings are expected
                    return "OK"
                read, __, __ = select.select([s],[],[], 0)
                
            amount -= 1
            sleep(0.1)

        message = "received unexpected answer: {}".format(socket_rx_buffer_str[3: -2])
        log.error(message)
        return ("ERROR (AWAIT_REPLY): " + message)

    def send_command(self, command, timeout=3):
        """Sends command with argument. Waits for response. Returns True/False if success/fail."""
        global s

        self.__empty_rcv_socket(s)
        s.send(command + "\r")  # send the command
        sleep(0.1)  # needed pause for reply
        reply = self.__await_reply(timeout)  # for default commands (non-movement/reset), a timeout of 3 seconds is presumed
        if reply == "OK":  # no valid response received
            return "OK"
        else:
            log.error("No acknowledgment received for command '{}'".format(command))
            return "ERROR (SEND_COMMAND) with send_command: {}".format(reply)

    def send_query(self, query, timeout=3):
        """Sends query. Waits for response. Returns reply if any."""
        self.__empty_rcv_socket(s)
        s.send(query + "\r")
        sleep(0.1)  # needed pause for reply
        reply = self.__await_reply(timeout)
        if reply[:5] == "ERROR":
            log.error("Unexpected anwer received for query '{}': {}".format(query, reply)) # debug
            return "ERROR (SEND_QUERY) Unexpected anwer received for query '{}': {}".format(query, reply)
        else:
            return reply

    def __calculate_resolution(self):
        """Calculates the resolution of steps (in degrees per position).
        PR and TR queries return the resolution in arc degrees per position. Divide by 3600 to get degrees per position.
        """
        global pan_resolution
        global tilt_resolution
        global all_clear

        try:
            pan_resolution_arc = float(self.send_query("PR", 2))
            tilt_resolution_arc = float(self.send_query("TR", 2))
            pan_resolution = pan_resolution_arc / 3600  # conversion from degrees arc-seconds to degrees
            tilt_resolution = tilt_resolution_arc / 3600  # conversion from degrees arc-seconds to degrees
            return True
        except:
            all_clear = False
            log.error("Problems during calculate_resolution")
            return "ERROR (CALCULATE_RESOLUTION): Problems during calculate_resolution"

    def __get_limits(self):
        """Gets the pan/tilt limits, in steps.
        Returns True if successful, error message if failed
        """
        global tilt_low_limit
        global tilt_high_limit
        global pan_low_limit
        global pan_high_limit
        global all_clear

        try:
            # get limits from device
            pan_low_limit = int(self.send_query("PN", 2))
            pan_high_limit = int(self.send_query("PX", 2))
            tilt_low_limit = int(self.send_query("TN", 2))
            tilt_high_limit = int(self.send_query("TX", 2))
            return True
        except Exception, e:
            all_clear = False
            message = "Problems while getting movement limits: {}".format(e)
            log.error(message)
            return "ERROR " + message

    def show_parameters(self):
        """Returns some parameters and info in a dict.
        Items in returned dict: ["voltage"], ["temp_head"}], ["temp_pan"], ["temp_tilt"]
        """
        return_dict = dict()
        voltage_and_temps = (self.send_query("O")).split(",")

        return_dict["voltage"] = float(voltage_and_temps[0])
        return_dict["temp_head"] =(float(voltage_and_temps[1])-32) /1.8  # convert from fahrenheit to degrees C
        return_dict["temp_pan"] = (float(voltage_and_temps[2])-32) /1.8
        return_dict["temp_tilt"] = (float(voltage_and_temps[3])-32) /1.8

        return return_dict

    def pan_degrees(self, degrees):
        """Pan the head [degrees] relative to current position.
        Degrees can be int or float. Timeout passed for the command is 32 seconds.
        """
        global all_clear

        try:
            if not all_clear: 
                raise Exception("Not all clear, perform reset!")

            pan_movement = int(degrees / pan_resolution)  # calculate needed steps to pan "degrees"
            current_pan_position = int(self.get_position()["pan_pos"])  # query position before movement
            target_position = current_pan_position + pan_movement

            if pan_low_limit <= target_position <= pan_high_limit:  # end position is within movement limits
                reply = self.send_command("PO" + str(int(pan_movement)), 32)  # execute pan
            else: 
                raise Exception("End point not within movement limits")

            if not reply == "OK": 
                raise Exception("Invalid reply from pan command: {}".format(reply)) # something has gone wrong

            self.send_command("A", 32)  # wait until movement has completed

            position_offset = int(self.get_position()["pan_pos"]) - target_position  # check end position compared to expected end position

            if position_offset <> 0: 
                raise Exception("Offset during movement: {}".format(position_offset)) # there's an offset

            return "OK"

        except Exception, e:
            message = "{}".format(e)
            log.error(message)
            return "ERROR {}".format(message)

    def tilt_degrees(self, degrees):
        """Pan the head [degrees] relative to current position.

        Degrees can be int or float. Timeout passed for the command is 25 seconds.
        """
        global all_clear
        try:
            if not all_clear:
                raise Exception("Not all clear, perform reset!")

            tilt_movement = int(degrees / tilt_resolution)  # calculate needed steps to tilt "degrees"
            current_tilt_position = int(self.get_position()["tilt_pos"])  # query position before movement
            target_position = current_tilt_position + tilt_movement

            if tilt_low_limit <= target_position <= tilt_high_limit:  # end position is within movement limits
                reply = self.send_command("TO" + str(tilt_movement), 20)  # execute tilt
            else:
               raise Exception("End point not within movement limits")

            if reply <> "OK":  # something has gone wrong
                raise Exception("Invalid reply from tilt command: {}".format(reply))

            self.send_command("A", 20)  # wait until movement has completed

            position_offset = int(self.get_position()["tilt_pos"]) - target_position  # check end position compared to expected end position

            if not position_offset == 0:  # there's an offset
                raise Exception("Offset during movement: {}".format(position_offset))
            else:
                return "OK"

        except Exception, e:
            message = "{}".format(e)
            log.error(message)
            return "ERROR {}".format(message)
    
    def move_position(self, heading="", elevation=""):
        """Moves the head to heading and elevation.

        Heading should be 0 <= heading < 360
        Elevation should be -30 <= elevation <= 90
        If one of (heading, elevation) is not defined, that axis isn't moved.
        """

        commands_list= []
        try:        
            if not all_clear: raise Exception("Not all clear, perform reset")
        
            ## first check heading and elevation
            if heading <> "":  # heading was provided
                if not 0 <= float(heading) < 360: 
                    raise Exception("{} is an invalid heading (should be  0 <= x < 360, North referenced)".format(heading))

                if 180 <= float(heading) <= 360:  # first convert 0 - 360 degrees to +/- 180 degrees (and check if reasonable heading was given)
                    heading = heading - 360
                pan_target_position = int(float(heading) / pan_resolution)  # convert to head position

                if not pan_low_limit <= pan_target_position <= pan_high_limit:
                    message = "target heading {:06.2f} (position {}) is out of bounds".format(heading, pan_target_position)
                    logging.warning(message)
                    return "ERROR " + message
                commands_list.append("PP{}".format(pan_target_position))

            if elevation <> "":
                if not -90 <= float(elevation) <= 30:  # was a reasonable angle passed?
                    raise Exception("{} is an invalid elevation (should be -90 <= x <= 30)".format(elevation))          
                tilt_target_position = int(float(elevation) / tilt_resolution)  # convert to head position

                if not tilt_low_limit <= tilt_target_position <= tilt_high_limit:  # end position is within movement limits
                    # raise Exception("target elevation {:05.2f} (position {}) is out of bounds".format(elevation, tilt_target_position)) # end position is outside of movement limits
                    message = "target elevation {:05.2f} (position {}) is out of bounds".format(elevation, tilt_target_position)
                    log.warning(message)
                    return "ERROR " + message
                commands_list.append("TP{}".format(tilt_target_position))

            # at this point, tilt_target_position and pan_target_position have been determined and checked.
            commands_list.append("A")  # last command is to wait until the move has finished

            for i in commands_list:
                reply = self.send_command(i, 32)
                if reply <> "OK": raise Exception("Invalid response from command {}: {}".format(i, reply))
            
            end_position = self.get_position()

            error_message = []
            if heading <> "":
                if end_position["pan_pos"] <> pan_target_position:
                    error_message.append("pan_pos is {}, should be {}".format(end_position["pan_pos"], pan_target_position))
            if elevation <> "":
                if end_position["tilt_pos"] <> tilt_target_position:
                    error_message.append("tilt_pos is {}, should be {}".format(end_position["tilt_pos"], tilt_target_position))
            if len(error_message) > 0:
                raise Exception(",".join(error_message))
            
            return "OK"

        except Exception, e:
            message = "{}".format(e)
            log.error(message)
            return "ERROR " + message
        

    def park(self):
        """Pan to zero and tilts to its lowest limit to guard the sensors from fouling."""
        try:
            park_commands = ("PP0", "TP{}".format(tilt_low_limit), "A")
            
            for i in park_commands:
                reply = self.send_command(i, 30)  # Pan to zero and tilt to lower limits
                if reply <> "OK": raise Exception("invalid reply from command {}: {}".format(i, reply))
                
            pos = self.get_position()
            if not ((int(pos["tilt_pos"]) == tilt_low_limit) and (int(pos["pan_pos"]) == 0)):  # check end position compared to expected end position
                raise Exception("not at correct position after parking, but at {0[tilt_pos]} tilt, {0[pan_pos]} pan".format(pos))
            
        except Exception, e:
            log.error("{}".format(e) )  # debug
            return "ERROR (PARK): {}".format(e)

        return "OK"

    def get_position(self):
        """Returns the position (heading/elevation) in degrees.

        Returns dict with:
        - items "heading" (in degrees), "pan_pos" (position in steps), "elevation" (in degrees) and tilt_pos (position in steps).
        All of these are according to the head "0", +/- half a revolution, so heading is -180 to +180 degrees.
        - items "heading_corrected" and "elevation_corrected"
        """
        pan_position = int(self.send_query("PP"))
        tilt_position = int(self.send_query("TP"))
        heading = (pan_position * pan_resolution) % 360
        elevation = tilt_position * tilt_resolution

        pos_dict = dict()
        pos_dict["pan_pos"] = pan_position
        pos_dict["heading"] = float("{:06.2f}".format(heading))
        pos_dict["tilt_pos"] = tilt_position
        pos_dict["elevation"] = float("{:+06.2f}".format(elevation))
        return pos_dict



"""Main functions."""


"""Configuration settings."""


"""Main loop."""

if __name__ == "__main__":
    head = pthead()
    head.setup_socket()

    if head.initialize() == "OK":
        print("\n" + ("#" * 30))
        print("Pan/tilt head initialization successful\n")
        print("Pan/tilt resolution: {:.8f} / {:.8f} degrees per step".format(pan_resolution, tilt_resolution))
        print("Pan low/high position limits (degrees): {: 6} ({:06.2f}) / {: 6} ({:06.2f})".format(pan_low_limit, (pan_low_limit * pan_resolution), pan_high_limit, (pan_high_limit * pan_resolution)))
        print("Tilt low/high position limits (degrees): {: 6} ({:06.2f}) / {: 6} ({:06.2f})".format(tilt_low_limit, (tilt_low_limit * tilt_resolution), tilt_high_limit, (tilt_high_limit * tilt_resolution)))
        print("#" * 30)

    else:
        print("Initialization was not successful")