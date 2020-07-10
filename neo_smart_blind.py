import logging
import socket
import time

import requests

from .const import (
    CMD_UP,
    CMD_DOWN,
    CMD_STOP,
    CMD_FAV,
)

_LOGGER = logging.getLogger(__name__)
LOGGER = logging.getLogger(__name__)


class NeoSmartBlind:
    def __init__(self, host, the_id, device, close_time, port, protocol):
        self._host = host
        self._port = port
        self._protocol = protocol
        self._the_id = the_id
        self._device = device
        self._close_time = int(close_time)
        
    def adjust_blind(self, pos):
        """Adjust the blind based on the pos value send"""
        if pos == 50:
            self.send_command(CMD_FAV)
            return
        if pos >= 51:
            self.send_command(CMD_UP)
            wait1 = (pos - 50)*2
            wait = (wait1*self._close_time)/100
            LOGGER.warning(wait)
            time.sleep(wait)
            self.send_command(CMD_STOP)
            return            
        if pos <= 49:    
            self.send_command(CMD_DOWN)
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
            LOGGER.error("NeoSmartBlinds, Unknown protocol: " + self._protocol + ", please use: http or tcp")

    def send_command_tcp(self, code):
        """Command sender for TCP"""

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)

            command = self._device + "-" + code + '\r\n'
            LOGGER.info("NeoSmartBlinds, Sending command: " + command)
            s.connect((self._host, self._port))
            while True:
                s.send(command)
        except socket.error:
            LOGGER.exception(socket.error.strerror)
            return

    def send_command_http(self, command):
        """Command sender for HTTP"""
        url = "http://" + self._host + ":" + str(self._port) + "/neo/v1/transmit"

        params = {'id': self._the_id, 'command': self._device + "-" + command, 'hash': str(time.time()).strip(".")[-7:]}

        r = requests.get(url=url, params=params)
        LOGGER.info("Sent: " + r.url)
        LOGGER.info("Neo Hub Responded with - " + r.text)
