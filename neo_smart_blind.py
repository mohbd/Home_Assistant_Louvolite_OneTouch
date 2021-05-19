import logging
import socket
import time
from datetime import datetime

import aiohttp
import asyncio

from .const import (
    CMD_UP,
    CMD_UP2,
    CMD_DOWN,
    CMD_DOWN2,
    CMD_STOP,
    CMD_FAV,
    CMD_FAV_1,
    CMD_FAV_2,
    CMD_MICRO_UP,
    CMD_MICRO_DOWN,
    DEFAULT_IO_TIMEOUT
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
        self._was_connected = None

    def on_io_complete(self, result=None):
        """
        Helper function to trap connection status and log it on change only.
        result is either None (success) or an exception (fail)
        """
        if result is None:
            if not self._was_connected:
                _LOGGER.info('{}, connected to hub'.format(self._device))
                self._was_connected = True
        else:
            if self._was_connected or self._was_connected is None:
                _LOGGER.warning('{}, disconnected from hub: {}'.format(self._device, repr(result)))
                self._was_connected = False
        
        return self._was_connected


class NeoTcpCommandSender(NeoCommandSender):
    
    async def async_send_command(self, command):
        """Command sender for TCP"""

        async def async_sender():
            """
            Wrap all the IO in an awaitable closure so a timeout can be put on it in the outer function
            """
            reader, writer = await asyncio.open_connection(self._host, self._port)

            mc = ""
            if self._motor_code:
                mc = "!{}".format(self._motor_code)

            complete_command = self._device + "-" + command + mc + '\r\n'
            _LOGGER.debug("{}, Tx: {}".format(self._device, complete_command))
            writer.write(complete_command.encode())

            response = await reader.read()
            _LOGGER.debug("{}, Rx: {}".format(self._device, response.decode()))

            writer.close()
            await writer.wait_closed()

        try:
            await asyncio.wait_for(async_sender(), timeout=DEFAULT_IO_TIMEOUT)
            return self.on_io_complete()
        except Exception as e:
            return self.on_io_complete(e)


class NeoHttpCommandSender(NeoCommandSender):
    def __init__(self, http_session_factory, host, the_id, device, port, motor_code):
        self._session = http_session_factory(DEFAULT_IO_TIMEOUT)
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

        try:
            async with self._session.get(url=url, params=params, raise_for_status=True) as r:
                _LOGGER.debug("{}, Tx: {}".format(self._device, r.url))
                _LOGGER.debug("{}, Rx: {} - {}".format(self._device, r.status, await r.text()))
                return self.on_io_complete()
        except Exception as e:
            return self.on_io_complete(e)
        

class NeoSmartBlind:
    def __init__(self, host, the_id, device, port, protocol, rail, motor_code, http_session_factory):
        self._rail = rail

        if self._rail < 1 or self._rail > 2:
            _LOGGER.error("{}, unknown rail: {}, please use: 1 or 2".format(device, rail))

        """Command handler to send based on correct protocol"""
        self._command_sender = None

        if protocol.lower() == "http":
            self._command_sender = NeoHttpCommandSender(http_session_factory, host, the_id, device, port, motor_code)

        elif protocol.lower() == "tcp":
            self._command_sender = NeoTcpCommandSender(host, the_id, device, port, motor_code)

        else:
            _LOGGER.error("{}, unknown protocol: {}, please use: http or tcp".format(device, protocol))

    def unique_id(self, prefix):
        return "{}.{}.{}.{}".format(prefix, self._command_sender._device, self._command_sender._motor_code, self._rail)

    async def async_set_position_by_percent(self, pos):
        """NeoBlinds works off of percent closed, but HA works off of percent open, so need to invert the percentage"""
        closed_pos = 100 - pos
        padded_position = f'{closed_pos:02}'
        return await self._command_sender.async_send_command(padded_position)

    async def async_stop_command(self):
        return await self._command_sender.async_send_command(CMD_STOP)

    async def async_open_cover_tilt(self, **kwargs):
        if self._rail == 1:
            return await self._command_sender.async_send_command(CMD_MICRO_UP)
        elif self._rail == 2:
            return await self._command_sender.async_send_command(CMD_MICRO_UP2)
        """Open the cover tilt."""
        return False
        
    async def async_close_cover_tilt(self, **kwargs):
        if self._rail == 1:
            return await self._command_sender.async_send_command(CMD_MICRO_DOWN)
        elif self._rail == 2:
            return await self._command_sender.async_send_command(CMD_MICRO_DOWN2)
        """Close the cover tilt."""
        return False

    """Send down command with rail support"""
    async def async_down_command(self):
        if self._rail == 1:
            return await self._command_sender.async_send_command(CMD_DOWN)
        elif self._rail == 2:
            return await self._command_sender.async_send_command(CMD_DOWN2)
        return False

    """Send up command with rail support"""
    async def async_up_command(self):
        if self._rail == 1:
            return await self._command_sender.async_send_command(CMD_UP)
        elif self._rail == 2:
            return await self._command_sender.async_send_command(CMD_UP2)
        return False

    async def async_set_fav_position(self, pos):
        if pos <= 50:
            if await self._command_sender.async_send_command(CMD_FAV):
                return 50
        if pos >= 51:
            if await self._command_sender.async_send_command(CMD_FAV_2):
                return 51
        return False




# 2021-05-13 10:20:38 INFO (SyncWorker_4) [root] Sent: http://<ip>:8838/neo/v1/transmit?id=440036000447393032323330&command=146.215-08-up&hash=.812864
# 2021-05-13 10:20:38 INFO (SyncWorker_4) [root] Neo Hub Responded with - 

# 2021-05-13 10:30:54 INFO (SyncWorker_6) [root] Sent: http://<ip>:8838/neo/v1/transmit?id=440036000447393032323330&command=146.215-08-sp&hash=4.65143 (from 1620901854.65143)
# 2021-05-13 10:30:54 INFO (SyncWorker_6) [root] Neo Hub Responded with - 