"""Final safety checks with fake clocks, clients and HA boundaries only."""
import ast
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from test_p1_lifecycle import SETUP, Entry, Hass, Hub as LifecycleHub
from test_p3_control import (ALLOW, ENTITIES, FLOW, HUB, HomeAssistantError,
                             WriteClient, make_hub)
from test_peleo_config_flow import FakeHass
from test_peleo_sensors import SENSOR, FakeHub

ROOT = Path(__file__).resolve().parents[1]
CONFIRMATION_GLOBALS = ENTITIES['number'].SetpointConfirmation.__init__.__globals__


class IntervalReviewTests(unittest.IsolatedAsyncioTestCase):
    async def test_new_inputs_require_ten_seconds_and_default_remains_thirty(self):
        data = dict(name='PELEO', host='offline.example', port=502, slave_id=1)
        for interval in (10, 30, 3600):
            self.assertEqual(FLOW['validate_config']({**data, 'scan_interval': interval}), {})
        for interval in range(10):
            self.assertIn('scan_interval', FLOW['validate_config']({**data, 'scan_interval': interval}))
            user = FLOW['ConfigFlow']()
            user.hass = FakeHass()
            with patch.dict(FLOW, {'ParadigmaHub': lambda *args: self.fail('Unexpected connection')}):
                result = await user.async_step_user({**data, 'scan_interval': interval})
            self.assertEqual(result['errors']['scan_interval'], 'invalid_scan_interval')
            entry = SimpleNamespace(entry_id='entry', data=dict(data), options={})
            options = FLOW['OptionsFlowHandler'](entry)
            options.config_entry = entry
            options.hass = FakeHass()
            result = await options.async_step_init({'scan_interval': interval})
            self.assertEqual(result['errors']['scan_interval'], 'invalid_scan_interval')
            self.assertEqual(entry.data, data)
        self.assertEqual(FLOW['scan_interval']({}), 30)
        for name in ('strings.json', 'translations/de.json', 'translations/en.json'):
            translations = json.loads((ROOT / 'custom_components/paradigma' / name).read_text())
            for section in ('config', 'options'):
                self.assertIn('10', translations[section]['error']['invalid_scan_interval'])

    async def test_legacy_small_interval_loads_safely_without_mutating_entry(self):
        LifecycleHub.connect_ok = True
        LifecycleHub.no_responses = False
        for interval in range(1, 10):
            entry = Entry()
            entry.data['scan_interval'] = interval
            original = entry.data.copy()
            hass = Hass()
            with self.assertLogs(level='WARNING'):
                await SETUP['async_setup_entry'](hass, entry)
            hub = hass.data['paradigma'][entry.entry_id]
            self.assertEqual(hub.coordinator.update_interval.total_seconds(), 30)
            self.assertEqual(entry.data, original)
            self.assertEqual(hub.platforms, ['sensor'])
            await SETUP['async_unload_entry'](hass, entry)

    async def test_thirty_seconds_applies_to_a_complete_deduplicated_cycle(self):
        for config in ({}, {option: True for option in ('solar_installed', 'hk2_installed',
                                                       'boiler_installed', 'room_sensor_installed',
                                                       'pool_installed')}):
            hass = FakeHass()
            hub = FakeHub()
            coordinator = SENSOR.ParadigmaDataCoordinator(hass, hub, config)
            expected = [('input' if kind == 'input' else 'holding', address, count)
                        for (kind, address), count in coordinator._read_plan.items()]
            self.assertEqual(coordinator.update_interval.total_seconds(), 30)
            await coordinator.async_refresh()
            self.assertEqual(hub.calls, expected)
            self.assertEqual(len(hub.calls), len(set(hub.calls)))
            await coordinator.async_refresh()
            self.assertEqual(hub.calls, expected + expected)


class ConfirmationReviewTests(unittest.TestCase):
    def setUp(self):
        silence = patch.object(HUB._LOGGER, 'disabled', True)
        silence.start()
        self.addCleanup(silence.stop)
        self.hub = make_hub(True)
        self.entry = SimpleNamespace(entry_id='existing-entry', data={'hk2_installed': True})
        self.number = ENTITIES['number'].ParadigmaNumber(self.hub, 'setpoint_flow_hk1', 2, 20, 80, 1, self.entry)
        self.water = ENTITIES['water_heater'].ParadigmaWaterHeater(self.hub, self.entry)
        self.now = 100.0
        self.clock = patch.dict(CONFIRMATION_GLOBALS, {'monotonic': lambda: self.now})
        self.clock.start()
        self.addCleanup(self.clock.stop)

    def test_matching_readback_expires_and_polling_never_renews_it(self):
        self.number.set_native_value(60)
        self.water.set_temperature(temperature=60)
        for entity in (self.number, self.water):
            self.assertEqual(entity.extra_state_attributes['setpoint_confirmation'], 'readback_matches')
        count = len(self.hub._client.writes)
        for self.now in (200, 399, 400, 401, 700):
            self.number.update()
            self.water.update()
            expected = 'readback_matches' if self.now < 400 else 'expired'
            for entity in (self.number, self.water):
                self.assertEqual(entity.extra_state_attributes['setpoint_confirmation'], expected)
        self.assertEqual(len(self.hub._client.writes), count)
        self.assertIsNone(self.water._attr_current_operation)
        # Register contents remain observable; they do not prove an active override.
        self.assertEqual(self.number._attr_native_value, 60)
        self.assertEqual(self.water.target_temperature, 60)

    def test_delayed_ack_and_readback_cannot_extend_the_window(self):
        original = self.hub._client.write_registers
        def delayed_write(**kwargs):
            response = original(**kwargs)
            self.now += 301
            return response
        with patch.object(self.hub._client, 'write_registers', side_effect=delayed_write):
            self.number.set_native_value(60)
        self.assertEqual(self.number.extra_state_attributes['setpoint_confirmation'], 'expired')

    def test_acknowledgement_without_readback_is_not_confirmation(self):
        confirmation = ENTITIES['number'].SetpointConfirmation()
        confirmation.begin(60)
        self.assertEqual(confirmation.attributes['setpoint_confirmation'], 'pending')
        confirmation.acknowledge()
        self.assertEqual(confirmation.attributes['setpoint_confirmation'], 'acknowledged')
        confirmation.observe(None)
        self.assertEqual(confirmation.attributes['setpoint_confirmation'], 'readback_failed')
        confirmation.observe(50)
        self.assertEqual(confirmation.attributes['setpoint_confirmation'], 'readback_mismatch')
        self.now = 400
        confirmation.observe(60)
        self.assertEqual(confirmation.attributes['setpoint_confirmation'], 'expired')

    def test_failed_second_write_clears_previous_confirmed_value(self):
        self.number.set_native_value(60)
        self.hub._client.ack = None
        with self.assertRaises(HomeAssistantError):
            self.number.set_native_value(70)
        self.assertIsNone(self.number._attr_native_value)
        self.assertFalse(self.number.available)
        self.assertEqual(self.number.extra_state_attributes['setpoint_confirmation'], 'write_failed')

    def test_restarting_entities_never_restores_a_confirmation(self):
        self.number.set_native_value(60)
        self.water.set_temperature(temperature=60)
        number = ENTITIES['number'].ParadigmaNumber(self.hub, 'setpoint_flow_hk1', 2, 20, 80, 1, self.entry)
        water = ENTITIES['water_heater'].ParadigmaWaterHeater(self.hub, self.entry)
        count = len(self.hub._client.writes)
        for entity in (number, water):
            entity.update()
            self.assertEqual(entity.extra_state_attributes['setpoint_confirmation'], 'not_requested')
        self.assertEqual(len(self.hub._client.writes), count)
        self.assertEqual(number._attr_unique_id, self.number._attr_unique_id)
        self.assertEqual(water._attr_unique_id, self.water._attr_unique_id)

    def test_all_entity_actions_without_explicit_permission_emit_no_write(self):
        for permission in (False, None, 0, 1, 'true', 'false'):
            hub = make_hub(permission)
            number = ENTITIES['number'].ParadigmaNumber(hub, 'setpoint_flow_hk1', 2, 20, 80, 1, self.entry)
            water = ENTITIES['water_heater'].ParadigmaWaterHeater(hub, self.entry)
            switch = ENTITIES['switch'].ParadigmaSwitch(hub, 'dhw_enable', 4, self.entry)
            for action in (lambda: number.set_native_value(60),
                           lambda: water.set_temperature(temperature=60),
                           water.turn_on, water.turn_off, switch.turn_on, switch.turn_off):
                with self.assertRaises(HomeAssistantError):
                    action()
            self.assertEqual(hub._client.writes, [])
            self.assertEqual(hub._client.calls, [])
            self.assertEqual(hub._client.connects, 0)

    def test_only_fc10_client_write_api_exists_in_production(self):
        calls = []
        for path in (ROOT / 'custom_components/paradigma').glob('*.py'):
            for node in ast.walk(ast.parse(path.read_text())):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr.startswith('write')
                        and isinstance(node.func.value, ast.Attribute)
                        and node.func.value.attr == '_client'):
                    calls.append((path.name, node.func.attr))
        self.assertEqual(calls, [('hub.py', 'write_registers')])

    def test_revocation_does_not_reset_active_overrides(self):
        self.number.set_native_value(60)
        self.water.set_temperature(temperature=60)
        count = len(self.hub._client.writes)
        self.hub.revoke_control()
        self.assertEqual(len(self.hub._client.writes), count)
        self.assertEqual(self.hub._client.stored[2], 600)
        self.assertEqual(self.hub._client.stored[8], 600)
        self.assertFalse(self.number.available)
        self.assertFalse(self.water.available)

    def test_cyclic_platform_read_counts_and_target_only_readback(self):
        self.hub._client.calls.clear()
        self.number.update()
        self.assertEqual(self.hub._client.calls, [('holding', 2, 1, 1)])
        self.hub._client.calls.clear()
        self.water.update()
        self.assertEqual(self.hub._client.calls, [('input', 3, 1, 1), ('holding', 8, 1, 1)])
        self.hub._client.calls.clear()
        self.water.set_temperature(temperature=60)
        self.assertEqual(self.hub._client.calls, [('coils', 4, 2, 1), ('holding', 8, 1, 1)])
        entities = []
        # Switch setup never creates a polled entity.
        import asyncio
        asyncio.run(ENTITIES['switch'].async_setup_entry(None, self.entry, entities.extend))
        self.assertEqual(entities, [])


class RestartSafetyTests(unittest.IsolatedAsyncioTestCase):
    async def test_setup_restart_reconnect_grant_and_unload_never_emit_writes(self):
        hubs = []
        class RuntimeHub(HUB.ParadigmaHub):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._client = WriteClient()
                hubs.append(self)

            @property
            def closed(self):
                return self._closed

        entry = Entry()
        entry.options = {}
        for permission in (False, True, False):
            entry.data[ALLOW] = permission
            hass = Hass()  # Fresh HA runtime, same stored entry and identities.
            forward_sensors = hass.forward
            async def forward(entry, platforms):
                await forward_sensors(entry, platforms)
                hass.controls = []
                for name, module in ENTITIES.items():
                    if name in platforms:
                        await module.async_setup_entry(hass, entry, hass.controls.extend)
            hass.config_entries.async_forward_entry_setups = forward
            with patch.dict(SETUP, {'ParadigmaHub': RuntimeHub}):
                await SETUP['async_setup_entry'](hass, entry)
                hub = hubs[-1]
                hub._client.connected = False
                await hub.coordinator.async_refresh()
                for control in hass.controls:
                    control.update()
                self.assertEqual(hub._client.writes, [])
                for control in hass.controls:
                    self.assertEqual(control.extra_state_attributes['setpoint_confirmation'], 'not_requested')
                await SETUP['update_listener'](hass, entry)
                await SETUP['async_unload_entry'](hass, entry)
                self.assertEqual(hub._client.writes, [])
