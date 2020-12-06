import time
import logging
from contextlib import contextmanager

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from typing import Any, Callable, Dict, Optional

from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_PASSWORD,
    CONF_USERNAME,
    TEMP_CELSIUS,
)
from homeassistant.components.climate import (
    ClimateEntity,
    PLATFORM_SCHEMA,
)

from homeassistant.helpers.typing import (
    ConfigType,
    DiscoveryInfoType,
    HomeAssistantType,
)


from homeassistant.components.climate.const import (
    CURRENT_HVAC_OFF, CURRENT_HVAC_IDLE, CURRENT_HVAC_COOL, CURRENT_HVAC_HEAT, CURRENT_HVAC_DRY,
    HVAC_MODE_OFF, HVAC_MODE_COOL, HVAC_MODE_FAN_ONLY, HVAC_MODE_DRY, HVAC_MODE_HEAT, HVAC_MODE_HEAT_COOL,
    SUPPORT_TARGET_TEMPERATURE, SUPPORT_FAN_MODE, FAN_OFF, FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH
)

from electrasmart import AC, ElectraAPI

_LOGGER = logging.getLogger(__name__)


CONF_IMEI = "imei"
CONF_TOKEN = "token"
CONF_ACS = "acs"
CONF_AC_ID = "id"
CONF_AC_NAME = "name"
CONF_SID_INTERVAL = "sid_interval"

DEFAULT_NAME = "ElectraSmart"

AC_SCHEMA = vol.Schema(
    {vol.Required(CONF_AC_ID): cv.string, vol.Required(CONF_AC_NAME, default=DEFAULT_NAME): cv.string}
)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_IMEI): cv.string,
        vol.Required(CONF_TOKEN): cv.string,
        vol.Optional(CONF_SID_INTERVAL, default=20): cv.positive_int,
        vol.Required(CONF_ACS): vol.All(cv.ensure_list, [AC_SCHEMA]),
        # TODO: add presets (cool, fan, night...)
        # vol.Optional(
        #     CONF_AWAY_TEMPERATURE, default=DEFAULT_AWAY_TEMPERATURE
        # ): vol.Coerce(float),
        # vol.Optional(
        #     CONF_SAVING_TEMPERATURE, default=DEFAULT_SAVING_TEMPERATURE
        # ): vol.Coerce(float),
        # vol.Optional(
        #     CONF_COMFORT_TEMPERATURE, default=DEFAULT_COMFORT_TEMPERATURE
        # ): vol.Coerce(float),
    }
)


async def async_setup_platform(
    hass: HomeAssistantType,
    config: ConfigType,
    async_add_entities: Callable,
    discovery_info: Optional[DiscoveryInfoType] = None,
) ->None:
    # Note: since this is a global thing, if at least one entity activates it, it's on
    """Set up the ElectraSmartClimate platform."""
    _LOGGER.debug("Setting up the ElectraSmart climate platform")
    session = async_get_clientsession(hass)
    imei = config.get(CONF_IMEI)
    token = config.get(CONF_TOKEN)
    sid_interval = config.get(CONF_SID_INTERVAL)
    acs = [ElectraSmartClimate(ac, imei, token, sid_interval) for ac in config.get(CONF_ACS)]

    async_add_entities(acs, update_before_add=True)


class ElectraSmartClimate(ClimateEntity):
    def __init__(self, ac, imei, token, sid_interval):
        """Initialize the thermostat."""
        self._name = ac[CONF_AC_NAME]
        self._sid_renew_interval = sid_interval
        self.ac = AC(imei, token, ac[CONF_AC_ID])
        self._last_sid_renew = None

    # managed properties

    @property
    def name(self):
        return self._name

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this thermostat."""
        return "_".join([self._name, "climate"])

    @property
    def should_poll(self):
        """Return if polling is required."""
        return True

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return 16

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return 30

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        if self.ac.status is None:
            _LOGGER.debug(f"current_temperature: status is None, returning None")
            return None
        value = self.ac.status.current_temp
        if value is not None:
            value = int(value)
        _LOGGER.debug(f"value of current_temperature property: {value}")
        return value

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        if self.ac.status is None:
            _LOGGER.debug(f"target_temperature: status is None, returning None")
            return None
        value = self.ac.status.spt
        if value is not None:
            value = int(value)
        _LOGGER.debug(f"value of target_temperature property: {value}")
        return value

    @property
    def target_temperature_step(self):
        return 1

    MODE_BY_NAME = {
        "IDLE": CURRENT_HVAC_IDLE
    }

    HVAC_MODE_MAPPING = {
        "STBY": HVAC_MODE_OFF,
        "COOL": HVAC_MODE_COOL,
        "FAN": HVAC_MODE_FAN_ONLY,
        "DRY": HVAC_MODE_DRY,
        "HEAT": HVAC_MODE_HEAT,
        "AUTO": HVAC_MODE_HEAT_COOL,
    }

    HVAC_MODE_MAPPING_INV = {v: k for k, v in HVAC_MODE_MAPPING.items()}

    @property
    def hvac_mode(self):
        """Return hvac operation ie. heat, cool mode."""
        if self.ac.status is None:
            _LOGGER.debug(f"hvac_mode: status is None, returning None")
            return None
        if self.ac.status.is_on:
            ac_mode = self.ac.status.ac_mode
            value = self.HVAC_MODE_MAPPING[ac_mode]
            _LOGGER.debug(f"hvac_mode: returning {value} (derived from {ac_mode})")
            return value
        else:
            _LOGGER.debug(f"hvac_mode: returning HVAC_MODE_OFF - device is off")
            return HVAC_MODE_OFF

    @property
    def hvac_modes(self):
        """HVAC modes."""
        return [HVAC_MODE_OFF, HVAC_MODE_COOL, HVAC_MODE_FAN_ONLY, HVAC_MODE_DRY, HVAC_MODE_HEAT, HVAC_MODE_HEAT_COOL]

    # TODO:!
    # @property
    # def hvac_action(self):
    #     """Return the current running hvac operation."""
    #     # if self._target_temperature < self._current_temperature:
    #     #     return CURRENT_HVAC_IDLE
    #     # return CURRENT_HVAC_HEAT
    #     return CURRENT_HVAC_IDLE

    FAN_MODE_MAPPING = {
        "LOW": FAN_LOW,
        "MED": FAN_MEDIUM,
        "HIGH": FAN_HIGH,
        "AUTO": FAN_AUTO,
    }

    FAN_MODE_MAPPING_INV = {v: k for k, v in FAN_MODE_MAPPING.items()}

    @property
    def fan_mode(self):
        """Returns the current fan mode (low, high, auto etc)"""
        if self.ac.status is None:
            _LOGGER.debug(f"fan_mode: status is None, returning None")
            return None
        if self.ac.status.is_on:
            fan_speed = self.ac.status.fan_speed
            value = self.FAN_MODE_MAPPING[fan_speed]
            _LOGGER.debug(f"fan_mode: returning {value} (derived from {fan_speed})")
            return value
        else:
            _LOGGER.debug(f"fan_mode: returning FAN_OFF - device is off")
            return FAN_OFF

    @property
    def fan_modes(self):
        """Fan modes."""
        return [FAN_OFF, FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH]

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE

    # actions

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        _LOGGER.debug(f"setting new temperature to {temperature}")
        if temperature is None:
            return
        temperature = int(temperature)
        with self._act_and_update():
            self.ac.modify_oper(temperature=temperature)
        _LOGGER.debug(f"new temperature was set to {temperature}")

    def set_hvac_mode(self, hvac_mode):
        _LOGGER.debug(f"setting hvac mode to {hvac_mode}")
        if hvac_mode == HVAC_MODE_OFF:
            _LOGGER.debug(f"turning off ac due to hvac_mode being set to {hvac_mode}")
            with self._act_and_update():
                self.ac.turn_off()
            _LOGGER.debug(f"ac has been turned off due hvac_mode being set to {hvac_mode}")
        else:
            ac_mode = self.HVAC_MODE_MAPPING_INV[hvac_mode]
            _LOGGER.debug(f"setting hvac mode to {hvac_mode} (ac_mode {ac_mode})")
            with self._act_and_update():
                self.ac.modify_oper(ac_mode=ac_mode)
            _LOGGER.debug(f"hvac mode was set to {hvac_mode} (ac_mode {ac_mode})")

    def set_fan_mode(self, fan_mode):
        _LOGGER.debug(f"setting fan mode to {fan_mode}")
        fan_speed = self.FAN_MODE_MAPPING_INV[fan_mode]
        _LOGGER.debug(f"setting fan mode to {fan_mode} (fan_speed {fan_speed})")
        with self._act_and_update():
            self.ac.modify_oper(fan_speed=fan_speed)
        _LOGGER.debug(f"fan mode was set to {fan_mode} (fan_speed {fan_speed})")

    @contextmanager
    def _act_and_update(self):
        self._renew_sid_if_needed()
        yield
        time.sleep(2)
        self.update()
        time.sleep(3)
        self.update()

    # data fetch mechanism

    def _renew_sid_if_needed(self):
        if self._last_sid_renew is None or time.time() - self._last_sid_renew > self._sid_renew_interval:
            _LOGGER.debug("renewing sid")
            self.ac.renew_sid()
            self._last_sid_renew = time.time()

    def update(self):
        """Get the latest data."""
        _LOGGER.debug("Updating status using the client AC instance...")
        self._renew_sid_if_needed()
        self.ac.update_status()
        _LOGGER.debug("Status updated using the client AC instance")
