import time
import logging
import json
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
    CURRENT_HVAC_OFF,
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_DRY,
    HVAC_MODE_OFF,
    HVAC_MODE_COOL,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_DRY,
    HVAC_MODE_HEAT,
    HVAC_MODE_HEAT_COOL,
    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_FAN_MODE,
    SUPPORT_PRESET_MODE,
    FAN_OFF,
    FAN_AUTO,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_HIGH,
    PRESET_NONE,
    PRESET_SLEEP,
)

PRESET_SHABAT = "Shabat"
PRESET_IFEEL = "IFeel"
PRESET_SHABAT_SLEEP = "Shabat, Sleep"
PRESET_SHABAT_IFEEL = "Shabat, IFeel"
PRESET_SLEEP_IFEEL = "Sleep, IFeel"
PRESET_SHABAT_SLEEP_IFEEL = "Shabat, Sleep, IFeel"

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
    hass: HomeAssistantType,
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

    MODE_BY_NAME = {"IDLE": CURRENT_HVAC_IDLE}

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
        return [
            HVAC_MODE_OFF,
            HVAC_MODE_COOL,
            HVAC_MODE_FAN_ONLY,
            HVAC_MODE_DRY,
            HVAC_MODE_HEAT,
            HVAC_MODE_HEAT_COOL,
        ]

    @property
    def preset_modes(self):
        """PRESET modes."""
        return [
            PRESET_NONE,
            PRESET_SHABAT,
            PRESET_SLEEP,
            PRESET_SHABAT_SLEEP,
            PRESET_IFEEL,
            PRESET_SHABAT_IFEEL,
            PRESET_SLEEP_IFEEL,
            PRESET_SHABAT_SLEEP_IFEEL,
        ]

    PRESET_MODE_ID = {
        PRESET_NONE: 0,
        PRESET_SHABAT: 1,
        PRESET_SLEEP: 2,
        PRESET_SHABAT_SLEEP: 3,
        PRESET_IFEEL: 4,
        PRESET_SHABAT_IFEEL: 5,
        PRESET_SLEEP_IFEEL: 6,
        PRESET_SHABAT_SLEEP_IFEEL: 7,
    }

    PRESET_MODE_ID_INV = {v: k for k, v in PRESET_MODE_ID.items()}

    PRESET_MODE_MAPPING = {
        "SHABAT": PRESET_SHABAT,
        "SLEEP": PRESET_SLEEP,
        "IFEEL": PRESET_IFEEL,
    }

    PRESET_MODE_MAPPING_ARGS = {
        PRESET_SHABAT: "shabat",
        PRESET_SLEEP: "ac_sleep",
        PRESET_IFEEL: "ifeel",
    }

    PRESET_MODE_MAPPING_INV = {v: k for k, v in PRESET_MODE_MAPPING.items()}

    PRESET_MODE_MAPPING_ATTR = {p: p.lower() for p in PRESET_MODE_MAPPING.keys()}

    @property
    def preset_mode(self):
        """Returns the current preset mode"""
        if self.ac.status is None:
            _LOGGER.debug(f"preset_mode: status is None, returning None")
            return None
        if self.ac.status.is_on:
            preset_mode_bit = 0
            for p in self.PRESET_MODE_MAPPING.keys():
                if getattr(self.ac.status, self.PRESET_MODE_MAPPING_ATTR[p]) == "ON":
                    preset_mode_bit += self.PRESET_MODE_ID[self.PRESET_MODE_MAPPING[p]]
            preset_mode = self.PRESET_MODE_ID_INV[preset_mode_bit]
            _LOGGER.debug(f"preset_mode: returning {preset_mode}")
            return preset_mode
        else:
            _LOGGER.debug(f"preset_mode: returning PRESET_NONE - device is off")
            return PRESET_NONE

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
        return SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE | SUPPORT_PRESET_MODE

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

    def set_preset_mode(self, preset_mode):
        _LOGGER.debug(f"setting preset mode to {preset_mode}")
        if preset_mode not in self.preset_modes:
            _LOGGER.debug(f"preset mode '{preset_mode}' not in '{', '.join(self.preset_modes)}'")
            return

        kwargs = {
            self.PRESET_MODE_MAPPING_ARGS[self.PRESET_MODE_MAPPING[pm]]:
                "ON" if pm.lower() in preset_mode.lower() else "OFF"
            for pm in self.PRESET_MODE_MAPPING.keys()
            if pm != PRESET_NONE
        }

        self.ac.modify_oper(**kwargs)
        _LOGGER.debug(f"preset mode was set to {preset_mode}")

    @contextmanager
    def _act_and_update(self):
        yield
        time.sleep(2)
        self.update()
        time.sleep(3)
        self.update()

    # data fetch mechanism
    def update(self):
        """Get the latest data."""
        _LOGGER.debug("Updating status using the client AC instance...")
        self.ac.update_status()
        _LOGGER.debug("Status updated using the client AC instance")
