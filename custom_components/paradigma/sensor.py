"""Sensors for Paradigma."""
from homeassistant.components.sensor import SensorEntity, SensorEntityDescription, SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfTemperature, UnitOfEnergy, UnitOfPower, UnitOfTime
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.entity import DeviceInfo
from datetime import timedelta
import logging
from .configuration import scan_interval
from .const import DOMAIN, CONF_SOLAR, CONF_HK2, CONF_POOL, CONF_ROOM, CONF_BOILER

_LOGGER = logging.getLogger(__name__)

# Preserve the previous 16-bit sentinel policy; do not apply it to uint32.
INVALID_UINT16 = frozenset({0x7FFF, 0x8000, 0xFFFF})


def is_valid_uint(value, bits):
    """Validate a raw unsigned register value without coercing malformed data."""
    return type(value) is int and 0 <= value < (1 << bits)


def decode_uint32(registers):
    """Decode high word first, pending confirmation from real PELEO values.

    Individual words may equal 16-bit sentinels in a valid uint32 counter.
    Only the complete 0xFFFFFFFF value is the known invalid uint32 sentinel.
    """
    if not isinstance(registers, (list, tuple)) or len(registers) != 2:
        return None
    if not all(is_valid_uint(word, 16) for word in registers):
        return None
    value = (registers[0] << 16) | registers[1]
    return None if value == 0xFFFFFFFF else value



STATUS_HK = { 
    0: "off", 1: "heating", 2: "push", 3: "hold", 
    4: "blocked", 5: "startup", 6: "frost", 7: "screed", 
    8: "cooling_excess", 9: "manual", 10: "emergency", 
    11: "not_installed", 12: "cooling_active" 
}

STATUS_WW = { 
    0: "no_demand", 1: "loading", 2: "frost", 3: "waiting", 
    4: "pump_runon", 5: "buffer_hot", 
    6: "wait_draw", 7: "draw_off", 8: "startup", 
    9: "manual", 10: "circ_active", 11: "circ_runon", 
    12: "circ_lock", 13: "blocked_smarthome" 
}

STATUS_POOL = { 
    0: "no_extension", 1: "off", 2: "blocked", 3: "warm_enough", 
    4: "frost", 5: "heating_normal", 6: "heating_comfort", 
    7: "solar_excess", 8: "blocked_buffer_cold", 
    9: "blocked_ww_prio", 10: "cooling" 
}

STATUS_CIRC = { 
    0: "unused", 1: "runon", 2: "blocked", 3: "off", 
    4: "blocked_sensor", 5: "on", 6: "frost", 7: "blocked_smarthome" 
}

STATUS_BOILER = { 
    0: "off", 1: "on", 2: "on_heating", 3: "loading_buffer", 
    4: "blocked", 5: "cooling_hp", 6: "ww_prep" 
}

STATUS_SOLAR = { 
    0: "waiting", 1: "frost", 2: "push", 3: "delay", 
    4: "loading", 5: "storage_full", 6: "collector_overheat", 
    7: "manual", 8: "measuring", 9: "emergency" 
}


from .catalog import SENSOR_DEFINITIONS, REGISTERS, selected_sensors, allowed_addresses


async def async_setup_entry(hass, entry, async_add_entities):
    hub = hass.data[DOMAIN][entry.entry_id]
    coordinator = hub.coordinator
    if coordinator is None:
        coordinator = ParadigmaDataCoordinator(hass, hub, entry.data, entry)
        await coordinator.async_config_entry_first_refresh()
        hub.coordinator = coordinator
    
    entities = []
    for s in SENSOR_DEFINITIONS:
        if s[0] not in selected_sensors(entry.data):
            continue
        entities.append(ParadigmaSensor(coordinator, entry, s))
    async_add_entities(entities)

class ParadigmaDataCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, hub, config, entry=None):
        super().__init__(
            hass, _LOGGER, name="ParadigmaSensors", config_entry=entry,
            update_interval=timedelta(seconds=scan_interval(config)),
            always_update=False,
        )
        self.hub = hub
        self.config = config
        # Derive the plan from the entity definitions; no address/type duplication.
        self._read_plan = {}
        for definition in SENSOR_DEFINITIONS:
            _, _, _, _, register_type, address, required = definition
            if definition[0] not in selected_sensors(config):
                continue
            kind = "input" if register_type == "input" else (
                "holding_32" if register_type == "holding_32" else "holding"
            )
            self._read_plan[(kind, address)] = 2 if kind == "holding_32" else 1

        for address in allowed_addresses(config):
            self._read_plan[("holding", address)] = 1
        if 8 in allowed_addresses(config):
            self._read_plan[("input", 3)] = 1

    async def _async_update_data(self):
        # All synchronous reads run outside the event loop, in one executor job.
        return await self.hass.async_add_executor_job(self._read_data)

    def _read_data(self):
        data = {}
        responses = 0
        for (kind, address), count in self._read_plan.items():
            reader = self.hub.read_input_registers if kind == "input" else self.hub.read_holding_registers
            values = reader(address, count)
            if not isinstance(values, (list, tuple)) or len(values) != count:
                continue
            if not all(is_valid_uint(value, 16) for value in values):
                continue
            # A sentinel is invalid measurement data, but a valid transport response.
            responses += 1
            data[f"{kind}_{address}"] = decode_uint32(values) if count == 2 else values[0]
        if self._read_plan and not responses:
            raise UpdateFailed("No valid Modbus responses from the configured sensor registers")
        return data

class ParadigmaSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, entry, definition):
        super().__init__(coordinator)
        self._key = definition[0]
        self._unit = definition[1]
        self._dev_class = definition[2]
        self._factor = definition[3]
        self._type = definition[4]
        self._reg_idx = definition[5]
        self._entry_id = entry.entry_id
        self.entity_description = SensorEntityDescription(
            key=self._key, translation_key=self._key,
            native_unit_of_measurement=self._unit, device_class=self._dev_class,
        )
        
        self._attr_has_entity_name = True
        self._attr_translation_key = self._key
        self._attr_unique_id = f"{entry.entry_id}_{self._type}_{self._reg_idx}"
        
        if self._dev_class == SensorDeviceClass.ENERGY:
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        elif self._dev_class in [SensorDeviceClass.TEMPERATURE, SensorDeviceClass.POWER]:
            self._attr_state_class = SensorStateClass.MEASUREMENT
        else:
            self._attr_state_class = None

    @property
    def device_info(self):
        return DeviceInfo(identifiers={(DOMAIN, self._entry_id)})

    @property
    def available(self):
        if not self.coordinator.last_update_success or self.coordinator.data is None:
            return False
        kind = "input" if self._type == "input" else (
            "holding_32" if self._type == "holding_32" else "holding"
        )
        return self.native_value is not None

    @property
    def native_value(self):
        if "input" in self._type:
            key = f"input_{self._reg_idx}"
        elif "holding_32" in self._type:
            key = f"holding_32_{self._reg_idx}"
        else:
            key = f"holding_{self._reg_idx}"
            
        raw = (self.coordinator.data or {}).get(key)
        
        if self._type == "holding_32":
            if not is_valid_uint(raw, 32) or raw == 0xFFFFFFFF:
                return None
        elif not is_valid_uint(raw, 16) or raw in INVALID_UINT16:
            return None


        if getattr(self.coordinator, "config", {}).get("model") in ("systacomfort_ii", "compact_c"):
            tables = {
                "holding_status_hk": {0: "off", 1: "outdoor_limit", 2: "room_limit", 3: "buffer_block", 4: "dhw_priority", 6: "frost", 7: "solar_excess", 8: "preheat", 9: "normal", 10: "comfort", 11: "reduced", 16: "station_dhw", 17: "screed"},
                "holding_status_boiler": {0: "off", 1: "manual", 2: "ww_prep", 3: "on_heating", 4: "wood_block", 5: "stove_block", 6: "outdoor_block", 7: "cooling_hp", 8: "combi_dhw"},
                "holding_status_pool": {0: "pump_block", 3: "buffer_block", 4: "dhw_priority", 7: "solar_excess", 12: "warm_enough", 13: "schedule_block", 14: "normal", 15: "comfort"},
            }
            if self._type in tables:
                return tables[self._type].get(raw, str(raw))

        if "status_hk" in self._type: return STATUS_HK.get(raw, str(raw))
        if "status_ww" in self._type: return STATUS_WW.get(raw, str(raw))
        if "status_circ" in self._type: return STATUS_CIRC.get(raw, str(raw))
        if "status_solar" in self._type: return STATUS_SOLAR.get(raw, str(raw))
        if "status_boiler" in self._type: return STATUS_BOILER.get(raw, str(raw))
        if "status_pool" in self._type: return STATUS_POOL.get(raw, str(raw))

        if self._unit == UnitOfTemperature.CELSIUS:
             if raw > 32767: raw -= 65536
        
        return round(raw * self._factor, 1) if self._unit == UnitOfTemperature.CELSIUS else raw * self._factor

    @property
    def extra_state_attributes(self):
        return {"component": REGISTERS[self._key].component, "register_key": self._key}

    @property
    def native_unit_of_measurement(self):
        if self._dev_class is None and self._unit is None:
            return None
        return self._unit
    
    @property
    def options(self):
        if self._unit is not None or "status" not in self._type:
            return None
        table = {"holding_status_hk": STATUS_HK, "holding_status_ww": STATUS_WW,
                 "holding_status_circ": STATUS_CIRC, "holding_status_solar": STATUS_SOLAR,
                 "holding_status_boiler": STATUS_BOILER, "holding_status_pool": STATUS_POOL}.get(self._type, {})
        # Include the actual value so unknown/new firmware codes remain visible.
        values = set(table.values())
        if self.native_value is not None:
            values.add(self.native_value)
        return sorted(values)

    @property
    def device_class(self):
        if self._dev_class:
            return self._dev_class

        if self._unit is None and "status" in self._type:
            return SensorDeviceClass.ENUM
        return None
