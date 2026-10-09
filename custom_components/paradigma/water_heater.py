"""Verified DHW target only; legacy on/off coil commands remain blocked."""
from homeassistant.components.water_heater import WaterHeaterEntity, WaterHeaterEntityFeature
from homeassistant.const import UnitOfTemperature, ATTR_TEMPERATURE, PRECISION_TENTHS
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN
from .control import decode_temperature, encode_temperature, SetpointConfirmation


async def async_setup_entry(hass, entry, async_add_entities):
    hub = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ParadigmaWaterHeater(hub, entry)] if hub.can_write_register(8) else [])


class ParadigmaWaterHeater(WaterHeaterEntity):
    def __init__(self, hub, entry):
        self._hub = hub
        self._entry_id = entry.entry_id
        self._attr_has_entity_name = True
        self._attr_translation_key = "dhw"
        self._attr_unique_id = f"{entry.entry_id}_wh_ww"
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_precision = PRECISION_TENTHS
        self._attr_target_temperature_step = 0.1
        self._attr_supported_features = WaterHeaterEntityFeature.TARGET_TEMPERATURE
        self._attr_min_temp = 30
        self._attr_max_temp = 70
        self._attr_current_operation = None
        self._current_temp = None
        self._target_temp = None
        self._attr_available = False
        self._confirmation = SetpointConfirmation()

    @property
    def device_info(self):
        return DeviceInfo(identifiers={(DOMAIN, self._entry_id)}, name="Paradigma Heizung", manufacturer="Paradigma", model="SystaSmartC II")

    @property
    def available(self):
        return self._attr_available and self._hub.can_write_register(8)

    @property
    def current_temperature(self):
        return self._current_temp

    @property
    def target_temperature(self):
        return self._target_temp

    @property
    def extra_state_attributes(self):
        return self._confirmation.attributes

    def update(self):
        self._current_temp = decode_temperature(self._hub.read_input_registers(3, 1))
        self._update_target()

    def _update_target(self):
        self._target_temp = decode_temperature(self._hub.read_holding_registers(8, 1))
        self._attr_available = self._target_temp is not None
        self._confirmation.observe(self._target_temp)

    def set_temperature(self, **kwargs):
        try:
            raw = encode_temperature(kwargs.get(ATTR_TEMPERATURE), 30, 70, 0.1)
        except ValueError as err:
            raise ServiceValidationError(str(err)) from err
        self._confirmation.begin(raw / 10)
        if not self._hub.write_register(8, raw):
            self._confirmation.fail()
            self._target_temp = None
            self._attr_available = False
            self.schedule_update_ha_state()
            raise HomeAssistantError("Warmwasser-Sollwert gesperrt oder Schreibfehler; Freigabe-Override muss bestätigt sein")
        self._confirmation.acknowledge()
        self._update_target()
        self.schedule_update_ha_state()
        if self._target_temp is None:
            raise HomeAssistantError("Schreiben bestätigt, Rücklesen des Warmwasser-Sollwerts fehlgeschlagen")
        if self._target_temp != raw / 10:
            raise HomeAssistantError("Schreiben bestätigt, rückgelesener Warmwasser-Sollwert weicht ab")

    def turn_on(self, **kwargs):
        raise HomeAssistantError("Warmwasser-Coil-Steuerung bis zur Bestätigung der Override-Sequenz gesperrt")

    def turn_off(self, **kwargs):
        raise HomeAssistantError("Warmwasser-Coil-Steuerung bis zur Bestätigung der Override-Sequenz gesperrt")
