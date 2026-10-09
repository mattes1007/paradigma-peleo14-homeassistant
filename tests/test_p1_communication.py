"""Offline transport and coordinator tests; the real client is never imported."""
import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

from test_peleo_sensors import SENSOR, FakeHass

ROOT = Path(__file__).resolve().parents[1]


class ModbusException(Exception):
    pass


class Response:
    def __init__(self, values=None, error=False):
        self.registers = values
        self.bits = values
        self.error = error

    def isError(self):
        return self.error

    def __str__(self):
        return 'illegal address' if self.error else 'registers'


class Client:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.connected = False
        self.connect_ok = True
        self.offline = False
        self.closed = 0
        self.connects = 0
        self.calls = []
        self.overrides = {}

    def connect(self):
        self.connects += 1
        if isinstance(self.connect_ok, Exception):
            raise self.connect_ok
        self.connected = self.connect_ok
        return self.connect_ok

    def close(self):
        self.closed += 1
        self.connected = False

    def _read(self, kind, address, count, device_id):
        self.calls.append((kind, address, count, device_id))
        if self.offline:
            raise TimeoutError('offline timeout')
        result = self.overrides.get((kind, address), Response([0, 4294] if count == 2 else [0]))
        if isinstance(result, Exception):
            raise result
        return result

    def read_input_registers(self, address, *, count, device_id):
        return self._read('input', address, count, device_id)

    def read_holding_registers(self, address, *, count, device_id):
        return self._read('holding', address, count, device_id)

    def read_coils(self, address, *, count, device_id):
        return self._read('coils', address, count, device_id)


def load_hub():
    modules = {name: ModuleType(name) for name in ('pymodbus', 'pymodbus.client', 'pymodbus.exceptions')}
    modules['pymodbus.client'].ModbusTcpClient = Client
    modules['pymodbus.exceptions'].ModbusException = ModbusException
    with patch.dict(sys.modules, modules):
        spec = importlib.util.spec_from_file_location('p1_hub', ROOT / 'custom_components/paradigma/hub.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


HUB = load_hub()


class HubTests(unittest.TestCase):
    def setUp(self):
        self.hub = HUB.ParadigmaHub(None, 'PELEO', 'offline.example', 502, 1)
        self.client = self.hub._client
        self.clock = patch.object(HUB, 'monotonic', return_value=100)
        self.time = self.clock.start()
        self.addCleanup(self.clock.stop)

    def test_keyword_api_and_shared_client_defaults_preserved(self):
        self.assertEqual(self.hub.read_holding_registers(27, 2), [0, 4294])
        self.assertEqual(self.client.calls, [('holding', 27, 2, 1)])
        self.assertNotIn('timeout', self.client.kwargs)
        self.assertNotIn('retries', self.client.kwargs)
        self.client.overrides[('coils', 4)] = Response([True] * 8)
        self.assertEqual(self.hub.read_coils(4, 1), [True] * 8)

    def test_connect_failure_and_retry(self):
        for failure in (False, OSError('refused'), ModbusException('connect error')):
            with self.subTest(failure=failure):
                self.hub._retry_after = 0
                self.client.connect_ok = failure
                with self.assertLogs(HUB._LOGGER, level='DEBUG'):
                    self.assertFalse(self.hub.connect())
                calls = self.client.connects
                self.assertIsNone(self.hub.read_input_registers(0, 1))
                self.assertEqual(self.client.connects, calls)
        self.client.connect_ok = True
        self.time.return_value = 105
        with self.assertLogs(HUB._LOGGER, level='INFO') as logs:
            self.assertEqual(self.hub.read_input_registers(0, 1), [0])
        self.assertIn('restored', '\n'.join(logs.output))

    def test_timeout_backoff_and_recovery(self):
        self.client.offline = True
        with self.assertLogs(HUB._LOGGER, level='WARNING') as logs:
            self.assertIsNone(self.hub.read_input_registers(0, 1))
        self.assertIn('address 0', '\n'.join(logs.output))
        self.assertIn('device 1', '\n'.join(logs.output))
        for _ in range(10):
            self.assertIsNone(self.hub.read_holding_registers(27, 2))
        self.assertEqual(len(self.client.calls), 1)
        self.client.offline = False
        self.time.return_value = 105
        with self.assertLogs(HUB._LOGGER, level='INFO'):
            self.assertEqual(self.hub.read_holding_registers(27, 2), [0, 4294])

    def test_device_errors_are_not_transport_errors_and_are_rate_limited(self):
        self.client.overrides[('holding', 41)] = Response(error=True)
        with self.assertLogs(HUB._LOGGER, level='WARNING'):
            self.assertIsNone(self.hub.read_holding_registers(41, 1))
        with self.assertNoLogs(HUB._LOGGER, level='WARNING'):
            self.assertIsNone(self.hub.read_holding_registers(41, 1))
        self.assertEqual(self.client.closed, 0)
        self.assertEqual(self.hub.read_input_registers(0, 1), [0])
        self.client.overrides.clear()
        with self.assertLogs(HUB._LOGGER, level='INFO'):
            self.assertEqual(self.hub.read_holding_registers(41, 1), [0])

    def test_none_and_exception_response_trigger_backoff(self):
        for response in (None, ModbusException('no response')):
            with self.subTest(response=response):
                self.hub._retry_after = 0
                self.client.overrides[('holding', 27)] = response
                with self.assertLogs(HUB._LOGGER, level='DEBUG'):
                    self.assertIsNone(self.hub.read_holding_registers(27, 2))
                self.assertEqual(self.hub._retry_after, 105)

    def test_malformed_responses(self):
        for values in ([], [0], [0, 1, 2], [-1, 0], [0, 65536], [True, 0], [0, '1']):
            with self.subTest(values=values):
                self.client.overrides[('holding', 27)] = Response(values)
                with self.assertLogs(HUB._LOGGER, level='DEBUG'):
                    self.assertIsNone(self.hub.read_holding_registers(27, 2))

    def test_returned_transport_exception(self):
        with patch.object(self.client, 'read_holding_registers', return_value=ModbusException('no reply')):
            with self.assertLogs(HUB._LOGGER, level='WARNING'):
                self.assertIsNone(self.hub.read_holding_registers(27, 2))
        self.assertEqual(self.hub._retry_after, 105)

    def test_invalid_response_object_and_coil_payload(self):
        self.client.overrides[('holding', 27)] = object()
        with self.assertLogs(HUB._LOGGER, level='WARNING'):
            self.assertIsNone(self.hub.read_holding_registers(27, 2))
        self.client.overrides[('coils', 4)] = Response(['invalid'])
        with self.assertLogs(HUB._LOGGER, level='WARNING'):
            self.assertIsNone(self.hub.read_coils(4, 1))

    def test_closed_client_does_not_reconnect_for_reads(self):
        self.hub.connect()
        self.hub.close()
        self.assertIsNone(self.hub.read_input_registers(0, 1))
        self.assertFalse(self.hub.connect())
        self.assertEqual(self.client.connects, 1)


class CoordinatorTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.hub = HUB.ParadigmaHub(None, 'PELEO', 'offline.example', 502, 1)
        self.hass = FakeHass(self.hub)
        self.coordinator = SENSOR.ParadigmaDataCoordinator(self.hass, self.hub, {'scan_interval': 45}, SimpleNamespace(entry_id='existing-entry'))
        self.entity = SENSOR.ParadigmaSensor(self.coordinator, SimpleNamespace(entry_id='old'), next(d for d in SENSOR.SENSOR_DEFINITIONS if d[0] == 'boiler_hours'))

    async def test_outage_and_reconnection_restore_sensor(self):
        with patch.object(HUB, 'monotonic', return_value=100) as clock:
            await self.coordinator.async_refresh()
            self.assertTrue(self.entity.available)
            self.assertEqual(self.entity.native_value, 4294)
            self.hub._client.offline = True
            with self.assertLogs(HUB._LOGGER, level='WARNING'):
                await self.coordinator.async_refresh()
            self.assertFalse(self.entity.available)
            self.hub._client.offline = False
            clock.return_value = 145
            with self.assertLogs(HUB._LOGGER, level='INFO'):
                await self.coordinator.async_refresh()
            self.assertTrue(self.entity.available)
            self.assertEqual(self.entity.native_value, 4294)
            self.assertEqual(self.entity._attr_unique_id, 'old_holding_32_27')

    async def test_before_first_refresh_has_no_value_and_is_unavailable(self):
        self.assertFalse(self.entity.available)
        self.assertIsNone(self.entity.native_value)

    async def test_all_registers_return_modbus_errors(self):
        for (kind, address) in self.coordinator._read_plan:
            self.hub._client.overrides[('input' if kind == 'input' else 'holding', address)] = Response(error=True)
        with self.assertLogs(HUB._LOGGER, level='WARNING'):
            await self.coordinator.async_refresh()
        self.assertFalse(self.coordinator.last_update_success)
        self.assertFalse(self.entity.available)
        self.assertFalse(self.hub._client.closed)

    async def test_partial_failure_and_sentinel(self):
        self.hub._client.overrides[('holding', 27)] = Response(error=True)
        with self.assertLogs(HUB._LOGGER, level='WARNING'):
            await self.coordinator.async_refresh()
        self.assertTrue(self.coordinator.last_update_success)
        self.assertFalse(self.entity.available)
        self.hub._client.overrides[('holding', 27)] = Response([65535, 65535])
        with self.assertLogs(HUB._LOGGER, level='INFO'):
            await self.coordinator.async_refresh()
        self.assertTrue(self.entity.available)
        self.assertIsNone(self.entity.native_value)

    async def test_configured_interval_and_no_duplicate_initial_refresh(self):
        self.assertEqual(self.coordinator.update_interval.total_seconds(), 45)
        self.hub.coordinator = self.coordinator
        await self.coordinator.async_config_entry_first_refresh()
        count = len(self.hub._client.calls)
        entities = []
        await SENSOR.async_setup_entry(self.hass, SimpleNamespace(entry_id='existing-entry', data={}), entities.extend)
        self.assertEqual(len(self.hub._client.calls), count)
        self.assertTrue(all(e.coordinator is self.coordinator for e in entities))

    async def test_missing_interval_defaults_and_legacy_invalid_falls_back(self):
        self.assertEqual(SENSOR.ParadigmaDataCoordinator(self.hass, self.hub, {}).update_interval.total_seconds(), 30)
        with self.assertLogs(level='WARNING'):
            coordinator = SENSOR.ParadigmaDataCoordinator(self.hass, self.hub, {'scan_interval': -1})
        self.assertEqual(coordinator.update_interval.total_seconds(), 30)


class ExecutorTests(unittest.IsolatedAsyncioTestCase):
    async def test_sensor_io_runs_outside_event_loop(self):
        import asyncio
        import threading
        from concurrent.futures import ThreadPoolExecutor
        loop_thread = threading.get_ident()
        io_threads = []

        class ThreadHass:
            def __init__(self, pool):
                self.pool = pool

            async def async_add_executor_job(self, func, *args):
                # Poll a real thread future without depending on asyncio's
                # socketpair wakeup and default-executor teardown in the sandbox.
                future = self.pool.submit(func, *args)
                while not future.done():
                    await asyncio.sleep(0.001)
                return future.result()

        class ThreadHub:
            def read_input_registers(self, address, count):
                io_threads.append(threading.get_ident())
                return [0]

            def read_holding_registers(self, address, count):
                io_threads.append(threading.get_ident())
                return [0] * count

        with ThreadPoolExecutor(max_workers=1) as pool:
            coordinator = SENSOR.ParadigmaDataCoordinator(ThreadHass(pool), ThreadHub(), {})
            data = await coordinator._async_update_data()
        self.assertIn('holding_32_27', data)
        self.assertTrue(io_threads)
        self.assertTrue(all(thread != loop_thread for thread in io_threads))
