"""Offline regression tests using minimal HA interfaces, no installed packages."""
import asyncio
import ast
from itertools import product
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load_sensor_module():
    """Load production sensor code without importing integration setup or hub."""
    modules = {}
    for name in ('homeassistant', 'homeassistant.components',
                 'homeassistant.components.sensor', 'homeassistant.const',
                 'homeassistant.helpers', 'homeassistant.helpers.update_coordinator',
                 'homeassistant.helpers.entity', 'homeassistant.exceptions', 'peleo_test'):
        modules[name] = ModuleType(name)
    modules['peleo_test'].__path__ = [str(ROOT / 'custom_components/paradigma')]
    const = modules['homeassistant.const']
    for name, values in {
        'UnitOfTemperature': {'CELSIUS': '°C'},
        'UnitOfEnergy': {'KILO_WATT_HOUR': 'kWh'},
        'UnitOfPower': {'KILO_WATT': 'kW'},
        'UnitOfTime': {'HOURS': 'h'},
        'Platform': dict(SENSOR='sensor', NUMBER='number', SWITCH='switch', WATER_HEATER='water_heater'),
    }.items():
        setattr(const, name, SimpleNamespace(**values))
    const.CONF_HOST = 'host'
    const.CONF_PORT = 'port'
    const.CONF_SCAN_INTERVAL = 'scan_interval'
    sensor = modules['homeassistant.components.sensor']
    sensor.SensorEntity = type('SensorEntity', (), {})
    sensor.SensorDeviceClass = SimpleNamespace(TEMPERATURE='temperature', DURATION='duration', ENERGY='energy', POWER='power', ENUM='enum')
    sensor.SensorStateClass = SimpleNamespace(TOTAL_INCREASING='total_increasing', MEASUREMENT='measurement')

    class CoordinatorEntity:
        def __init__(self, coordinator):
            self.coordinator = coordinator

    class DataUpdateCoordinator:
        def __init__(self, hass, logger, **kwargs):
            self.hass = hass
            self.update_interval = kwargs['update_interval']
            self.config_entry = kwargs.get('config_entry')
            self.data = None
            self.last_update_success = True
            self.shutdown = False

        async def async_config_entry_first_refresh(self):
            if self.config_entry is None:
                raise RuntimeError('First refresh requires a config entry')
            try:
                self.data = await self._async_update_data()
            except UpdateFailed as err:
                self.last_update_success = False
                raise ConfigEntryNotReady(str(err)) from err

        async def async_refresh(self):
            try:
                self.data = await self._async_update_data()
                self.last_update_success = True
            except UpdateFailed:
                self.last_update_success = False

        async def async_shutdown(self):
            self.shutdown = True

    class UpdateFailed(Exception):
        pass

    class ConfigEntryNotReady(Exception):
        pass

    modules['homeassistant.exceptions'].ConfigEntryNotReady = ConfigEntryNotReady
    coordinator = modules['homeassistant.helpers.update_coordinator']
    coordinator.UpdateFailed = UpdateFailed
    coordinator.CoordinatorEntity = CoordinatorEntity
    coordinator.DataUpdateCoordinator = DataUpdateCoordinator
    modules['homeassistant.helpers.entity'].DeviceInfo = dict
    with patch.dict(sys.modules, modules):
        spec = importlib.util.spec_from_file_location('peleo_test.sensor', ROOT / 'custom_components/paradigma/sensor.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


SENSOR = load_sensor_module()


class FakeHub:
    def __init__(self, counters=None):
        self.calls = []
        self.coordinator = None
        self.counters = {27: [0, 4294], 29: [0, 123]} if counters is None else counters

    def read_input_registers(self, address, count):
        self.calls.append(('input', address, count))
        return [200]

    def read_holding_registers(self, address, count):
        self.calls.append(('holding', address, count))
        return self.counters.get(address) if count == 2 else [0]


class FakeHass:
    def __init__(self, hub):
        self.data = {'paradigma': {'existing-entry': hub}}

    async def async_add_executor_job(self, func, *args):
        return func(*args)


class PeleoTests(unittest.TestCase):
    def entity(self, key, raw):
        definition = next(d for d in SENSOR.SENSOR_DEFINITIONS if d[0] == key)
        typ = definition[4] if definition[4] in ('input', 'holding_32') else 'holding'
        coordinator = SimpleNamespace(data={f'{typ}_{definition[5]}': raw})
        return SENSOR.ParadigmaSensor(coordinator, SimpleNamespace(entry_id='existing-entry'), definition)

    def test_mapping_and_unique_ids(self):
        definitions = SENSOR.SENSOR_DEFINITIONS
        self.assertEqual(len({(d[4], d[5]) for d in definitions}), len(definitions))
        for key, typ, address in (('boiler_hours', 'holding_32', 27), ('boiler_starts', 'holding_32', 29), ('status_boiler', 'holding_status_boiler', 41)):
            matching = [d for d in definitions if d[0] == key]
            self.assertEqual(len(matching), 1)
            self.assertEqual(matching[0][4:7], (typ, address, None))
            self.assertEqual(self.entity(key, 0)._attr_unique_id, f'existing-entry_{typ}_{address}')
        self.assertFalse(any(d[0].startswith(('wood_', 'pellet_')) or d[5] in (42, 43) for d in definitions))

    def test_uint32_word_order(self):
        for words, expected in (([0, 4294], 4294), ([4294, 0], 281411584), ([1, 2], 65538), ([0, 0], 0), ([65535, 65534], 4294967294)):
            with self.subTest(words=words):
                self.assertEqual(SENSOR.decode_uint32(words), expected)

    def test_invalid_uint32_responses(self):
        for words in (None, 42, True, "ab", {0: 1, 1: 2}, [], [0], [0, 1, 2], [65535, 65535], [-1, 0], [65536, 0], [True, 0], [0, '1'], [0, None], [0, 1.0]):
            with self.subTest(words=words):
                self.assertIsNone(SENSOR.decode_uint32(words))

    def test_counter_sentinels_and_bounds(self):
        for key in ('boiler_hours', 'boiler_starts'):
            for raw in (0, 4294, 32767, 32768, 65535, 65536, 4294967294):
                with self.subTest(key=key, raw=raw):
                    value = self.entity(key, raw).native_value
                    self.assertEqual(value, raw)
                    self.assertIs(type(value), int)
            for raw in (None, -1, 4294967295, 4294967296, True, '4294', 4294.0):
                self.assertIsNone(self.entity(key, raw).native_value)

    def test_valid_words_with_16bit_sentinel_values(self):
        for word in (32767, 32768, 65535):
            self.assertEqual(SENSOR.decode_uint32([0, word]), word)
            self.assertEqual(SENSOR.decode_uint32([word, 0]), word << 16)

    def test_uint16_invalid_and_signed_temperature(self):
        for key in ('outdoor_temp', 'status_boiler', 'solar_power'):
            for raw in (None, -1, 65536, 32767, 32768, 65535, True, '0', 0.0):
                self.assertIsNone(self.entity(key, raw).native_value)
        self.assertEqual(self.entity('outdoor_temp', 65486).native_value, -5.0)
        self.assertEqual(self.entity('outdoor_temp', 0).native_value, 0)
        self.assertEqual(self.entity('status_boiler', 0).native_value, 'off')
        self.assertEqual(self.entity('status_boiler', 99).native_value, '99')

    def test_setup_and_reads_ignore_legacy_wood_option(self):
        options = ('solar_installed', 'hk2_installed', 'pool_installed', 'room_sensor_installed', 'boiler_installed', 'wood_installed')
        configs = [{}] + [dict(zip(options, values)) for values in product((False, True), repeat=len(options))]
        for config in configs:
            with self.subTest(config=config):
                hub = FakeHub()
                entities = []
                entry = SimpleNamespace(entry_id='existing-entry', data=config)
                asyncio.run(SENSOR.async_setup_entry(FakeHass(hub), entry, entities.extend))
                keys = [e._key for e in entities]
                self.assertEqual(len({e._attr_unique_id for e in entities}), len(entities))
                for key in ('boiler_hours', 'boiler_starts', 'status_boiler'):
                    self.assertEqual(keys.count(key), 1)
                for call in (('holding', 27, 2), ('holding', 29, 2), ('holding', 41, 1)):
                    self.assertEqual(hub.calls.count(call), 1)
                self.assertFalse(any(address in (14, 15, 16, 42, 43) for _, address, _ in hub.calls))

    def test_translations_match_sensor_profile(self):
        keys = {d[0] for d in SENSOR.SENSOR_DEFINITIONS}
        source = None
        for name in ('strings.json', 'translations/de.json', 'translations/en.json'):
            data = json.loads((ROOT / 'custom_components/paradigma' / name).read_text())
            self.assertEqual(set(data['entity']['sensor']), keys)
            for section, step in (('config', 'user'), ('options', 'init')):
                fields = data[section]['step'][step]['data']
                self.assertNotIn('wood_installed', fields)
                self.assertIn('PELEO 14', fields['boiler_installed'])
            self.assertIn('name', data['config']['step']['user']['data'])
            if source is None:
                source = data
            else:
                self.assertEqual(self.translation_paths(data), self.translation_paths(source))
                if name.endswith('en.json'):
                    self.assertEqual(data, source)

    @staticmethod
    def translation_paths(data, prefix=()):
        if isinstance(data, dict):
            return set().union(*(PeleoTests.translation_paths(value, prefix + (key,)) for key, value in data.items()))
        return {prefix}

    def test_all_status_values_have_translations(self):
        for name in ('strings.json', 'translations/de.json', 'translations/en.json'):
            data = json.loads((ROOT / 'custom_components/paradigma' / name).read_text())
            for key, table in (('status_hk1', SENSOR.STATUS_HK), ('status_hk2', SENSOR.STATUS_HK), ('status_ww', SENSOR.STATUS_WW), ('status_circ', SENSOR.STATUS_CIRC), ('status_solar', SENSOR.STATUS_SOLAR), ('status_pool', SENSOR.STATUS_POOL), ('status_boiler', SENSOR.STATUS_BOILER)):
                self.assertEqual(set(data['entity']['sensor'][key]['state']), set(table.values()))

    def test_other_platform_translation_keys(self):
        for filename, variable, platform in (('number.py', 'NUMBERS', 'number'), ('switch.py', 'SWITCHES', 'switch')):
            tree = ast.parse((ROOT / 'custom_components/paradigma' / filename).read_text())
            node = next(n for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == variable for t in n.targets))
            expected = {ast.literal_eval(item.elts[0]) for item in node.value.elts}
            for name in ('strings.json', 'translations/de.json', 'translations/en.json'):
                data = json.loads((ROOT / 'custom_components/paradigma' / name).read_text())
                self.assertEqual(set(data['entity'][platform]), expected)
                self.assertEqual(set(data['entity']['water_heater']), {'dhw'})

    def test_identity_survives_option_changes(self):
        # Check identity inputs across reloads, not HA's registry implementation.
        old_registry = {
            'existing-entry_holding_32_27': 'sensor.meine_pelletstunden',
            'existing-entry_holding_32_29': 'sensor.meine_kesselstarts',
            'existing-entry_holding_status_boiler_41': 'sensor.mein_kesselstatus',
        }
        snapshot = old_registry.copy()
        for config in ({'wood_installed': True, 'boiler_installed': False}, {'boiler_installed': True}, {}):
            entities = []
            asyncio.run(SENSOR.async_setup_entry(FakeHass(FakeHub()), SimpleNamespace(entry_id='existing-entry', data=config), entities.extend))
            boiler = [e for e in entities if e._key in ('boiler_hours', 'boiler_starts', 'status_boiler')]
            self.assertEqual({e._attr_unique_id for e in boiler}, set(snapshot))
            self.assertTrue(all(e.device_info['identifiers'] == {('paradigma', 'existing-entry')} for e in boiler))
            self.assertTrue(all(not hasattr(e, 'entity_id') for e in boiler))
        self.assertEqual(old_registry, snapshot)

    def test_solar_uint32_scaling_preserved(self):
        self.assertAlmostEqual(self.entity('solar_total', 65535).native_value, 6553.5)
        self.assertIsNone(self.entity('solar_total', 4294967295).native_value)

    def test_coordinator_discards_invalid_counter(self):
        hub = FakeHub({27: [65535, 65535], 29: [0]})
        coordinator = SENSOR.ParadigmaDataCoordinator(FakeHass(hub), hub, {})
        data = asyncio.run(coordinator._async_update_data())
        self.assertIsNone(data['holding_32_27'])
        self.assertNotIn('holding_32_29', data)


if __name__ == '__main__':
    unittest.main()
