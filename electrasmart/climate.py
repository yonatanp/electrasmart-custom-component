import time
import logging

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
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

DEFAULT_NAME = "ElectraSmart"

AC_SCHEMA = vol.Schema(
    {vol.Required(CONF_AC_ID): cv.string, vol.Required(CONF_AC_NAME, default=DEFAULT_NAME): cv.string}
)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_IMEI): cv.string,
        vol.Required(CONF_TOKEN): cv.string,
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


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the ElectraSmartClimate platform."""
    _LOGGER.debug("Setting up the ElectraSmart climate platform")
    imei = config.get(CONF_IMEI)
    token = config.get(CONF_TOKEN)
    acs = config.get(CONF_ACS)
    # TODO: api_verbosity config
    ElectraAPI.GLOBAL_VERBOSE = True

    for ac in acs:
        add_entities(
            [ElectraSmartClimate(ac, imei, token)]
            )


class ElectraSmartClimate(ClimateEntity):
    SID_RENEW_INTERVAL = 20

    def __init__(self, ac, imei, token):
        """Initialize the thermostat."""
        self._name = ac[CONF_AC_NAME]
        self.ac = AC(imei, token, ac[CONF_AC_ID])
        self._status = None
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
        diag_l2 = self.status.get("DIAG_L2", {}).get("DIAG_L2", {})
        value = diag_l2.get("I_CALC_AT") or diag_l2.get("I_RAT")
        if value is not None:
            value = int(value)
        _LOGGER.debug(f"value of current_temperature property: {value}")
        return value

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        value = self._operoper.get("SPT")
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
        # TODO: find the below
        "???1": HVAC_MODE_DRY,
        "???2": HVAC_MODE_HEAT,
        "???3": HVAC_MODE_HEAT_COOL,
    }

    HVAC_MODE_MAPPING_INV = {v: k for k, v in HVAC_MODE_MAPPING.items()}

    @property
    def hvac_mode(self):
        """Return hvac operation ie. heat, cool mode."""
        operoper = self._operoper
        if operoper.get("TURN_ON_OFF", "OFF") == "OFF" or "AC_MODE" not in operoper:
            return HVAC_MODE_OFF
        mode = operoper.get("AC_MODE")
        value = self.HVAC_MODE_MAPPING[mode]
        _LOGGER.debug(f"value of hvac_mode property: {value} (derived from {mode})")
        return value

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
        "AUTO": FAN_AUTO,
        "LOW": FAN_LOW,
        "???1": FAN_MEDIUM,
        "HIGH": FAN_HIGH,
    }

    FAN_MODE_MAPPING_INV = {v: k for k, v in FAN_MODE_MAPPING.items()}

    @property
    def fan_mode(self):
        """Returns the current fan mode (low, high, auto etc)"""
        operoper = self._operoper
        if operoper.get("TURN_ON_OFF", "OFF") == "OFF" or "FANSPD" not in operoper:
            return FAN_OFF
        mode = operoper.get("FANSPD")
        value = self.FAN_MODE_MAPPING[mode]
        _LOGGER.debug(f"value of fan_mode property: {value} (derived from {mode})")
        return value

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
        self._renew_sid_if_needed()
        self.ac.modify_oper(temperature=temperature)
        _LOGGER.debug(f"new temperature was set to {temperature}")

    def set_hvac_mode(self, hvac_mode):
        _LOGGER.debug(f"setting hvac mode to {hvac_mode}")
        _LOGGER.warning(self.HVAC_MODE_MAPPING)
        _LOGGER.warning(self.HVAC_MODE_MAPPING_INV)
        ac_mode = self.HVAC_MODE_MAPPING_INV[hvac_mode]
        _LOGGER.debug(f"setting hvac mode to {hvac_mode} (ac_mode {ac_mode})")
        self._renew_sid_if_needed()
        self.ac.modify_oper(ac_mode=ac_mode)
        _LOGGER.debug(f"hvac mode was set to {hvac_mode} (ac_mode {ac_mode})")

    def set_fan_mode(self, fan_mode):
        _LOGGER.debug(f"setting fan mode to {fan_mode}")
        fan_speed = self.FAN_MODE_MAPPING_INV[fan_mode]
        _LOGGER.debug(f"setting fan mode to {fan_mode} (fan_speed {fan_speed})")
        self._renew_sid_if_needed()
        self.ac.modify_oper(fan_speed=fan_speed)
        _LOGGER.debug(f"fan mode was set to {fan_mode} (fan_speed {fan_speed})")

    # data fetch mechanism

    @property
    def status(self):
        if self._status is None:
            _LOGGER.debug(f"updating status due to _status being None")
            self.update()
        return self._status

    def _renew_sid_if_needed(self):
        if self._last_sid_renew is None or time.time() - self._last_sid_renew > self.SID_RENEW_INTERVAL:
            _LOGGER.debug("renewing sid")
            self.ac.renew_sid()
            self._last_sid_renew = time.time()

    def update(self):
        """Get the latest data."""
        _LOGGER.debug("Updating status using the client AC instance...")
        self._renew_sid_if_needed()
        self._status = self.ac.status(check=False)
        _LOGGER.debug("Status updated using the client AC instance")

    @property
    def _operoper(self):
        return self.status.get("OPER", {}).get("OPER", {})
