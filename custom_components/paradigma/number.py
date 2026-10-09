"""Verified setpoint controls; read-only holding 44/45 remain unexposed."""
from homeassistant.components.number import NumberEntity
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN, CONF_HK2
from .control import decode_temperature, encode_temperature, SetpointConfirmation

# Preserve definitions/identities; the hub approves only documented writers.
NUMBERS = [
    ("setpoint_flow_hk1", 2, 20, 80, 1, False),
    ("setpoint_flow_hk2", 3, 20, 80, 1, True),
    ("setpoint_buffer_top", 44, 20, 90, 0.5, False),
    ("setpoint_boiler", 45, 20, 90, 0.5, False),
]


async def async_setup_entry(hass, entry, async_add_entities):
    hub = hass.data[DOMAIN][entry.entry_id]
    entities = []
    hk2_active = entry.data.get(CONF_HK2, False)
    for n in NUMBERS:
        if n[5] and not hk2_active:
            continue
        if hub.can_write_register(n[1]):
            entities.append(ParadigmaNumber(hub, n[0], n[1], n[2], n[3], n[4], entry))
    async_add_entities(entities)


class ParadigmaNumber(NumberEntity):
    def __init__(self, hub, key, address, min_val, max_val, step, entry):
        self._hub = hub
        self._address = address
        self._entry_id = entry.entry_id
        self._attr_has_entity_name = True
        self._attr_translation_key = key
        self._attr_unique_id = f"{entry.entry_id}_num_{address}"
        self._attr_native_min_value = min_val
        self._attr_native_max_value = max_val
        self._attr_native_step = step
        self._attr_native_value = None
        self._attr_available = False
        self._confirmation = SetpointConfirmation()

    @property
    def device_info(self):
        return DeviceInfo(identifiers={(DOMAIN, self._entry_id)}, name="Paradigma Heizung", manufacturer="Paradigma", model="SystaSmartC II")

    @property
    def available(self):
        return self._attr_available and self._hub.can_write_register(self._address)

    @property
    def extra_state_attributes(self):
        return self._confirmation.attributes

    def update(self):
        self._attr_native_value = decode_temperature(self._hub.read_holding_registers(self._address, 1))
        self._attr_available = self._attr_native_value is not None
        self._confirmation.observe(self._attr_native_value)

    def set_native_value(self, value):
        try:
            raw = encode_temperature(value, self._attr_native_min_value,
                                     self._attr_native_max_value, self._attr_native_step)
        except ValueError as err:
            raise ServiceValidationError(str(err)) from err
        self._confirmation.begin(raw / 10)
        if not self._hub.write_register(self._address, raw):
            self._confirmation.fail()
            self._attr_native_value = None
            self._attr_available = False
            self.schedule_update_ha_state()
            raise HomeAssistantError("Sollwert wurde gesperrt oder der Modbus-Schreibzugriff ist fehlgeschlagen")
        self._confirmation.acknowledge()
        # A protocol acknowledgement is not an applied setpoint. Read the actual
        # holding value and keep it even when the controller clamps the request.
        self.update()
        self.schedule_update_ha_state()
        if self._attr_native_value is None:
            raise HomeAssistantError("Schreiben bestätigt, Rücklesen des Sollwerts fehlgeschlagen")
        if self._attr_native_value != raw / 10:
            raise HomeAssistantError("Schreiben bestätigt, rückgelesener Sollwert weicht ab")
