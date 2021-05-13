import logging
import socket
import time
from datetime import datetime

import requests

from .const import (
    CMD_UP,
    CMD_UP2,
    CMD_DOWN,
    CMD_DOWN2,
    CMD_STOP,
    CMD_FAV,
    CMD_FAV_1,
    CMD_FAV_2
)

_LOGGER = logging.getLogger(__name__)
LOGGER = logging.getLogger()

class NeoSmartBlind:
    def __init__(self, host, the_id, device, port, protocol, rail, motor_code):
        self._host = host
        self._port = port
        self._protocol = protocol
        self._the_id = the_id
        self._device = device
        self._rail = rail
        self._motor_code = motor_code

    def set_position_by_percent(self, pos):
        """NeoBlinds works off of percent closed, but HA works off of percent open, so need to invert the percentage"""
        closed_pos = 100 - pos
        padded_position = f'{closed_pos:02}'
        LOGGER.info('Sending ' + padded_position)
        self.send_command(padded_position)
        return

    def stop_command(self):
        self.send_command(CMD_STOP)

    def open_cover_tilt(self, **kwargs):
        if self._rail == 1:
            self.send_command(CMD_MICRO_UP)
        elif self._rail == 2:
            self.send_command(CMD_MICRO_UP2)
        """Open the cover tilt."""
        
    def close_cover_tilt(self, **kwargs):
        if self._rail == 1:
            self.send_command(CMD_MICRO_DOWN)
        elif self._rail == 2:
            self.send_command(CMD_MICRO_DOWN2)
        """Close the cover tilt."""

    """Send down command with rail support"""
    def down_command(self):
        if self._rail == 1:
            self.send_command(CMD_DOWN)
        elif self._rail == 2:
            self.send_command(CMD_DOWN2)
        return

    """Send up command with rail support"""
    def up_command(self):
        if self._rail == 1:
            self.send_command(CMD_UP)
        elif self._rail == 2:
            self.send_command(CMD_UP2)
        return

    def set_fav_position(self, pos):
        LOGGER.info('Setting fav: ' + str(pos))
        if pos <= 50:
            self.send_command(CMD_FAV)
            return 50
        if pos >= 51:
            self.send_command(CMD_FAV_2)
            return 51
        return

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

        hash_string = str(datetime.now().microsecond).zfill(6)
        # hash_string = pre_strip[-7:].strip(".")

        params = {'id': self._the_id, 'command': self._device + "-" + command + mc, 'hash': hash_string}

        r = requests.get(url=url, params=params)

        LOGGER.info("Sent: {}".format(r.url))
        LOGGER.info("Neo Hub Responded with - {}".format(r.text))

        """Check for error code and log"""
        if r.status_code != 200:
            LOGGER.error("Status Code - {}".format(r.status_code))


# 2021-05-13 10:20:38 INFO (SyncWorker_4) [root] Sent: http://<ip>:8838/neo/v1/transmit?id=440036000447393032323330&command=146.215-08-up&hash=.812864
# 2021-05-13 10:20:38 INFO (SyncWorker_4) [root] Neo Hub Responded with - 

# 2021-05-13 10:30:54 INFO (SyncWorker_6) [root] Sent: http://<ip>:8838/neo/v1/transmit?id=440036000447393032323330&command=146.215-08-sp&hash=4.65143 (from 1620901854.65143)
# 2021-05-13 10:30:54 INFO (SyncWorker_6) [root] Neo Hub Responded with - 