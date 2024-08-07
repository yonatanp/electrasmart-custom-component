import time
import logging
from contextlib import contextmanager

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from typing import Any, Callable, Dict, Optional

from homeassistant.core import HomeAssistant

from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
    UnitOfTemperature,
    PLATFORM_SCHEMA,
)

from homeassistant.helpers.typing import (
    ConfigType,
    DiscoveryInfoType
)


from homeassistant.components.climate.const import (
    FAN_OFF,
    FAN_AUTO,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_HIGH,
)

from electrasmart import AC, ElectraAPI

_LOGGER = logging.getLogger(__name__)


CONF_IMEI = "imei"
CONF_TOKEN = "token"
CONF_ACS = "acs"
CONF_AC_ID = "id"
CONF_AC_NAME = "name"
CONF_USE_SHARED_SID = "use_shared_sid"

DEFAULT_NAME = "ElectraSmart"

AC_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_AC_ID): cv.string,
        vol.Required(CONF_AC_NAME, default=DEFAULT_NAME): cv.string,
    }
)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_IMEI): cv.string,
        vol.Required(CONF_TOKEN): cv.string,
        vol.Optional(CONF_USE_SHARED_SID, default=False): cv.boolean,
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
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: Callable,
    discovery_info: Optional[DiscoveryInfoType] = None,
) -> None:
    # Note: since this is a global thing, if at least one entity activates it, it's on
    """Set up the ElectraSmartClimate platform."""
    _LOGGER.debug("Setting up the ElectraSmart climate platform")
    session = async_get_clientsession(hass)
    imei = config.get(CONF_IMEI)
    token = config.get(CONF_TOKEN)
    use_shared_sid = config.get(CONF_USE_SHARED_SID)
    acs = [
        ElectraSmartClimate(ac, imei, token, use_shared_sid)
        for ac in config.get(CONF_ACS)
    ]

    async_add_entities(acs, update_before_add=True)


class ElectraSmartClimate(ClimateEntity):
    def __init__(self, ac, imei, token, use_shared_sid):
        self._enable_turn_on_off_backwards_compatibility = False
        """Initialize the thermostat."""
        self._name = ac[CONF_AC_NAME]
        self.ac = AC(imei, token, ac[CONF_AC_ID], None, use_shared_sid)

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
        return UnitOfTemperature.CELSIUS

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
    def target_temperature_low(self):
        return self.target_temperature()
 
    @property
    def target_temperature_high(self):
        return self.target_temperature()

    @property
    def target_temperature_step(self):
        return 1

    MODE_BY_NAME = {"IDLE": HVACAction.IDLE}

    HVAC_MODE_MAPPING = {
        "STBY": HVACMode.OFF,
        "COOL": HVACMode.COOL,
        "FAN": HVACMode.FAN_ONLY,
        "DRY": HVACMode.DRY,
        "HEAT": HVACMode.HEAT,
        "AUTO": HVACMode.HEAT_COOL,
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
            _LOGGER.debug(f"hvac_mode: returning HVACMode.OFF - device is off")
            return HVACMode.OFF

    @property
    def hvac_modes(self):
        """HVAC modes."""
        return [
            HVACMode.OFF,
            HVACMode.COOL,
            HVACMode.FAN_ONLY,
            HVACMode.DRY,
            HVACMode.HEAT,
            HVACMode.HEAT_COOL,
        ]

    # TODO:!
    # @property
    # def hvac_action(self):
    #     """Return the current running hvac operation."""
    #     # if self._target_temperature < self._current_temperature:
    #     #     return HVACAction.IDLE
    #     # return HVACAction.HEAT
    #     return HVACAction.IDLE

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
        return ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE | ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF

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
        if hvac_mode == HVACMode.OFF:
            _LOGGER.debug(f"turning off ac due to hvac_mode being set to {hvac_mode}")
            with self._act_and_update():
                self.ac.turn_off()
            _LOGGER.debug(
                f"ac has been turned off due hvac_mode being set to {hvac_mode}"
            )
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
        yield
        time.sleep(3)
        self.update()
        time.sleep(1)
        self.update()

    # data fetch mechanism
    def update(self):
        """Get the latest data."""
        _LOGGER.debug("Updating status using the client AC instance...")
        self.ac.update_status()
        _LOGGER.debug("Status updated using the client AC instance")
