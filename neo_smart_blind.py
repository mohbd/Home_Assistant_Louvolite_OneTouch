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
    CMD_FAV_1,
    CMD_FAV_2,
)

_LOGGER = logging.getLogger(__name__)
LOGGER = logging.getLogger(__name__)


class NeoSmartBlind:
    def __init__(self, host, the_id, device, close_time, port, protocol, rail):
        self._host = host
        self._port = port
        self._protocol = protocol
        self._the_id = the_id
        self._device = device
        self._close_time = int(close_time)
        self._rail = rail
        
    def adjust_blind(self, pos):
        """Adjust the blind based on the pos value send"""
        if pos == 50:
            self.send_command(CMD_FAV_1)
            return
        if pos == 51:
            self.send_command(CMD_FAV_2)
            return
        if pos >= 52:
            self.send_command(CMD_UP)
            if self._rail == 1:
                self.send_command(CMD_UP)
            elif self._rail == 2:
                self.send_command(CMD_UP2)
            wait1 = (pos - 50)*2
            wait = (wait1*self._close_time)/100
            LOGGER.warning(wait)
            time.sleep(wait)
            self.send_command(CMD_STOP)
            return            
        if pos <= 49:
            if self._rail == 1:
                self.send_command(CMD_DOWN)
            elif self._rail == 2:
                self.send_command(CMD_DOWN2)
            wait1 = (50 - pos)*2
            wait = (wait1*self._close_time)/100
            LOGGER.warning(wait)
            time.sleep(wait)
            self.send_command(CMD_STOP)
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

            command = self._device + "-" + code + '\r\n'
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

        params = {'id': self._the_id, 'command': self._device + "-" + command, 'hash': str(time.time()).strip(".")[-7:]}

        r = requests.get(url=url, params=params)
        LOGGER.info("Sent: {}".format(r.url))
        LOGGER.info("Neo Hub Responded with - {}".format(r.text))
