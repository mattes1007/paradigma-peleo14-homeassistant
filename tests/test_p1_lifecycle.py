"""Exercise production setup/unload functions with offline HA boundaries."""
import ast
import asyncio
import logging
from pathlib import Path
from types import SimpleNamespace
import unittest

from test_peleo_config_flow import FLOW
from test_peleo_sensors import SENSOR, FakeHub, FakeHass

ROOT = Path(__file__).resolve().parents[1]


class ConfigEntryNotReady(Exception):
    pass


class ConfigEntryError(Exception):
    pass


class Hub(FakeHub):
    instances = []
    connect_ok = True
    no_responses = False

    def __init__(self, *args, allow_control=False, permission_check=None):
        super().__init__()
        self._allow_control = allow_control is True
        self._permission_check = permission_check
        self.closed = False
        Hub.instances.append(self)

    @property
    def control_enabled(self):
        return self._allow_control and (self._permission_check is None or self._permission_check() is True)

    def revoke_control(self):
        self._allow_control = False

    def connect(self):
        return self.connect_ok

    def close(self):
        self.closed = True

    def read_input_registers(self, address, count):
        return None if self.no_responses else super().read_input_registers(address, count)

    def read_holding_registers(self, address, count):
        return None if self.no_responses else super().read_holding_registers(address, count)


def load_setup_functions():
    tree = ast.parse((ROOT / 'custom_components/paradigma/__init__.py').read_text())
    namespace = dict(
        ConfigEntry=object, HomeAssistant=object,
        CONF_HOST='host', CONF_PORT='port', CONF_NAME='name',
        CONF_SLAVE_ID='slave_id', DOMAIN='paradigma',
        PLATFORMS=['sensor', 'number', 'switch', 'water_heater'],
        ConfigEntryNotReady=ConfigEntryNotReady, ConfigEntryError=ConfigEntryError,
        validate_config=FLOW['validate_config'], control_allowed=FLOW['control_allowed'],
        Platform=SimpleNamespace(SENSOR='sensor'),
        ParadigmaHub=Hub, ParadigmaDataCoordinator=SENSOR.ParadigmaDataCoordinator,
        dr=SimpleNamespace(async_get=lambda hass: SimpleNamespace(async_get_or_create=lambda **kw: None)),
        _LOGGER=logging.getLogger('test_setup'),
    )
    functions = ast.Module(body=[n for n in tree.body if isinstance(n, ast.AsyncFunctionDef)], type_ignores=[])
    exec(compile(functions, '__init__.py', 'exec'), namespace)
    return namespace


SETUP = load_setup_functions()


class Entry:
    def __init__(self):
        self.entry_id = 'existing-entry'
        self.data = dict(name='Bestehend', host='offline.example', port=502, slave_id=1, scan_interval=45, wood_installed=True)
        self.callbacks = []

    def add_update_listener(self, listener):
        self.listener = listener
        return lambda: None

    def async_on_unload(self, callback):
        self.callbacks.append(callback)


class Hass(FakeHass):
    def __init__(self):
        self.data = {}
        self.forward_error = None
        self.unload_ok = True
        self.events = []
        self.config_entries = SimpleNamespace(async_forward_entry_setups=self.forward,
                                             async_unload_platforms=self.unload,
                                             async_reload=self.reload)

    async def async_add_executor_job(self, func, *args):
        self.events.append(('executor', func.__name__))
        return func(*args)

    async def forward(self, entry, platforms):
        self.events.append(('forward', list(platforms)))
        self.asserted_first_data = self.data['paradigma'][entry.entry_id].coordinator.data
        if self.forward_error:
            raise self.forward_error
        entities = []
        await SENSOR.async_setup_entry(self, entry, entities.extend)
        self.entities = entities

    async def unload(self, entry, platforms):
        self.events.append(('unload', list(platforms)))
        hub = self.data['paradigma'][entry.entry_id]
        assert not hub.closed, 'Client closed before platforms unloaded'
        assert not hub.coordinator.shutdown, 'Coordinator stopped before unload decision'
        return self.unload_ok

    async def reload(self, entry_id):
        self.events.append(('reload', entry_id))


class LifecycleTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        Hub.instances = []
        Hub.connect_ok = True
        Hub.no_responses = False
        self.hass = Hass()
        self.entry = Entry()

    async def test_successful_setup_reads_once_and_successful_unload(self):
        self.assertTrue(await SETUP['async_setup_entry'](self.hass, self.entry))
        hub = Hub.instances[-1]
        self.assertIsNotNone(self.hass.asserted_first_data)
        self.assertEqual(hub.calls.count(('holding', 27, 2)), 1)
        self.assertEqual(hub.coordinator.update_interval.total_seconds(), 45)
        self.assertEqual(self.entry.listener, SETUP['update_listener'])
        self.assertTrue(await SETUP['async_unload_entry'](self.hass, self.entry))
        self.assertTrue(hub.closed)
        self.assertTrue(hub.coordinator.shutdown)
        self.assertNotIn(self.entry.entry_id, self.hass.data['paradigma'])
        self.assertIn(('executor', 'close'), self.hass.events)

    async def test_failed_connection_cleaned_and_retry_can_succeed(self):
        Hub.connect_ok = False
        with self.assertRaises(ConfigEntryNotReady):
            await SETUP['async_setup_entry'](self.hass, self.entry)
        self.assertTrue(Hub.instances[-1].closed)
        self.assertTrue(Hub.instances[-1].coordinator.shutdown)
        self.assertNotIn('paradigma', self.hass.data)
        Hub.connect_ok = True
        self.assertTrue(await SETUP['async_setup_entry'](self.hass, self.entry))

    async def test_first_read_failure_cleanup(self):
        Hub.no_responses = True
        with self.assertRaisesRegex(Exception, 'No valid Modbus responses'):
            await SETUP['async_setup_entry'](self.hass, self.entry)
        self.assertTrue(Hub.instances[-1].closed)
        self.assertTrue(Hub.instances[-1].coordinator.shutdown)
        self.assertFalse(any(event[0] == 'forward' for event in self.hass.events))

    async def test_failed_unload_retains_functioning_client(self):
        await SETUP['async_setup_entry'](self.hass, self.entry)
        hub = Hub.instances[-1]
        self.hass.unload_ok = False
        self.assertFalse(await SETUP['async_unload_entry'](self.hass, self.entry))
        self.assertFalse(hub.closed)
        self.assertFalse(hub.coordinator.shutdown)
        self.assertIs(self.hass.data['paradigma'][self.entry.entry_id], hub)
        self.hass.unload_ok = True
        self.assertTrue(await SETUP['async_unload_entry'](self.hass, self.entry))

    async def test_failed_platform_setup_cleans_up(self):
        self.hass.forward_error = RuntimeError('platform failed')
        with self.assertRaisesRegex(RuntimeError, 'platform failed'):
            await SETUP['async_setup_entry'](self.hass, self.entry)
        self.assertTrue(Hub.instances[-1].closed)
        self.assertNotIn(self.entry.entry_id, self.hass.data['paradigma'])

    async def test_failed_platform_cleanup_keeps_client(self):
        self.hass.forward_error = RuntimeError('platform failed')
        self.hass.unload_ok = False
        with self.assertLogs(SETUP['_LOGGER'], level='ERROR'):
            with self.assertRaises(RuntimeError):
                await SETUP['async_setup_entry'](self.hass, self.entry)
        self.assertFalse(Hub.instances[-1].closed)
        self.assertIn(self.entry.entry_id, self.hass.data['paradigma'])
        count = len(Hub.instances)
        with self.assertRaises(ConfigEntryError):
            await SETUP['async_setup_entry'](self.hass, self.entry)
        self.assertEqual(len(Hub.instances), count)

    async def test_reload_uses_same_entry_and_new_interval(self):
        await SETUP['async_setup_entry'](self.hass, self.entry)
        old_id = next(e._attr_unique_id for e in self.hass.entities if e._key == 'boiler_hours')
        self.entry.data['scan_interval'] = 60
        await SETUP['update_listener'](self.hass, self.entry)
        self.assertIn(('reload', self.entry.entry_id), self.hass.events)
        await SETUP['async_unload_entry'](self.hass, self.entry)
        await SETUP['async_setup_entry'](self.hass, self.entry)
        self.assertEqual(Hub.instances[-1].coordinator.update_interval.total_seconds(), 60)
        self.assertEqual(next(e._attr_unique_id for e in self.hass.entities if e._key == 'boiler_hours'), old_id)

    async def test_invalid_connection_config_never_creates_client(self):
        self.entry.data['port'] = -1
        with self.assertRaises(ConfigEntryError):
            await SETUP['async_setup_entry'](self.hass, self.entry)
        self.assertEqual(Hub.instances, [])

    async def test_setup_cancellation_closes_client(self):
        self.hass.forward_error = asyncio.CancelledError()
        with self.assertRaises(asyncio.CancelledError):
            await SETUP['async_setup_entry'](self.hass, self.entry)
        self.assertTrue(Hub.instances[-1].closed)
