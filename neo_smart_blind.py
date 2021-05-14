import logging
import socket
import time
from datetime import datetime

import aiohttp

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

class NeoCommandSender(object):
    def __init__(self, host, the_id, device, port, motor_code):
        self._host = host
        self._port = port
        self._the_id = the_id
        self._device = device
        self._motor_code = motor_code

class NeoTcpCommandSender(NeoCommandSender):
    
    def send_command(self, command):
        """Command sender for TCP"""

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
            mc = ""
            if self._motor_code:
                mc = "!{}".format(self._motor_code)

            complete_command = self._device + "-" + command + mc + '\r\n'
            _LOGGER.info("NeoSmartBlinds, Sending command: {}".format(complete_command))
            s.connect((self._host, self._port))
            while True:
                s.send(complete_command.encode())
        except socket.error:
            LOGGER.exception(socket.error.strerror)
            return

class NeoHttpCommandSender(NeoCommandSender):
    def __init__(self, host, the_id, device, port, motor_code):
        #TODO: share across all senders
        self._session = aiohttp.ClientSession()
        super().__init__(host, the_id, device, port, motor_code)

    async def async_send_command(self, command):
        """Command sender for HTTP"""
        url = "http://{}:{}/neo/v1/transmit".format(self._host, self._port)

        mc = ""
        if self._motor_code:
            mc = "!{}".format(self._motor_code)

        hash_string = str(datetime.now().microsecond).zfill(7)
        # hash_string = pre_strip[-7:].strip(".")

        params = {'id': self._the_id, 'command': self._device + "-" + command + mc, 'hash': hash_string}

        async with self._session.get(url=url, params=params) as r:
            _LOGGER.info("Tx: {}".format(r.url))
            if r.status == 200:
                _LOGGER.info("Rx: {} - {}".format(r.status, await r.text()))
            else:
                _LOGGER.error("Rx: {} - {}".format(r.status, await r.text()))


class NeoSmartBlind:
    def __init__(self, host, the_id, device, port, protocol, rail, motor_code):
        self._rail = rail
        """Command handler to send based on correct protocol"""
        self._command_sender = None

        if protocol.lower() == "http":
            self._command_sender = NeoHttpCommandSender(host, the_id, device, port, motor_code)

        elif str(self._protocol).lower() == "tcp":
            self._command_sender = NeoTcpCommandSender(host, the_id, device, port, motor_code)

        else:
            LOGGER.error("NeoSmartBlinds, Unknown protocol: {}, please use: http or tcp".format(protocol))


    def unique_id(self, prefix):
        return "{}.{}.{}.{}".format(prefix, self._command_sender._device, self._command_sender._motor_code, self._rail)

    def set_position_by_percent(self, pos):
        """NeoBlinds works off of percent closed, but HA works off of percent open, so need to invert the percentage"""
        closed_pos = 100 - pos
        padded_position = f'{closed_pos:02}'
        _LOGGER.info('Sending ' + padded_position)
        self._command_sender.send_command(padded_position)
        return

    async def async_stop_command(self):
        await self._command_sender.async_send_command(CMD_STOP)

    def open_cover_tilt(self, **kwargs):
        if self._rail == 1:
            self._command_sender.send_command(CMD_MICRO_UP)
        elif self._rail == 2:
            self._command_sender.send_command(CMD_MICRO_UP2)
        """Open the cover tilt."""
        
    def close_cover_tilt(self, **kwargs):
        if self._rail == 1:
            self._command_sender.send_command(CMD_MICRO_DOWN)
        elif self._rail == 2:
            self._command_sender.send_command(CMD_MICRO_DOWN2)
        """Close the cover tilt."""

    """Send down command with rail support"""
    async def async_down_command(self):
        if self._rail == 1:
            await self._command_sender.async_send_command(CMD_DOWN)
        elif self._rail == 2:
            await self._command_sender.async_send_command(CMD_DOWN2)

    """Send up command with rail support"""
    async def async_up_command(self):
        if self._rail == 1:
            await self._command_sender.async_send_command(CMD_UP)
        elif self._rail == 2:
            await self._command_sender.async_send_command(CMD_UP2)

    def set_fav_position(self, pos):
        LOGGER.info('Setting fav: ' + str(pos))
        if pos <= 50:
            self._command_sender.send_command(CMD_FAV)
            return 50
        if pos >= 51:
            self._command_sender.send_command(CMD_FAV_2)
            return 51
        return




# 2021-05-13 10:20:38 INFO (SyncWorker_4) [root] Sent: http://<ip>:8838/neo/v1/transmit?id=440036000447393032323330&command=146.215-08-up&hash=.812864
# 2021-05-13 10:20:38 INFO (SyncWorker_4) [root] Neo Hub Responded with - 

# 2021-05-13 10:30:54 INFO (SyncWorker_6) [root] Sent: http://<ip>:8838/neo/v1/transmit?id=440036000447393032323330&command=146.215-08-sp&hash=4.65143 (from 1620901854.65143)
# 2021-05-13 10:30:54 INFO (SyncWorker_6) [root] Neo Hub Responded with - 