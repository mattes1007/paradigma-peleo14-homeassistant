"""Single register catalogue. TH-3000 V1.1; legacy identities are immutable."""
from dataclasses import dataclass
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import UnitOfTemperature, UnitOfEnergy, UnitOfPower, UnitOfTime
from .const import CONF_ROOM, CONF_HK2, CONF_BOILER, CONF_SOLAR, CONF_POOL

MODELS = ("systacomfort_ii", "compact_c", "legacy_unverified", "systasmartc_ii")
VERIFIED_MODELS = MODELS[:2]
COMPONENTS = ("general", "boiler", "buffer", "hk1", "hk2", "dhw", "circulation", "solar", "pool", "room")
SENSOR_DEFINITIONS = [


    ("outdoor_temp", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, 0.1, "input", 0, None),
    ("flow_hk1", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, 0.1, "input", 1, None),
    ("return_hk1", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, 0.1, "input", 2, None),
    ("dhw_temp", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, 0.1, "input", 3, None),
    ("buffer_top", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, 0.1, "input", 4, None),
    ("buffer_bottom", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, 0.1, "input", 5, None),
    ("circ_return_temp", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, 0.1, "input", 6, None),

    ("room_temp_hk1", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, 0.1, "input", 9, CONF_ROOM),
    ("room_temp_hk2", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, 0.1, "input", 10, CONF_ROOM),

    ("flow_hk2", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, 0.1, "input", 7, CONF_HK2),
    ("return_hk2", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, 0.1, "input", 8, CONF_HK2),

    ("boiler_flow", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, 0.1, "input", 12, CONF_BOILER),
    ("boiler_return", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, 0.1, "input", 13, CONF_BOILER),
    ("boiler_hours", UnitOfTime.HOURS, SensorDeviceClass.DURATION, 1, "holding_32", 27, None),
    ("boiler_starts", None, None, 1, "holding_32", 29, None),



    ("collector_temp", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, 0.1, "input", 11, CONF_SOLAR),
    ("solar_power", UnitOfPower.KILO_WATT, SensorDeviceClass.POWER, 0.1, "holding", 19, CONF_SOLAR),
    ("solar_day", UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, 0.1, "holding", 20, CONF_SOLAR),
    ("solar_total", UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, 0.1, "holding_32", 21, CONF_SOLAR),

    ("pool_temp", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, 0.1, "input", 19, CONF_POOL),
    ("pool_flow", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, 0.1, "input", 20, CONF_POOL),
    ("pool_return", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, 0.1, "input", 21, CONF_POOL),

    ("status_ww", None, None, 1, "holding_status_ww", 34, None),
    ("status_circ", None, None, 1, "holding_status_circ", 35, None),
    ("status_hk1", None, None, 1, "holding_status_hk", 36, None),
    ("status_hk2", None, None, 1, "holding_status_hk", 37, CONF_HK2),
    ("status_solar", None, None, 1, "holding_status_solar", 39, CONF_SOLAR),
    ("status_pool", None, None, 1, "holding_status_pool", 40, CONF_POOL),
    ("status_boiler", None, None, 1, "holding_status_boiler", 41, None),
]
SENSOR_DEFINITIONS += [
    ("external_flow_hk1", "°C", SensorDeviceClass.TEMPERATURE, .1, "holding", 2, None),
    ("target_buffer_top", "°C", SensorDeviceClass.TEMPERATURE, .1, "holding", 44, None),
    ("target_boiler", "°C", SensorDeviceClass.TEMPERATURE, .1, "holding", 45, None),
]

@dataclass(frozen=True)
class Register:
    key: str
    definition: tuple
    component: str
    name_de: str
    name_en: str
    models: tuple = VERIFIED_MODELS
    readable: bool = True
    default: bool = True
    source: str = "TH-3000 V1.1, appendix A (15–19)"
    validity: str = "16-bit: reject 0x8000/0x7fff/0xffff; 32-bit: reject 0xffffffff"

    @property
    def description(self):
        return "External temporary flow override, not internally calculated target" if self.key == "external_flow_hk1" else self.name_en

    @property
    def writable(self):
        return self.kind == "holding" and any(v[1] == self.definition[5] for v in CONTROLS.values())

    @property
    def prerequisites(self):
        return (self.component,) + (("room",) if self.definition[6] == CONF_ROOM else ())

    @property
    def availability(self):
        return "Successful coordinator response and valid decoded value"

    @property
    def kind(self):
        return self.definition[4] if self.definition[4] in ("input", "holding_32") else "holding"

    @property
    def datatype(self):
        return "uint32" if self.kind == "holding_32" else ("int16" if self.definition[2] == SensorDeviceClass.TEMPERATURE else "uint16")


def component(key):
    if "hk2" in key: return "hk2"
    if "hk1" in key: return "hk1"
    if "boiler" in key: return "boiler"
    if "buffer" in key: return "buffer"
    if "circ" in key: return "circulation"
    if "solar" in key or "collector" in key: return "solar"
    if "pool" in key: return "pool"
    if key in ("dhw_temp", "status_ww"): return "dhw"
    return "general"

NAMES = {'outdoor_temp': ('Außentemperatur', 'Outdoor Temperature'), 'flow_hk1': ('Vorlauf HK1', 'Flow HK1'), 'return_hk1': ('Rücklauf HK1', 'Return HK1'), 'dhw_temp': ('Warmwasser Temperatur', 'DHW Temperature'), 'buffer_top': ('Puffer Oben', 'Buffer Top'), 'buffer_bottom': ('Puffer Unten', 'Buffer Bottom'), 'circ_return_temp': ('Rücklauf Zirkulation', 'Circulation Return'), 'room_temp_hk1': ('Raumtemperatur HK1', 'Room Temp HK1'), 'room_temp_hk2': ('Raumtemperatur HK2', 'Room Temp HK2'), 'boiler_flow': ('Kessel Vorlauf', 'Boiler Flow'), 'boiler_return': ('Kessel Rücklauf', 'Boiler Return'), 'boiler_hours': ('PELEO 14 Betriebsstunden', 'PELEO 14 operating hours'), 'boiler_starts': ('PELEO 14 Kesselstarts', 'PELEO 14 boiler starts'), 'flow_hk2': ('Vorlauf HK2', 'Flow HK2'), 'return_hk2': ('Rücklauf HK2', 'Return HK2'), 'collector_temp': ('Kollektortemperatur', 'Collector Temperature'), 'solar_power': ('Solar Leistung', 'Solar Power'), 'solar_day': ('Solar Tagesertrag', 'Solar Yield Day'), 'solar_total': ('Solar Gesamtertrag', 'Solar Yield Total'), 'pool_temp': ('Pool Temperatur', 'Pool Temperature'), 'pool_flow': ('Pool Vorlauf', 'Pool Flow'), 'pool_return': ('Pool Rücklauf', 'Pool Return'), 'status_hk1': ('Status Heizkreis 1', 'Status HK1'), 'status_hk2': ('Status Heizkreis 2', 'Status HK2'), 'status_ww': ('Status Warmwasser', 'Status DHW'), 'status_circ': ('Status Zirkulation', 'Status Circulation'), 'status_solar': ('Status Solar', 'Status Solar'), 'status_pool': ('Status Pool', 'Status Pool'), 'status_boiler': ('PELEO 14 Kesselstatus', 'PELEO 14 boiler status'), 'external_flow_hk1': ('Externe Vorlauf-Sollwertvorgabe HK1', 'External flow target HC1'), 'target_buffer_top': ('Solltemperatur Puffer oben', 'Buffer top target temperature'), 'target_boiler': ('Kesselsolltemperatur', 'Boiler target temperature')}
REGISTERS = {d[0]: Register(d[0], d, component(d[0]), *NAMES[d[0]], default=d[0] not in ("external_flow_hk1", "target_buffer_top", "target_boiler")) for d in SENSOR_DEFINITIONS}
# Write metadata is separate from sensor selection; raw prerequisites aren't entities.
CONTROLS = {"flow_hk1": ("hk1", 2, 200, 800, 10), "flow_hk2": ("hk2", 3, 200, 800, 10), "dhw_target": ("dhw", 8, 300, 700, 1)}
RAW_PREREQUISITES = {"flow_hk1": ("holding", 9, 1), "flow_hk2": ("holding", 10, 1), "dhw_target": ("coil", 4, 2)}

def legacy_sensors(data):
    return [d[0] for d in SENSOR_DEFINITIONS if REGISTERS[d[0]].default and (not d[6] or data.get(d[6]))]

def selected_sensors(data):
    if "sensors" not in data: return legacy_sensors(data)
    return [k for k in data["sensors"] if k in REGISTERS and (data.get("model") in VERIFIED_MODELS or REGISTERS[k].default) and REGISTERS[k].component in data.get("components", []) and (not REGISTERS[k].definition[6] == CONF_ROOM or "room" in data.get("components", []))]

def legacy_control_functions(data):
    """The functions actually exposed by v1, never inferred from new selections."""
    unit_id = data.get("slave_id", 1)
    if data.get("allow_control") is not True or type(unit_id) is not int or unit_id != 1:
        return []
    return ["flow_hk1", *(["flow_hk2"] if data.get(CONF_HK2) else []), "dhw_target"]


def migrate_data(data):
    result = dict(data)
    result.setdefault("model", "legacy_unverified")
    result.setdefault("sensors", legacy_sensors(data))
    result.setdefault("components", list(dict.fromkeys([REGISTERS[k].component for k in result["sensors"]] + (["room"] if data.get(CONF_ROOM) else []))))
    # Capture the v1 grant before modular options can change components/controls.
    # Already modular entries without evidence must not invent a legacy grant.
    legacy = legacy_control_functions(data) if "controls" not in data else []
    result.setdefault("legacy_control_functions", legacy.copy())
    result.setdefault("controls", legacy.copy())
    result.setdefault("legacy_control", bool(legacy))
    return result


def allowed_addresses(data):
    """Read selections and a legacy boolean can never broaden write authority."""
    if "controls" not in data:
        return {CONTROLS[k][1] for k in legacy_control_functions(data)}
    selected = data.get("controls")
    if not isinstance(selected, (list, tuple)):
        return set()
    if data.get("model") not in VERIFIED_MODELS:
        if data.get("legacy_control") is not True:
            return set()
        original = data.get("legacy_control_functions", [])
        if not isinstance(original, (list, tuple)):
            return set()
        selected = [key for key in selected if key in original]
    return {v[1] for k, v in CONTROLS.items()
            if k in selected and v[0] in data.get("components", [])}

COMPONENT_NAMES = {
    "general": ("Allgemein / Außentemperatur", "General / outdoor temperature"),
    "boiler": ("Kessel / Pelletheizung", "Boiler / pellet heating"),
    "buffer": ("Pufferspeicher", "Buffer storage"),
    "hk1": ("Heizkreis 1", "Heating circuit 1"), "hk2": ("Heizkreis 2", "Heating circuit 2"),
    "dhw": ("Warmwasser", "Domestic hot water"), "circulation": ("Zirkulation", "Circulation"),
    "solar": ("Solarthermie", "Solar thermal"), "pool": ("Schwimmbad", "Pool"), "room": ("Raumfühler", "Room sensors"),
}
