"""Support for NeoSmartBlinds covers."""
import asyncio
import logging
import time

from homeassistant.components.cover import PLATFORM_SCHEMA
from custom_components.neosmartblinds.neo_smart_blind import NeoSmartBlind
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
import functools as ft

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


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
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
    async_add_entities([cover])

def compute_wait_time(larger, smaller, close_time):
    return ((larger - smaller) * close_time) / 100

class PositioningRequest(object):
    def __init__(self, target_position, starting_position, needs_stop):
        self._target_position = target_position
        self._starting_position = starting_position
        self._interrupt = asyncio.Event()
        self._start = time.time()
        self._active_wait = None
        self._adjusted_wait = None
        self._needs_stop = needs_stop

    async def async_wait(self, reason):
        elapsed = 0
        while True:
            LOGGER.info('Sleeping for {} to allow for {} to {}, elapsed={}'.format(self._active_wait, reason, self._target_position, elapsed))
            await asyncio.wait_for(
                asyncio.create_task(self._interrupt.wait()), self._active_wait - elapsed
                )
            elapsed = time.time() - self._start
            if self._adjusted_wait is not None:
                #compute adjusted target position given interrupt
                self._active_wait = self._adjusted_wait
                self._adjusted_wait = None
                self._interrupt.clear()
            else:
                break
        return elapsed

    async def async_wait_for_move_up(self, cover):
        was_interrupted = False

        self._active_wait = compute_wait_time(self._target_position, self._starting_position, cover._close_time)
        try:
            elapsed = await self.async_wait('open')
            if elapsed < self._active_wait:
                self._target_position = int(
                    self._starting_position + (self._target_position - self._starting_position) * elapsed / self._active_wait
                    )
                was_interrupted = True
        except asyncio.TimeoutError:
            #all done
            pass 

        return was_interrupted

    async def async_wait_for_move_down(self, cover):
        was_interrupted = False

        self._active_wait = compute_wait_time(self._starting_position, self._target_position, cover._close_time)
        try:
            elapsed = await self.async_wait('close')
            if elapsed < self._active_wait:
                self._target_position = int(
                    self._starting_position - (self._starting_position - self._target_position) * elapsed / self._active_wait
                    )
                was_interrupted = True
        except asyncio.TimeoutError:
            #all done
            pass 

        return was_interrupted

    def is_moving_up(self):
        return self._target_position > self._starting_position

    def estimate_current_position(self):
        if not self._active_wait:
            return self._starting_position
            
        elapsed = time.time() - self._start
        if self.is_moving_up():
            return int(
                self._starting_position + (self._target_position - self._starting_position) * elapsed / self._active_wait
                )            
        else:
            return int(
                self._starting_position - (self._starting_position - self._target_position) * elapsed / self._active_wait
                )

    def adjust(self, target_position, cover):
        """Return estimated current position if the ongoing request can't be adjusted"""
        cur = self.estimate_current_position()
        if self.is_moving_up():
            if cur <= target_position:
                self._target_position = target_position
                self._adjusted_wait = compute_wait_time(target_position, self._starting_position, cover._close_time)
                self.interrupt()
                return
        else:
            if cur >= target_position:
                self._target_position = target_position
                self._adjusted_wait = compute_wait_time(self._starting_position, target_position, cover._close_time)
                self.interrupt()
                return
        LOGGER.info('Estimated position is {}, force direction change'.format(cur))
        return cur

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
        self._stopped = None

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
        return self._client.unique_id(DATA_NEOSMARTBLINDS)

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
        
    async def async_close_cover_to(self, target_position, move_command=None):
        self._stopped = asyncio.Event()
        self._pending_positioning_command = PositioningRequest(target_position, self._current_position, target_position == 0 or move_command)

        self._current_position = target_position
        self._current_action = ACTION_CLOSING

        await self._client.async_down_command() if move_command is None else move_command()

        LOGGER.info('closing to {}'.format(target_position))
        self.hass.async_create_task(self.async_cover_closed_to_position())
        self.async_write_ha_state()

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        await self.async_open_cover_to(100)

    async def async_open_cover_to(self, target_position, move_command=None):
        self._stopped = asyncio.Event()
        self._pending_positioning_command = PositioningRequest(target_position, self._current_position, target_position == 100 or move_command)

        self._current_position = target_position
        self._current_action = ACTION_OPENING

        await self._client.async_up_command() if move_command is None else move_command()

        LOGGER.info('opening to {}'.format(target_position))
        self.hass.async_create_task(self.async_cover_opened_to_position())
        self.async_write_ha_state()

    async def async_cover_closed_to_position(self):
        if not await self._pending_positioning_command.async_wait_for_move_down(self):
            if self._pending_positioning_command._needs_stop:
                await self._client.async_stop_command()
        self.cover_change_complete()

    async def async_cover_opened_to_position(self):
        if not await self._pending_positioning_command.async_wait_for_move_up(self):
            if self._pending_positioning_command._needs_stop:
                await self._client.async_stop_command()
        self.cover_change_complete()

    def cover_change_complete(self):
        if self._pending_positioning_command is not None:
            self._current_action = ACTION_STOPPED
            self._current_position = self._pending_positioning_command._target_position
            LOGGER.info('move done {}'.format(self._current_position))
            self._pending_positioning_command = None
            self._stopped.set()
            self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs):
        LOGGER.info('stop')
        await self._client.async_stop_command()
        if self._pending_positioning_command is not None:
            self._pending_positioning_command.interrupt()
            await self._stopped.wait()
            self._stopped = None
        else:
            self._current_action = ACTION_STOPPED
        """Stop the cover."""
        
    async def async_open_cover_tilt(self, **kwargs):
        await self._client.async_open_cover_tilt()
        """Open the cover tilt."""
        
    async def async_close_cover_tilt(self, **kwargs):
        await self._client.async_close_cover_tilt()
        """Close the cover tilt."""

    async def async_set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        await self.async_adjust_blind(kwargs['position'])

    async def async_set_cover_tilt_position(self, **kwargs):
        # Position doesn't resemble reality so the state is likely to get out of step
        self._current_position = await self._client.async_set_fav_position(kwargs['tilt_position'])
        self.async_write_ha_state()

    """Adjust the blind based on the pos value send"""
    async def async_adjust_blind(self, pos):

        """Legacy support for using position to set favorites"""
        if self._percent_support == LEGACY_POSITIONING:
            if pos == 50 or pos == 51:
                self._current_position = await self._client.async_set_fav_position(pos)
                self.async_write_ha_state()
        else:
            """Always allow full open / close commands to get through"""

            if pos > 98:
                """
                Unable to send 100 to the API so assume anything greater then 98 is just an open command.
                Use the same logic irrespective of mode for consistency.            
                """
                pos = 100
            if pos < 2:
                """Assume anything greater less than 2 is just a close command"""
                pos = 0

            """Check for any change in position, only act if it has changed"""
            delta = 0

            """
            Work out whether the blind is already moving.
            If yes, work out whether it is moving in the right direction.
                If yes, just adjust the pending timeout.
                If no, cancel the existing timer and issue a fresh positioning command
            if not, issue a positioning command
            """
            if self._pending_positioning_command is not None:
                estimated_position = self._pending_positioning_command.adjust(pos, self)
                if estimated_position is not None:
                    #STOP then issue new command
                    await self.async_stop_cover()
                    delta = pos - estimated_position
                elif self._percent_support == EXPLICIT_POSITIONING:
                    #just issue the new position, the wait is adjusted already
                    await self._client.async_set_position_by_percent(pos)
                #else: adjustment handled silently, leave delta at zero so no command is sent
            else:
                delta = pos - self._current_position

            if delta > 0 or pos == 100:
                if self._percent_support == IMPLICIT_POSITIONING or pos == 100:
                    await self.async_open_cover_to(pos)
                elif self._percent_support == EXPLICIT_POSITIONING:
                    await self.async_open_cover_to(
                        pos, 
                        ft.partial(self._client.async_set_position_by_percent, pos)
                    )

            if delta < 0 or pos == 0:
                if self._percent_support == IMPLICIT_POSITIONING or pos == 0:
                    await self.async_close_cover_to(pos)
                elif self._percent_support == EXPLICIT_POSITIONING:
                    await self.async_open_cover_to(
                        pos, 
                        ft.partial(self._client.async_set_position_by_percent, pos)
                    )
