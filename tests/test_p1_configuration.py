"""Configuration boundaries, old entries and rejected flow inputs."""
import asyncio
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from test_peleo_config_flow import FLOW, FakeHass


class ValidationTests(unittest.TestCase):
    def config(self, **overrides):
        data = dict(name='PELEO', host='offline.example', port=502, slave_id=1, scan_interval=30)
        data.update(overrides)
        return data

    def test_integer_boundaries(self):
        for key, bounds in (('port', (1, 65535)), ('slave_id', (1, 255)), ('scan_interval', (10, 3600))):
            for value in bounds:
                self.assertEqual(FLOW['validate_config'](self.config(**{key: value})), {})
            for value in (bounds[0] - 1, bounds[1] + 1, True, False, str(bounds[0]), float(bounds[0]), None):
                with self.subTest(key=key, value=value):
                    self.assertIn(key, FLOW['validate_config'](self.config(**{key: value})))

    def test_hostname_and_ipv6_without_network_lookup(self):
        for host in ('offline.example', '192.0.2.42', '2001:db8::1'):
            self.assertEqual(FLOW['validate_config'](self.config(host=host)), {})
        for host in ('', ' offline.example', 'offline.example ', 'a\nb', None, 42):
            self.assertEqual(FLOW['validate_config'](self.config(host=host))['host'], 'invalid_host')

    def test_invalid_new_input_does_not_connect(self):
        flow = FLOW['ConfigFlow']()
        flow.hass = FakeHass()
        with patch.dict(FLOW, {'ParadigmaHub': lambda *args: self.fail('unexpected client creation')}):
            result = asyncio.run(flow.async_step_user(self.config(port=0, slave_id=0, scan_interval=0)))
        self.assertEqual(set(result['errors']), {'port', 'slave_id', 'scan_interval'})

    def test_invalid_options_do_not_mutate_existing_entry(self):
        entry = SimpleNamespace(entry_id='existing-entry', options={}, data=self.config(wood_installed=True))
        original = entry.data.copy()
        flow = FLOW['OptionsFlowHandler'](entry)
        flow.config_entry = entry
        flow.hass = FakeHass()
        result = asyncio.run(flow.async_step_init({'scan_interval': -1}))
        self.assertEqual(result['errors'], {'scan_interval': 'invalid_scan_interval'})
        self.assertEqual(entry.data, original)

    def test_connect_test_closes_client_on_error(self):
        class Hub:
            closed = False

            def __init__(self, *args):
                pass

            def connect(self):
                raise RuntimeError('test error')

            def close(self):
                Hub.closed = True

        flow = FLOW['ConfigFlow']()
        flow.hass = FakeHass()
        with patch.dict(FLOW, {'ParadigmaHub': Hub}):
            with self.assertRaises(RuntimeError):
                asyncio.run(flow.async_step_user(self.config()))
        self.assertTrue(Hub.closed)

    def test_old_missing_and_invalid_intervals(self):
        self.assertEqual(FLOW['scan_interval']({}), 30)
        for value in (0, -1, 1, 5, 6, 7, 8, 9, 3601, '30', True):
            data = self.config(scan_interval=value)
            with self.assertLogs(FLOW['_LOGGER'], level='WARNING'):
                self.assertEqual(FLOW['scan_interval'](data), 30)
            self.assertEqual(FLOW['validate_config'](data, check_interval=False), {})
            self.assertIn('scan_interval', FLOW['validate_config'](data))
