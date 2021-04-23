"""Support for NeoSmartBlinds covers."""
import logging

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
    CoverEntity,
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
    CMD_TDBU_CLOSE
)

SUPPORT_NEOSMARTBLINDS = (
    SUPPORT_OPEN
    | SUPPORT_CLOSE
    | SUPPORT_SET_POSITION
    | SUPPORT_OPEN_TILT
    | SUPPORT_CLOSE_TILT
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
        )
    add_entities([cover])


class NeoSmartBlindsCover(CoverEntity):
    """Representation of a NeoSmartBlinds cover."""

    def __init__(self, home_assistant, name, host, the_id, device, close_time, protocol, port, rail):
        """Initialize the cover."""
        self.home_assistant = home_assistant

        if DATA_NEOSMARTBLINDS not in self.home_assistant.data:
            self.home_assistant.data[DATA_NEOSMARTBLINDS] = []

        self._name = name
        self._host = host
        self._the_id = the_id
        self._device = device
        self._protocol = protocol
        self._port = port
        self._rail = rail
        self._client = NeoSmartBlind(self._host,
                                     self._the_id,
                                     self._device,
                                     close_time,
                                     self._port,
                                     self._protocol,
                                     self._rail)

        self.home_assistant.data[DATA_NEOSMARTBLINDS].append(self._client)

    @property
    def name(self):
        """Return the name of the NeoSmartBlinds device."""
        return self._name

    @property
    def unique_id(self):
        """Return a unique id for the entity"""
        return DATA_NEOSMARTBLINDS + "." + self._device

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
        return None

    @property
    def current_cover_position(self):
        """Return current position of cover."""
        return 50

    @property
    def current_cover_tilt_position(self):
        """Return current position of cover tilt."""
        return 50

    def close_cover(self, **kwargs):
        if self._rail == 1:
            self._client.send_command(CMD_DOWN)
        elif self._rail == 2:
            self._client.send_command(CMD_DOWN2)
        """Close the cover."""

    def open_cover(self, **kwargs):
        if self._rail == 1:
            self._client.send_command(CMD_UP)
        elif self._rail == 2:
            self._client.send_command(CMD_UP2)
        """Open the cover."""

    def stop_cover(self, **kwargs):
        self._client.send_command(CMD_STOP)
        """Stop the cover."""
        
    def open_cover_tilt(self, **kwargs):
        if self._rail == 1:
            self._client.send_command(CMD_MICRO_UP)
        elif self._rail == 2:
            self._client.send_command(CMD_MICRO_UP2)
        """Open the cover tilt."""
        
    def close_cover_tilt(self, **kwargs):
        if self._rail == 1:
            self._client.send_command(CMD_MICRO_DOWN)
        elif self._rail == 2:
            self._client.send_command(CMD_MICRO_DOWN2)
        """Close the cover tilt."""

    def set_cover_position(self, **kwargs):
        self._client.adjust_blind(kwargs['position'])
        """Move the cover to a specific position."""

