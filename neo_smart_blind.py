import logging
import socket
import time

import requests

from .const import (
    CMD_UP,
    CMD_UP2,
    CMD_DOWN,
    CMD_DOWN2,
    CMD_STOP,
    CMD_FAV,
    CMD_FAV_1,
    CMD_FAV_2,
    LEGACY_POSITIONING,
    EXPLICIT_POSITIONING,
    IMPLICIT_POSITIONING,
    ACTION_STOPPED,
    ACTION_OPENING,
    ACTION_CLOSING
)

_LOGGER = logging.getLogger(__name__)
LOGGER = logging.getLogger()

class NeoSmartBlind:
    def __init__(self, host, the_id, device, close_time, port, protocol, rail, percent_support, motor_code):
        self._host = host
        self._port = port
        self._protocol = protocol
        self._the_id = the_id
        self._device = device
        self._close_time = int(close_time)
        self._rail = rail
        self._percent_support = percent_support
        self._current_position = 50
        self._motor_code = motor_code
        self._current_action = ACTION_STOPPED


    """Adjust the blind based on the pos value send"""
    def adjust_blind(self, pos):

        """Legacy support for using position to set favorites"""
        if self._percent_support == LEGACY_POSITIONING:
            if pos == 50 or pos == 51:
                self.set_fav_position(pos)
            return

        """Always allow full open / close commands to get through"""

        if pos > 98:
            """
            Unable to send 100 to the API so assume anything greater then 98 is just an open command.
            Use the same logic irrespective of mode for consistency.            
            """
            return self.open_cover()
        if pos < 2:
            """Assume anything greater less than 2 is just a close command"""
            return self.close_cover()

        """Check for any change in position, only act if it has changed"""
        delta = pos - self._current_position

        if delta == 0:
            return

        """Logic for blinds that support percent positioning"""
        if self._percent_support == EXPLICIT_POSITIONING:
            """NeoBlinds works off of percent closed, but HA works off of percent open, so need to invert the percentage"""
            closed_pos = 100 - pos
            padded_position = f'{closed_pos:02}'
            LOGGER.info('Sending ' + padded_position)
            self.send_command(padded_position)
            self._current_position = pos
            return

        """
        Logic for blinds that do not support percent positioning
        0 = closed
        100 = open
        i.e.
        positive delta = up
        negative delta = down
        """
        wait = 0

        if delta > 0:
            self.up_command()
            self._current_action = ACTION_OPENING
            wait = (delta * self._close_time)/100

        if delta < 0:
            self.down_command()
            self._current_action = ACTION_CLOSING
            wait = (delta * self._close_time)/-100

        if wait > 0:
            self._current_position = pos
            def stop_it():
                LOGGER.info('Sleeping for {}, then stopping'.format(wait))
                time.sleep(wait)
                self.stop_cover()

            return stop_it
        
        return

    """Open blinds fully"""
    def open_cover(self):
        self.up_command()
        wait = ((100 - self._current_position) * self._close_time)/100
        self._current_position = 100
        def wait_for_open():
            LOGGER.info('Sleeping for {} to allow for open'.format(wait))
            time.sleep(wait)
            self._current_action = ACTION_STOPPED

        return wait_for_open

    """Close blinds fully"""
    def close_cover(self):
        self.down_command()
        wait = ((100 - self._current_position) * self._close_time)/100
        self._current_position = 0
        def wait_for_close():
            LOGGER.info('Sleeping for {} to allow for close'.format(wait))
            time.sleep(wait)
            self._current_action = ACTION_STOPPED

        return wait_for_close

    def stop_cover(self):
        self.send_command(CMD_STOP)
        self._current_action = ACTION_STOPPED

    """Send down command with rail support"""
    def down_command(self):
        if self._rail == 1:
            self._current_action = ACTION_CLOSING
            self.send_command(CMD_DOWN)
        elif self._rail == 2:
            self._current_action = ACTION_CLOSING
            self.send_command(CMD_DOWN2)
        return

    """Send up command with rail support"""
    def up_command(self):
        if self._rail == 1:
            self._current_action = ACTION_OPENING
            self.send_command(CMD_UP)
        elif self._rail == 2:
            self._current_action = ACTION_OPENING
            self.send_command(CMD_UP2)
        return

    def adjust_blind_tilt(self, pos):
        LOGGER.info('Tilt position set to: ' + str(pos))
        self.set_fav_position(pos)
        return

    def set_fav_position(self, pos):
        LOGGER.info('Setting fav: ' + str(pos))
        if pos <= 50:
            self.send_command(CMD_FAV)
            self._current_position = 50
            return
        if pos >= 51:
            self.send_command(CMD_FAV_2)
            self._current_position = 51
            return
        return

    def get_position(self):
        LOGGER.info('Current Position is: ' + str(self._current_position))
        return self._current_position

    def is_closed(self):
        return self._current_position == 0

    def is_closing(self):
        return self._current_action == ACTION_CLOSING

    def is_opening(self):
        return self._current_action == ACTION_OPENING

    def send_command(self, command):
        """Command handler to send based on correct protocol"""
        if str(self._protocol).lower() == "http":
            self.send_command_http(command)

        elif str(self._protocol).lower() == "tcp":
            self.send_command_tcp(command)

        else:
            LOGGER.error("NeoSmartBlinds, Unknown protocol: {}, please use: http or tcp".format(self._protocol))

    def send_command_tcp(self, code):
        """Command sender for TCP"""

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
            mc = ""
            if self._motor_code:
                mc = "!{}".format(self._motor_code)

            command = self._device + "-" + code + mc + '\r\n'
            LOGGER.info("NeoSmartBlinds, Sending command: {}".format(command))
            s.connect((self._host, self._port))
            while True:
                s.send(command)
        except socket.error:
            LOGGER.exception(socket.error.strerror)
            return

    def send_command_http(self, command):
        """Command sender for HTTP"""
        url = "http://{}:{}/neo/v1/transmit".format(self._host, self._port)

        mc = ""
        if self._motor_code:
            mc = "!{}".format(self._motor_code)


        params = {'id': self._the_id, 'command': self._device + "-" + command + mc, 'hash': str(time.time()).strip(".")[-7:]}

        r = requests.get(url=url, params=params)

        LOGGER.info("Sent: {}".format(r.url))
        LOGGER.info("Neo Hub Responded with - {}".format(r.text))

        """Check for error code and log"""
        if r.status_code != 200:
            LOGGER.error("Status Code - {}".format(r.status_code))
