"""Legacy coil controls retained but blocked pending safe override sequencing."""
from homeassistant.components.switch import SwitchEntity
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN

SWITCHES = [("dhw_enable", 4), ("circ_enable", 6)]


async def async_setup_entry(hass, entry, async_add_entities):
    # Neither legacy toggle describes both release/block override bits safely.
    async_add_entities([])


class ParadigmaSwitch(SwitchEntity):
    def __init__(self, hub, key, address, entry):
        self._hub = hub
        self._address = address
        self._entry_id = entry.entry_id
        self._attr_has_entity_name = True
        self._attr_translation_key = key
        self._attr_unique_id = f"{entry.entry_id}_switch_{address}"
        self._is_on = None

    @property
    def device_info(self):
        return DeviceInfo(identifiers={(DOMAIN, self._entry_id)}, name="Paradigma Heizung", manufacturer="Paradigma", model="SystaSmartC II")

    @property
    def available(self):
        return False

    @property
    def is_on(self):
        return self._is_on

    def turn_on(self, **kwargs):
        raise HomeAssistantError("Coil-Steuerung bis zur Bestätigung der Override-Sequenz gesperrt")

    def turn_off(self, **kwargs):
        raise HomeAssistantError("Coil-Steuerung bis zur Bestätigung der Override-Sequenz gesperrt")
