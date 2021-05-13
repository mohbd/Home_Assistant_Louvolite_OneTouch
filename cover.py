"""Support for NeoSmartBlinds covers."""
import asyncio
import logging
import time

from homeassistant.components.cover import PLATFORM_SCHEMA
from custom_components.neosmartblinds.neo_smart_blind import NeoSmartBlind
import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from homeassistant.components.cover import (
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_STOP,
    SUPPORT_SET_POSITION,    
    SUPPORT_OPEN_TILT,
    SUPPORT_CLOSE_TILT,
    SUPPORT_SET_TILT_POSITION,
    CoverEntity,
)

PARALLEL_UPDATES = 0

from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
)

from .const import (
    CONF_DEVICE,
    CONF_CLOSE_TIME,
    CONF_ID,
    CONF_PROTOCOL,
    CONF_PORT,
    CONF_RAIL,
    CONF_PERCENT_SUPPORT,
    CONF_MOTOR_CODE,
    DATA_NEOSMARTBLINDS,
    CMD_UP,
    CMD_DOWN,
    CMD_MICRO_UP,
    CMD_MICRO_DOWN,
    CMD_STOP,
    CMD_UP2,
    CMD_DOWN2,
    CMD_MICRO_UP2,
    CMD_MICRO_DOWN2,
    CMD_UP3,
    CMD_DOWN3,
    CMD_TDBU_OPEN,
    CMD_TDBU_CLOSE,
    LEGACY_POSITIONING,
    EXPLICIT_POSITIONING,
    IMPLICIT_POSITIONING,
    ACTION_STOPPED,
    ACTION_OPENING,
    ACTION_CLOSING
)

SUPPORT_NEOSMARTBLINDS = (
    SUPPORT_OPEN
    | SUPPORT_CLOSE
    | SUPPORT_SET_POSITION
    | SUPPORT_OPEN_TILT
    | SUPPORT_CLOSE_TILT
    | SUPPORT_SET_TILT_POSITION
    | SUPPORT_STOP
)

_LOGGER = logging.getLogger(__name__)

LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_DEVICE, description="ID Code of blind in app"): cv.string,
        vol.Required(CONF_CLOSE_TIME, default=20): cv.positive_int,
        vol.Required(CONF_ID): cv.string,
        vol.Required(CONF_PROTOCOL, default="http"): cv.string,
        vol.Required(CONF_PORT, default=8838): cv.port,
        vol.Required(CONF_RAIL, default=1): cv.positive_int,
        vol.Required(CONF_PERCENT_SUPPORT, default=0): cv.positive_int,
        vol.Required(CONF_MOTOR_CODE, default=''): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None, ):
    """Set up NeoSmartBlinds cover."""
    cover = NeoSmartBlindsCover(
        hass,
        config.get(CONF_NAME),
        config.get(CONF_HOST),
        config.get(CONF_ID),
        config.get(CONF_DEVICE),
        config.get(CONF_CLOSE_TIME),
        config.get(CONF_PROTOCOL),
        config.get(CONF_PORT),
        config.get(CONF_RAIL),
        config.get(CONF_PERCENT_SUPPORT),
        config.get(CONF_MOTOR_CODE)
        )
    add_entities([cover])

class PositioningRequest(object):
    def __init__(self, target_position, starting_position):
        self._target_position = target_position
        self._starting_position = starting_position
        self._interrupt = asyncio.Event()
        self._start = time.time()

    async def wait_for_move_up(self, cover):
        was_interrupted = False

        wait = ((self._target_position - self._starting_position) * cover._close_time) / 100
        try:
            LOGGER.info('Sleeping for {} to allow for open'.format(wait))
            await asyncio.wait_for(
                asyncio.create_task(self._interrupt.wait()), wait
                )
            elapsed = time.time() - self._start
            if elapsed < wait:
                #compute adjusted target position given interrupt
                self._target_position = int(
                    self._starting_position + (self._target_position - self._starting_position) * elapsed / wait
                    )
                was_interrupted = True
        except asyncio.TimeoutError:
            #all done
            pass 

        return was_interrupted

    async def wait_for_move_down(self, cover):
        was_interrupted = False

        wait = ((self._starting_position - self._target_position) * cover._close_time) / 100
        try:
            LOGGER.info('Sleeping for {} to allow for close'.format(wait))
            await asyncio.wait_for(
                asyncio.create_task(self._interrupt.wait()), wait
                )
            elapsed = time.time() - self._start
            if elapsed < wait:
                #compute adjusted target position given interrupt
                self._target_position = int(
                    self._starting_position - (self._starting_position - self._target_position) * elapsed / wait
                    )
                was_interrupted = True
        except asyncio.TimeoutError:
            #all done
            pass 

        return was_interrupted


    def interrupt(self):
        self._interrupt.set()



class NeoSmartBlindsCover(CoverEntity):
    """Representation of a NeoSmartBlinds cover."""

    def __init__(self, home_assistant, name, host, the_id, device, close_time, protocol, port, rail, percent_support, motor_code):
        """Initialize the cover."""
        self.home_assistant = home_assistant

        if DATA_NEOSMARTBLINDS not in self.home_assistant.data:
            self.home_assistant.data[DATA_NEOSMARTBLINDS] = []

        self._name = name
        self._current_position = 50
        self._percent_support = percent_support
        self._close_time = int(close_time)
        self._current_action = ACTION_STOPPED
        self._pending_positioning_command = None

        self._client = NeoSmartBlind(host,
                                     the_id,
                                     device,
                                     port,
                                     protocol,
                                     rail,
                                     motor_code)

        self.home_assistant.data[DATA_NEOSMARTBLINDS].append(self._client)

    @property
    def name(self):
        """Return the name of the NeoSmartBlinds device."""
        return self._name

    @property
    def unique_id(self):
        """Return a unique id for the entity"""
        return DATA_NEOSMARTBLINDS + "." + self._client._device

    @property
    def should_poll(self):
        """No polling needed within NeoSmartBlinds."""
        return False

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_NEOSMARTBLINDS

    @property
    def device_class(self):
        """Define this cover as either window/blind/awning/shutter."""
        return "blind"
        
    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return self._current_position == 0

    @property
    def is_closing(self):
        """Return if the cover is closing."""
        return self._current_action == ACTION_CLOSING

    @property
    def is_opening(self):
        """Return if the cover is opening."""
        return self._current_action == ACTION_OPENING

    @property
    def current_cover_position(self):
        """Return current position of cover."""
        LOGGER.info('Cover Position is: '+ str(self._current_position))
        return self._current_position

    @property
    def current_cover_tilt_position(self):
        """Return current position of cover tilt."""
        return 50

    async def async_close_cover(self, **kwargs):
        """Close cover."""
        await self.async_close_cover_to(0)
        
    async def async_close_cover_to(self, target_position, then=None, move_command=None):
        await self.hass.async_add_executor_job(self._client.down_command if move_command is None else move_command)

        self._pending_positioning_command = PositioningRequest(target_position, self._current_position)

        self._current_position = target_position
        self._current_action = ACTION_CLOSING
        self.async_write_ha_state()

        LOGGER.info('closing to {}'.format(target_position))
        self.hass.async_create_task(self.async_cover_closed() if then is None else then())

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        await self.async_open_cover_to(100)

    async def async_open_cover_to(self, target_position, then=None, move_command=None):
        await self.hass.async_add_executor_job(self._client.up_command if move_command is None else move_command)

        self._pending_positioning_command = PositioningRequest(target_position, self._current_position)

        self._current_position = target_position
        self._current_action = ACTION_OPENING
        self.async_write_ha_state()

        LOGGER.info('opening to {}'.format(target_position))
        self.hass.async_create_task(self.async_cover_opened() if then is None else then())

    async def async_cover_closed_to_position(self):
        if not await self._pending_positioning_command.wait_for_move_down(self):
            await self.hass.async_add_executor_job(self._client.stop_command)
        self.cover_change_complete()

    async def async_cover_opened_to_position(self):
        if not await self._pending_positioning_command.wait_for_move_up(self):
            await self.hass.async_add_executor_job(self._client.stop_command)
        self.cover_change_complete()

    async def async_cover_closed(self):
        await self._pending_positioning_command.wait_for_move_down(self)
        self.cover_change_complete()

    async def async_cover_opened(self):
        await self._pending_positioning_command.wait_for_move_up(self)
        self.cover_change_complete()

    def cover_change_complete(self):
        if self._pending_positioning_command is not None:
            self._current_action = ACTION_STOPPED
            self._current_position = self._pending_positioning_command._target_position
            LOGGER.info('move done {}'.format(self._current_position))
            self._pending_positioning_command = None
            self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs):
        LOGGER.info('stop')
        await self.hass.async_add_executor_job(self._client.stop_command)
        if self._pending_positioning_command is not None:
            self._pending_positioning_command.interrupt()
        else:
            self._current_action = ACTION_STOPPED
        """Stop the cover."""
        
    def open_cover_tilt(self, **kwargs):
        self._client.open_cover_tilt()
        """Open the cover tilt."""
        
    def close_cover_tilt(self, **kwargs):
        self._client.close_cover_tilt()
        """Close the cover tilt."""

    async def async_set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        await self.async_adjust_blind(kwargs['position'])
        # self.async_write_ha_state()
        # if follow_up is not None:
        #     follow_up()
        #     self.async_write_ha_state()

    def set_cover_tilt_position(self, **kwargs):
        self._current_position = self._client.set_fav_position(kwargs['tilt_position'])
        self.async_write_ha_state()

    """Adjust the blind based on the pos value send"""
    async def async_adjust_blind(self, pos):

        """Legacy support for using position to set favorites"""
        # if self._percent_support == LEGACY_POSITIONING:
        #     if pos == 50 or pos == 51:
        #         self._client.set_fav_position(pos)
        #     return

        """Always allow full open / close commands to get through"""

        if pos > 98:
            """
            Unable to send 100 to the API so assume anything greater then 98 is just an open command.
            Use the same logic irrespective of mode for consistency.            
            """
            await self.async_open_cover_to(100)
            return
        if pos < 2:
            """Assume anything greater less than 2 is just a close command"""
            await self.async_close_cover_to(0)
            return

        """Check for any change in position, only act if it has changed"""
        delta = pos - self._current_position

        """
        Work out whether the blind is already moving.
        If yes, work out whether it is moving in the right direction.
            If yes, just adjust the pending timeout.
            If no, cancel the existing timer and issue a fresh positioning command
        if not, issue a positioning command
        """

        if delta > 0:
            if self._percent_support == EXPLICIT_POSITIONING:
                pass
            else:
                await self.async_open_cover_to(pos, then=self.async_cover_opened_to_position)

        if delta < 0:
            if self._percent_support == EXPLICIT_POSITIONING:
                pass
            else:
                await self.async_close_cover_to(pos, then=self.async_cover_closed_to_position)
        
        return

