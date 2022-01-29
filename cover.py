"""Support for NeoSmartBlinds covers."""

import asyncio
import aiohttp
import logging
import time

from voluptuous import Any

from homeassistant.components.cover import PLATFORM_SCHEMA
from custom_components.neosmartblinds.neo_smart_blind import NeoSmartBlind
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
import functools as ft
from homeassistant.helpers.restore_state import RestoreEntity

from homeassistant.components.cover import (
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_STOP,
    SUPPORT_SET_POSITION,
    SUPPORT_OPEN_TILT,
    SUPPORT_CLOSE_TILT,
    SUPPORT_SET_TILT_POSITION,
    CoverEntity,
    ATTR_CURRENT_POSITION
)

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
    CONF_START_POSITION,
    DATA_NEOSMARTBLINDS,
    # CMD_UP,
    # CMD_DOWN,
    # CMD_MICRO_UP,
    # CMD_MICRO_DOWN,
    # CMD_STOP,
    # CMD_UP2,
    # CMD_DOWN2,
    # CMD_MICRO_UP2,
    # CMD_MICRO_DOWN2,
    # CMD_UP3,
    # CMD_DOWN3,
    # CMD_TDBU_OPEN,
    # CMD_TDBU_CLOSE,
    LEGACY_POSITIONING,
    EXPLICIT_POSITIONING,
    IMPLICIT_POSITIONING,
    ACTION_STOPPED,
    ACTION_OPENING,
    ACTION_CLOSING
)

PARALLEL_UPDATES = 0

SUPPORT_NEOSMARTBLINDS = (
        SUPPORT_OPEN
        | SUPPORT_CLOSE
        | SUPPORT_OPEN_TILT
        | SUPPORT_CLOSE_TILT
        | SUPPORT_STOP
)

_LOGGER = logging.getLogger(__name__)

LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST, description="hostname / IP of hub"): cv.string,
        vol.Required(CONF_NAME, description="name of blind to appear in HA"): cv.string,
        vol.Required(CONF_DEVICE, description="ID Code of blind in app"): cv.string,
        vol.Required(CONF_CLOSE_TIME, description="Time (seconds) it takes for blind to move from fully open to closed",
                     default=20): cv.positive_int,
        vol.Required(CONF_ID, description="ID of hub"): cv.string,
        vol.Required(CONF_PROTOCOL, description="Either http or tcp", default="http"): cv.string,
        vol.Required(CONF_PORT, description="port of hub (usually: http=8838, tcp=8839)", default=8838): cv.port,
        vol.Required(CONF_RAIL, description="rail to move", default=1): cv.positive_int,
        vol.Required(CONF_PERCENT_SUPPORT,
                     description="0=favourite positioning only, 1=send percent positioning commands to hub, 2=use up / down commands to estimate position",
                     default=0): cv.positive_int,
        vol.Required(CONF_MOTOR_CODE, description="ID Code of motor in app", default=''): cv.string,
        vol.Optional(CONF_START_POSITION,
                     description="If percent positioning mode is enabled, this value will be used as the starting position else it will be restored from the last run"): cv.positive_int,
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
        config.get(CONF_MOTOR_CODE),
        config.get(CONF_START_POSITION)
    )
    async_add_entities([cover])


def compute_wait_time(larger, smaller, close_time):
    """
    Helper function to estimate how long to wait for a blind move to complete.

    The caller must determine direction and specify the larger value. The positions
    provided are %.

    make sure we are returning a positive number, otherwise the time is instant.
    """
    return abs(((larger - smaller) * close_time) / 100)


class PositioningRequest(object):
    """
    Helper class for monitoring and reacting to a blind position change
    """

    def __init__(self, target_position, starting_position, needs_stop):
        self._target_position = target_position
        self._starting_position = starting_position
        # Event to interrupt pending positioning attempts and either cancel or recalculate the delay
        self._interrupt = asyncio.Event()
        # Time at which the positioning attempt began
        self._start = time.time()
        # Active wait (will be None until the wait coroutine begins)
        self._active_wait = None
        # If interrupted to adjust the wait time, this is the new wait time
        self._adjusted_wait = None
        # Indicates whether the pending positioning attempt requires the entity to call stop once complete
        self._needs_stop = needs_stop

    @property
    def needs_stop(self):
        return self._needs_stop

    @property
    def target_position(self):
        return self._target_position

    @property
    def starting_position(self):
        return 50

    async def async_wait(self, reason, cover):
        """
        Wait on the positioning request to complete.

        Can be interrupted by adjust() or interrupt().
        """
        elapsed = 0
        while True:
            LOGGER.info(
                '{} sleeping for {} to allow for {} to {}, elapsed={}'.format(cover.name, self._active_wait, reason,
                                                                              self._target_position, elapsed))
            await asyncio.wait_for(
                asyncio.create_task(self._interrupt.wait()), self._active_wait - elapsed
            )
            elapsed = time.time() - self._start
            if self._adjusted_wait is not None:
                # compute adjusted target position given interrupt
                self._active_wait = self._adjusted_wait
                self._adjusted_wait = None
                self._interrupt.clear()
            else:
                break
        return elapsed

    async def async_wait_for_move_up(self, cover):
        """
        Wait for the blind to move up to the target position

        Returns whether the request was interrupted and a new target position was computed.
        """
        was_interrupted = False

        self._active_wait = compute_wait_time(self._target_position, self._starting_position, cover.close_time)
        try:
            elapsed = await self.async_wait('open', cover)
            if elapsed < self._active_wait:
                self._target_position = int(
                    self._starting_position + (
                                self._target_position - self._starting_position) * elapsed / self._active_wait
                )
                was_interrupted = True
        except asyncio.TimeoutError:
            # all done
            pass

        return was_interrupted

    async def async_wait_for_move_down(self, cover):
        """
        Wait for the blind to move down to the target position

        Returns whether the request was interrupted and a new target position was computed.
        """
        was_interrupted = False

        self._active_wait = compute_wait_time(self._starting_position, self._target_position, cover.close_time)
        try:
            elapsed = await self.async_wait('close', cover)
            if elapsed < self._active_wait:
                self._target_position = int(
                    self._starting_position - (
                                self._starting_position - self._target_position) * elapsed / self._active_wait
                )
                was_interrupted = True
        except asyncio.TimeoutError:
            # all done
            pass

        return was_interrupted

    def is_moving_up(self):
        """
        Indicates whether the blind is moving up
        """
        return self._target_position > self._starting_position

    def estimate_current_position(self):
        """
        Compute an estimated position of the ongoing request based on elapsed time
        """
        # If the wait coro hasn't been awaited, this will be None. The position is simply the start.
        if not self._active_wait:
            return self._starting_position

        elapsed = time.time() - self._start
        if self.is_moving_up():
            return int(
                self._starting_position + (
                            self._target_position - self._starting_position) * elapsed / self._active_wait
            )
        else:
            return int(
                self._starting_position - (
                            self._starting_position - self._target_position) * elapsed / self._active_wait
            )

    def adjust(self, target_position, cover):
        """
        Attempt to adjust the ongoing request to a new target_position.
        Return estimated current position if the ongoing request can't be adjusted, None otherwise
        """
        cur = self.estimate_current_position()
        if self.is_moving_up():
            if cur <= target_position:
                self._target_position = target_position
                self._adjusted_wait = compute_wait_time(target_position, self._starting_position, cover.close_time)
                self.interrupt()
                return
        else:
            if cur >= target_position:
                self._target_position = target_position
                self._adjusted_wait = compute_wait_time(self._starting_position, target_position, cover.close_time)
                self.interrupt()
                return
        LOGGER.info('{} estimated position is {}, force direction change'.format(cover.name, cur))
        return cur

    def interrupt(self):
        """
        Interrupt the ongoing request
        """
        self._interrupt.set()


class NeoSmartBlindsCover(CoverEntity, RestoreEntity):
    """Representation of a NeoSmartBlinds cover."""

    def __init__(self, home_assistant, name, host, the_id, device, close_time, protocol, port, rail, percent_support,
                 motor_code, starting_position):
        """Initialize the cover."""
        self.home_assistant = home_assistant
        self._name = name
        # This isn't ideal but there is no feedback from the blind / hub about position.
        self._percent_support = percent_support
        if self._percent_support > 0:
            self._current_position = starting_position
        else:
            self._current_position = 50
        self._close_time = int(close_time)
        # Used to advertise state to ha
        self._current_action = ACTION_STOPPED
        # Pending positioning request
        self._pending_positioning_command = None
        # Event used to cleanly cancel a positioning command and stop the blind
        self._stopped = None

        def http_session_factory(timeout):
            """
            Closure used to give the client a HTTP session that is shared by all covers
            """
            if DATA_NEOSMARTBLINDS not in self.home_assistant.data:
                t = aiohttp.ClientTimeout(total=timeout)
                self.home_assistant.data[DATA_NEOSMARTBLINDS] = aiohttp.ClientSession(timeout=t)

            return self.home_assistant.data[DATA_NEOSMARTBLINDS]

        self._client = NeoSmartBlind(host,
                                     the_id,
                                     device,
                                     port,
                                     protocol,
                                     rail,
                                     motor_code,
                                     http_session_factory)

    @property
    def close_time(self):
        """Return the close time"""
        return self._close_time

    @property
    def pending_positioning_command(self):
        """Return the pending position command"""
        return self._pending_positioning_command

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
        return 50

    @property
    def current_cover_tilt_position(self):
        """Return current position of cover tilt."""
        return 50

    async def async_added_to_hass(self):
        """Complete the initialization."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if self._current_position is None:
            if last_state is not None and ATTR_CURRENT_POSITION in last_state.attributes:
                self._current_position = last_state.attributes[ATTR_CURRENT_POSITION]
            else:
                self._current_position = 50

    async def async_close_cover(self, **kwargs):
        """Fully close the cover."""
        # Be pessimistic and ensure that a command is always issued. To do this, ensure
        # any pending request is stopped first
        if self._pending_positioning_command is not None:
            await self.async_stop_cover()

        await self.async_close_cover_to(0)

    async def async_close_cover_to(self, target_position, move_command=None):
        """
        Close the cover to the target_position specified.
        The caller is responsible for determining that getting to the target_position requires the
        blind to close!
        If specified, move_command is a coroutine used to move the blind else a down command is issued.
        """
        # Create an event to manage clean stop for this positioning attempt
        self._stopped = asyncio.Event()
        self._pending_positioning_command = PositioningRequest(target_position, self._current_position,
                                                               not (target_position == 0 or move_command))

        # Set the current position of the entity to the target
        self._current_position = target_position
        self._current_action = ACTION_CLOSING

        # Issue the move command
        if await self._client.async_down_command() if move_command is None else await move_command():
            LOGGER.info('{} closing to {}'.format(self._name, target_position))
            # Put the positioning request on the ha queue to run in parallel but don't await it here (we want to continue)
            self.hass.async_create_task(self.async_cover_closed_to_position())
            # Finally, update the state to reflect that the command is in flight
            self.async_write_ha_state()
        else:
            # The request failed, just go through the motions of completion
            self.cover_change_complete(False)

    async def async_open_cover(self, **kwargs):
        """Fully open the cover."""
        # Be pessimistic and ensure that a command is always issued. To do this, ensure
        # any pending request is stopped first
        if self._pending_positioning_command is not None:
            await self.async_stop_cover()

        await self.async_open_cover_to(100)

    async def async_open_cover_to(self, target_position, move_command=None):
        """
        Close the cover to the target_position specified.
        The caller is responsible for determining that getting to the target_position requires the
        blind to close!
        If specified, move_command is a coroutine used to move the blind else a down command is issued.
        """
        # Create an event to manage clean stop for this positioning attempt
        self._stopped = asyncio.Event()
        self._pending_positioning_command = PositioningRequest(target_position, self._current_position,
                                                               not (target_position == 100 or move_command))

        # Set the current position of the entity to the target
        self._current_position = target_position
        self._current_action = ACTION_OPENING

        # Issue the move command
        if await self._client.async_up_command() if move_command is None else await move_command():
            LOGGER.info('{} opening to {}'.format(self._name, target_position))
            # Put the positioning request on the ha queue to run in parallel but don't await it here (we want to continue)
            self.hass.async_create_task(self.async_cover_opened_to_position())
            # Finally, update the state to reflect that the command is in flight
            self.async_write_ha_state()
        else:
            # The request failed, just go through the motions of completion
            self.cover_change_complete(False)

    async def async_cover_closed_to_position(self):
        """
        Coroutine to deal with completion of positioning request down.
        """
        # Wait for the request to run to its completion
        if not await self.pending_positioning_command.async_wait_for_move_down(self):
            # If the request completed fully but needs an explicit stop to finish off, trigger it now
            if self.pending_positioning_command.needs_stop:
                await self._client.async_stop_command()
        self.cover_change_complete()

    async def async_cover_opened_to_position(self):
        # Wait for the request to run to its completion
        if not await self.pending_positioning_command.async_wait_for_move_up(self):
            # If the request completed fully but needs an explicit stop to finish off, trigger it now
            if self.pending_positioning_command.needs_stop:
                await self._client.async_stop_command()
        self.cover_change_complete()

    def cover_change_complete(self, result=True):
        """
        Manage completion of a positioning request by cleaning everything up.
        """
        # If the completion issued and awaited a stop command, defend against a situation
        # that the command was cleaned up in parallel (NB. this might be a hangover from
        # the initial async conversion where the IO itself was sync and moved to the worker
        # pool so this defence may not strictly be necessary).
        if self.pending_positioning_command is not None:
            # Update the entity state
            self._current_action = ACTION_STOPPED
            if result:
                self._current_position = self.pending_positioning_command.target_position
                LOGGER.info('{} move done {}'.format(self._name, self._current_position))
            else:
                self._current_position = self.pending_positioning_command.starting_position
            self._pending_positioning_command = None
            # Signal to any other awaiting coroutines that the stop has completed fully
            self._stopped.set()
            # Finally, notify ha of the state change
            self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""
        LOGGER.info('{} stop'.format(self._name))
        await self._client.async_stop_command()
        if self.pending_positioning_command is not None:
            # Interrupt any pending positioning requests
            self.pending_positioning_command.interrupt()
            # Wait for the command to stop completely
            await self._stopped.wait()
            # NB. EVERYTHING must be happening on the main event thread to guarantee that it 
            # is safe to do this here
            self._stopped = None
        else:
            # Just make sure the state is correct (though there's a consistency issue here if 
            # this isn't already the case)
            self._current_action = ACTION_STOPPED

    async def async_open_cover_tilt(self, **kwargs):
        await self._client.async_open_cover_tilt()
        """Open the cover tilt."""

    async def async_close_cover_tilt(self, **kwargs):
        await self._client.async_close_cover_tilt()
        """Close the cover tilt."""

    async def async_set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        await self.async_adjust_blind(kwargs['position'])

    async def async_set_fav_position(self, pos):
        # Position doesn't resemble reality so the state is likely to get out of step
        position = await self._client.async_set_fav_position(pos)
        if isinstance(position, int):
            self._current_position = position
            self.async_write_ha_state()

    async def async_set_cover_tilt_position(self, **kwargs):
        await self.async_set_fav_position(kwargs['tilt_position'])

    """Adjust the blind based on the pos value send"""

    async def async_adjust_blind(self, pos):

        """Legacy support for using position to set favorites"""
        if self._percent_support == LEGACY_POSITIONING:
            if pos == 50 or pos == 51:
                await self.async_set_fav_position(pos)
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
                # The estimated position will be returned if the cover is moving in the wrong direction
                if estimated_position is not None:
                    # STOP then issue new command
                    await self.async_stop_cover()
                    delta = pos - estimated_position
                elif self._percent_support == EXPLICIT_POSITIONING:
                    # just issue the new position, the wait is adjusted already
                    await self._client.async_set_position_by_percent(pos)
                # else: adjustment handled silently, leave delta at zero so no command is sent
            else:
                # New command, nothing in-flight -- compute the delta
                delta = pos - self._current_position

            if delta > 0:
                if self._percent_support == IMPLICIT_POSITIONING or pos == 100:
                    await self.async_open_cover_to(pos)
                elif self._percent_support == EXPLICIT_POSITIONING:
                    await self.async_open_cover_to(
                        pos,
                        ft.partial(self._client.async_set_position_by_percent, pos)
                    )

            if delta < 0:
                if self._percent_support == IMPLICIT_POSITIONING or pos == 0:
                    await self.async_close_cover_to(pos)
                elif self._percent_support == EXPLICIT_POSITIONING:
                    await self.async_close_cover_to(
                        pos,
                        ft.partial(self._client.async_set_position_by_percent, pos)
                    )
