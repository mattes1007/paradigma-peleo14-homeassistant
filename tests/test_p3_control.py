"""P3 safety regressions: production policy/entities with strictly local clients."""
import asyncio
import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

from test_p1_communication import HUB, Client, Response, ModbusException
from test_p1_lifecycle import SETUP, Hub as LifecycleHub, Hass as LifecycleHass, Entry
from test_peleo_config_flow import FLOW, FakeHass

ROOT = Path(__file__).resolve().parents[1]
ALLOW = 'allow_control'


class WriteClient(Client):
    def __init__(self):
        super().__init__()
        self.writes = []
        self.stored = {2: 400, 3: 400, 8: 500, 9: 800, 10: 800}
        self.ack = 'ok'
        self.readback = None
        self.after_precondition = None

    def read_holding_registers(self, address, *, count, device_id):
        if ('holding', address) in self.overrides or self.offline:
            return super().read_holding_registers(address, count=count, device_id=device_id)
        self.calls.append(('holding', address, count, device_id))
        if self.after_precondition and address in (9, 10):
            self.after_precondition()
        return Response([0, 4294] if count == 2 else [self.stored.get(address, 0)])

    def read_coils(self, address, *, count, device_id):
        if ('coils', address) in self.overrides:
            return super().read_coils(address, count=count, device_id=device_id)
        self.calls.append(('coils', address, count, device_id))
        if self.after_precondition:
            self.after_precondition()
        return Response([True, False] + [False] * 6)

    def write_registers(self, *, address, values, device_id):
        self.writes.append(('registers', address, values, device_id))
        if isinstance(self.ack, Exception):
            raise self.ack
        if self.ack != 'ok':
            return self.ack
        self.stored[address] = values[0] if self.readback is None else self.readback
        return SimpleNamespace(isError=lambda: False, function_code=0x10, address=address, count=1)

    def write_coil(self, *args, **kwargs):
        raise AssertionError('No coil function is currently approved')


def make_hub(permission=False, **kwargs):
    hub = HUB.ParadigmaHub(None, 'PELEO', 'offline.example', 502, 1,
                          allow_control=permission, **kwargs)
    hub._client = WriteClient()
    return hub


class HomeAssistantError(Exception):
    pass


class ServiceValidationError(HomeAssistantError):
    pass


class Entity:
    def schedule_update_ha_state(self):
        self.scheduled = getattr(self, 'scheduled', 0) + 1


def load_entities():
    names = ('homeassistant', 'homeassistant.components', 'homeassistant.const',
             'homeassistant.components.number', 'homeassistant.components.switch',
             'homeassistant.components.water_heater', 'homeassistant.exceptions',
             'homeassistant.helpers', 'homeassistant.helpers.entity', 'p3_entity_package')
    modules = {name: ModuleType(name) for name in names}
    modules['p3_entity_package'].__path__ = [str(ROOT / 'custom_components/paradigma')]
    const = modules['homeassistant.const']
    const.Platform = SimpleNamespace(SENSOR='sensor', NUMBER='number', SWITCH='switch', WATER_HEATER='water_heater')
    const.UnitOfTemperature = SimpleNamespace(CELSIUS='°C')
    const.ATTR_TEMPERATURE = 'temperature'
    const.PRECISION_TENTHS = 0.1
    modules['homeassistant.components.number'].NumberEntity = Entity
    modules['homeassistant.components.switch'].SwitchEntity = Entity
    modules['homeassistant.components.water_heater'].WaterHeaterEntity = Entity
    modules['homeassistant.components.water_heater'].WaterHeaterEntityFeature = SimpleNamespace(TARGET_TEMPERATURE=1, ON_OFF=2)
    modules['homeassistant.exceptions'].HomeAssistantError = HomeAssistantError
    modules['homeassistant.exceptions'].ServiceValidationError = ServiceValidationError
    modules['homeassistant.helpers.entity'].DeviceInfo = dict
    result = {}
    with patch.dict(sys.modules, modules):
        for name in ('number', 'switch', 'water_heater'):
            spec = importlib.util.spec_from_file_location(f'p3_entity_package.{name}', ROOT / f'custom_components/paradigma/{name}.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            result[name] = module
    return result


ENTITIES = load_entities()


class HubSafetyTests(unittest.TestCase):
    def setUp(self):
        silence = patch.object(HUB._LOGGER, "disabled", True)
        silence.start()
        self.addCleanup(silence.stop)

    def test_blocked_write_log_identifies_target(self):
        hub = make_hub()
        with patch.object(HUB._LOGGER, "disabled", False):
            with self.assertLogs(HUB._LOGGER, level="WARNING") as logs:
                self.assertFalse(hub.write_register(2, 500))
            self.assertIn("holding address 2", logs.output[0])
            with self.assertNoLogs(HUB._LOGGER, level="WARNING"):
                self.assertFalse(hub.write_register(2, 500))

    def test_missing_and_invalid_permissions_never_reach_client(self):
        for permission in (False, None, 0, 1, 'true', 'false', 'True', [], {}, 1.0):
            with self.subTest(permission=permission):
                hub = make_hub(permission)
                for address in (2, 3, 8, 27, 29, 41, 44, 45):
                    self.assertFalse(hub.write_register(address, 500))
                for address in (4, 5, 6, 7):
                    self.assertFalse(hub.write_coil(address, True))
                self.assertEqual(hub._client.writes, [])
                self.assertEqual(hub._client.calls, [])
                self.assertEqual(hub._client.connects, 0)

    def test_unapproved_addresses_and_coils_stay_blocked_when_enabled(self):
        hub = make_hub(True)
        for address in (0, 1, 4, 27, 29, 41, 44, 45, 46, 9992, None, True, '2', []):
            self.assertFalse(hub.write_register(address, 500))
        for address in (4, 5, 6, 7, None, []):
            for value in (False, True, 1, 'true'):
                self.assertFalse(hub.write_coil(address, value))
        self.assertEqual(hub._client.writes, [])
        self.assertEqual(hub._client.calls, [])

    def test_verified_write_keyword_api_and_acknowledgement(self):
        hub = make_hub(True)
        for address, value in ((2, 200), (2, 800), (3, 500), (8, 300), (8, 700)):
            self.assertTrue(hub.write_register(address, value))
        self.assertEqual(hub._client.writes[0], ('registers', 2, [200], 1))
        self.assertIn(('holding', 9, 1, 1), hub._client.calls)
        self.assertIn(('holding', 10, 1, 1), hub._client.calls)
        self.assertIn(('coils', 4, 2, 1), hub._client.calls)

    def test_raw_limits_types_steps_and_sentinels(self):
        for address, bad in ((2, (199, 801, 205)), (3, (199, 801, 205)), (8, (299, 701))):
            for value in (*bad, True, None, '500', 500.0, -1, 0x8000, 0xFFFF):
                with self.subTest(address=address, value=value):
                    hub = make_hub(True)
                    self.assertFalse(hub.write_register(address, value))
                    self.assertEqual(hub._client.writes, [])
                    self.assertEqual(hub._client.calls, [])

    def test_dynamic_heating_limit_prevents_write(self):
        for value in (400, 0, 0x7FFF, 0x8000, 0xFFFF):
            hub = make_hub(True)
            hub._client.stored[9] = value
            self.assertFalse(hub.write_register(2, 500))
            self.assertEqual(hub._client.writes, [])
        hub = make_hub(True)
        hub._client.overrides[('holding', 9)] = Response(error=True)
        self.assertFalse(hub.write_register(2, 500))
        self.assertEqual(hub._client.writes, [])

    def test_dhw_requires_unambiguous_release_override(self):
        for values in ([False, False], [False, True], [True, True], [True], [2, False]):
            hub = make_hub(True)
            hub._client.overrides[('coils', 4)] = Response(values)
            self.assertFalse(hub.write_register(8, 500))
            self.assertEqual(hub._client.writes, [])

    def test_write_error_and_malformed_acknowledgements(self):
        responses = (None, Response(error=True), object(), ModbusException('returned'),
                     TimeoutError('timeout'), OSError('lost socket'), RuntimeError('unexpected'),
                     SimpleNamespace(isError=lambda: False, function_code=0x06, address=2, count=1),
                     SimpleNamespace(isError=lambda: False, function_code=0x10, address=3, count=1),
                     SimpleNamespace(isError=lambda: False, function_code=0x10, address=2, count=2))
        for response in responses:
            with self.subTest(response=response):
                hub = make_hub(True)
                hub._client.ack = response
                self.assertFalse(hub.write_register(2, 500))
                self.assertEqual(len(hub._client.writes), 1)

    def test_returned_exception_and_invalid_ack_types(self):
        for response in (ModbusException('returned object'),
                         SimpleNamespace(isError=lambda: None, function_code=0x10, address=2, count=1),
                         SimpleNamespace(isError=lambda: False, function_code=0x10, address=2, count=True)):
            hub = make_hub(True)
            with patch.object(hub._client, 'write_registers', return_value=response) as write:
                self.assertFalse(hub.write_register(2, 500))
                write.assert_called_once()

    def test_precondition_failure_is_fail_closed(self):
        for response in (None, object(), Response(error=True), Response([]), Response([True]),
                         ModbusException('error'), TimeoutError('timeout')):
            hub = make_hub(True)
            hub._client.overrides[('holding', 9)] = response
            self.assertFalse(hub.write_register(2, 500))
            self.assertEqual(hub._client.writes, [])

    def test_live_permission_recheck_and_revocation_are_sticky(self):
        data = {ALLOW: True}
        hub = make_hub(True, permission_check=lambda: FLOW['control_allowed'](data))
        self.assertTrue(hub.write_register(2, 500))
        for permission in (False, None, 1, 'true'):
            data[ALLOW] = permission
            self.assertFalse(hub.write_register(2, 500))
        data[ALLOW] = True
        hub.revoke_control()
        self.assertFalse(hub.write_register(2, 500))
        self.assertEqual(len(hub._client.writes), 1)
        replacement = make_hub(True, permission_check=lambda: FLOW['control_allowed'](data))
        self.assertTrue(replacement.write_register(2, 500))

    def test_revocation_during_precondition_prevents_transmission(self):
        for address in (2, 8):
            hub = make_hub(True)
            hub._client.after_precondition = hub.revoke_control
            self.assertFalse(hub.write_register(address, 500))
            self.assertEqual(hub._client.writes, [])

    def test_closed_failed_connection_and_wrong_slave_never_write(self):
        hub = make_hub(True)
        hub.close()
        self.assertFalse(hub.write_register(2, 500))
        self.assertEqual(hub._client.writes, [])
        hub = make_hub(True)
        hub._client.connect_ok = False
        self.assertFalse(hub.write_register(2, 500))
        self.assertEqual(hub._client.writes, [])
        hub = make_hub(True)
        hub._slave_id = 2
        self.assertFalse(hub.write_register(2, 500))
        self.assertEqual(hub._client.calls, [])

    def test_invalid_live_permission_callback_fails_closed(self):
        for value in (None, False, 1, "true"):
            hub = make_hub(True, permission_check=lambda: value)
            self.assertFalse(hub.write_register(2, 500))
            self.assertEqual(hub._client.calls, [])
        def broken_permission():
            raise RuntimeError("configuration unavailable")
        hub = make_hub(True, permission_check=broken_permission)
        self.assertFalse(hub.write_register(2, 500))
        self.assertEqual(hub._client.calls, [])

    def test_reading_remains_available_in_read_only(self):
        hub = make_hub()
        self.assertEqual(hub.read_holding_registers(2, 1), [400])
        self.assertEqual(hub.read_input_registers(3, 1), [0])
        self.assertEqual(hub._client.writes, [])


class EntityControlTests(unittest.TestCase):
    def setUp(self):
        silence = patch.object(HUB._LOGGER, "disabled", True)
        silence.start()
        self.addCleanup(silence.stop)
        self.hub = make_hub(True)
        self.entry = SimpleNamespace(entry_id='existing-entry', options={}, data={'hk2_installed': True})
        self.number = ENTITIES['number'].ParadigmaNumber(self.hub, 'setpoint_flow_hk1', 2, 20, 80, 1, self.entry)
        self.water = ENTITIES['water_heater'].ParadigmaWaterHeater(self.hub, self.entry)

    def test_no_controls_created_in_read_only(self):
        self.hub.revoke_control()
        hass = SimpleNamespace(data={'paradigma': {self.entry.entry_id: self.hub}})
        for module in ENTITIES.values():
            entities = []
            asyncio.run(module.async_setup_entry(hass, self.entry, entities.extend))
            self.assertEqual(entities, [])
        self.assertEqual(self.hub._client.writes, [])

    def test_only_approved_controls_and_existing_ids(self):
        hass = SimpleNamespace(data={'paradigma': {self.entry.entry_id: self.hub}})
        entities = []
        for module in ENTITIES.values():
            asyncio.run(module.async_setup_entry(hass, self.entry, entities.extend))
        self.assertEqual([entity._attr_unique_id for entity in entities],
                         ['existing-entry_num_2', 'existing-entry_num_3', 'existing-entry_wh_ww'])
        self.entry.data['hk2_installed'] = False
        entities = []
        asyncio.run(ENTITIES['number'].async_setup_entry(hass, self.entry, entities.extend))
        self.assertEqual([entity._attr_unique_id for entity in entities], ['existing-entry_num_2'])
        self.assertEqual(self.water._attr_supported_features, 1)

    def test_temperature_boundaries_and_steps(self):
        for value in (20, 80):
            self.number.set_native_value(value)
            self.assertEqual(self.number._attr_native_value, value)
        for value in (30, 70, 51.7):
            self.water.set_temperature(temperature=value)
            self.assertEqual(self.water.target_temperature, value)
        count = len(self.hub._client.writes)
        for value in (19, 81, 20.5, True, '50', None, float('nan'), float('inf')):
            with self.assertRaises(ServiceValidationError):
                self.number.set_native_value(value)
        for value in (29.9, 70.1, 50.01, False, '50', None, float('nan'), float('-inf')):
            with self.assertRaises(ServiceValidationError):
                self.water.set_temperature(temperature=value)
        self.assertEqual(len(self.hub._client.writes), count)

    def test_failed_write_never_sets_requested_value(self):
        self.number.update()
        self.water.update()
        self.hub._client.ack = Response(error=True)
        with self.assertRaises(HomeAssistantError):
            self.number.set_native_value(60)
        with self.assertRaises(HomeAssistantError):
            self.water.set_temperature(temperature=60)
        self.assertIsNone(self.number._attr_native_value)
        self.assertIsNone(self.water.target_temperature)
        self.assertFalse(self.number.available)
        self.assertFalse(self.water.available)
        self.assertEqual(self.number.extra_state_attributes["setpoint_confirmation"], "write_failed")
        self.assertEqual(self.water.extra_state_attributes["setpoint_confirmation"], "write_failed")

    def test_readback_mismatch_preserves_actual_value(self):
        self.hub._client.readback = 450
        with self.assertRaisesRegex(HomeAssistantError, 'weicht ab'):
            self.number.set_native_value(60)
        self.assertEqual(self.number._attr_native_value, 45)
        with self.assertRaisesRegex(HomeAssistantError, 'weicht ab'):
            self.water.set_temperature(temperature=60)
        self.assertEqual(self.water.target_temperature, 45)

    def test_successful_ack_failed_readback_becomes_unknown(self):
        for address, entity, invoke in ((2, self.number, lambda: self.number.set_native_value(60)),
                                        (8, self.water, lambda: self.water.set_temperature(temperature=60))):
            self.hub._client.overrides[('holding', address)] = None
            self.hub._retry_after = 0
            with self.assertRaisesRegex(HomeAssistantError, 'Rücklesen'):
                invoke()
            self.assertFalse(entity.available)
        self.assertIsNone(self.number._attr_native_value)
        self.assertIsNone(self.water.target_temperature)

    def test_no_simulated_values_for_sentinels_and_zero(self):
        for raw in (0x7FFF, 0x8000, 0xFFFF):
            self.hub._client.stored[8] = raw
            self.water.update()
            self.assertIsNone(self.water.target_temperature)
            self.assertFalse(self.water.available)
        self.hub._client.stored[8] = 0
        self.water.update()
        self.assertEqual(self.water.target_temperature, 0)
        self.assertIsNone(self.water._attr_current_operation)

    def test_old_entity_actions_cannot_bypass_lock(self):
        switch = ENTITIES['switch'].ParadigmaSwitch(self.hub, 'dhw_enable', 4, self.entry)
        self.assertEqual(switch._attr_unique_id, 'existing-entry_switch_4')
        for action in (switch.turn_on, switch.turn_off, self.water.turn_on, self.water.turn_off):
            with self.assertRaises(HomeAssistantError):
                action()
        self.hub.revoke_control()
        for action in (lambda: self.number.set_native_value(60),
                       lambda: self.water.set_temperature(temperature=60)):
            with self.assertRaises(HomeAssistantError):
                action()
        self.assertEqual(self.hub._client.writes, [])


class PermissionFlowTests(unittest.TestCase):
    def data(self, **kwargs):
        return dict(name='PELEO', host='offline.example', port=502, slave_id=1, **kwargs)

    def test_new_installation_defaults_to_false(self):
        flow = FLOW['ConfigFlow']()
        flow.hass = FakeHass()
        form = asyncio.run(flow.async_step_user())
        self.assertIs(next(key.default for key in form['data_schema'] if key == ALLOW), False)
        result = asyncio.run(flow.async_step_user(self.data()))
        self.assertIs(result['data'][ALLOW], False)

    def test_invalid_permission_rejected_by_both_flows(self):
        for permission in (None, 0, 1, 'true', 'false', [], {}):
            user = FLOW['ConfigFlow']()
            user.hass = FakeHass()
            with patch.dict(FLOW, {'ParadigmaHub': lambda *a: self.fail('Unexpected connection')}):
                result = asyncio.run(user.async_step_user(self.data(allow_control=permission)))
            self.assertEqual(result['errors'][ALLOW], 'invalid_allow_control')
            entry = SimpleNamespace(entry_id='existing-entry', options={}, data=self.data())
            options = FLOW['OptionsFlowHandler'](entry)
            options.config_entry = entry
            options.hass = FakeHass()
            result = asyncio.run(options.async_step_init({ALLOW: permission}))
            self.assertEqual(result['errors'][ALLOW], 'invalid_allow_control')
            self.assertNotIn(ALLOW, entry.data)

    def test_legacy_and_stale_options_do_not_grant_permission(self):
        entry = SimpleNamespace(entry_id='existing-entry', data=self.data(), options={ALLOW: True})
        options = FLOW['OptionsFlowHandler'](entry)
        options.config_entry = entry
        options.hass = FakeHass()
        form = asyncio.run(options.async_step_init())
        self.assertIs(next(key.default for key in form['data_schema'] if key == ALLOW), False)
        asyncio.run(options.async_step_init({'scan_interval': 40}))
        self.assertIs(entry.data[ALLOW], False)

    def test_endpoint_change_requires_a_second_explicit_grant(self):
        for field, value in (("host", "other.example"), ("port", 503), ("slave_id", 2)):
            entry = SimpleNamespace(entry_id='existing-entry', options={}, data=self.data(allow_control=True))
            flow = FLOW['OptionsFlowHandler'](entry)
            flow.config_entry = entry
            flow.hass = FakeHass()
            asyncio.run(flow.async_step_init({field: value, ALLOW: True}))
            self.assertIs(entry.data[ALLOW], False)
            asyncio.run(flow.async_step_init({ALLOW: True}))
            self.assertIs(entry.data[ALLOW], True)

    def test_identical_options_save_does_not_revoke_without_a_reload(self):
        data = self.data(allow_control=True)
        entry = SimpleNamespace(entry_id='existing-entry', data=data, options=dict(data))
        hub = make_hub(True)
        flow = FLOW['OptionsFlowHandler'](entry)
        flow.config_entry = entry
        flow.hass = FakeHass()
        flow.hass.data = {'paradigma': {entry.entry_id: hub}}
        asyncio.run(flow.async_step_init({ALLOW: True}))
        self.assertTrue(hub.control_enabled)

    def test_connection_test_never_receives_write_permission(self):
        hubs = []
        def factory(*args, **kwargs):
            hub = HUB.ParadigmaHub(*args, **kwargs)
            hubs.append(hub)
            return hub
        flow = FLOW['ConfigFlow']()
        flow.hass = FakeHass()
        with patch.dict(FLOW, {'ParadigmaHub': factory}):
            result = asyncio.run(flow.async_step_user(self.data(allow_control=True)))
        self.assertIs(result['data'][ALLOW], True)
        self.assertFalse(hubs[0]._allow_control)
        self.assertTrue(hubs[0]._closed)
        self.assertEqual(hubs[0]._client.calls, [])

    def test_explicit_grant_revokes_old_runtime_and_partial_save_locks(self):
        entry = SimpleNamespace(entry_id='existing-entry', options={}, data=self.data(allow_control=False))
        hub = make_hub(True)
        options = FLOW['OptionsFlowHandler'](entry)
        options.config_entry = entry
        options.hass = FakeHass()
        options.hass.data = {'paradigma': {entry.entry_id: hub}}
        asyncio.run(options.async_step_init({ALLOW: True}))
        self.assertIs(entry.data[ALLOW], True)
        self.assertFalse(hub.control_enabled)
        asyncio.run(options.async_step_init({'scan_interval': 60}))
        self.assertIs(entry.data[ALLOW], False)


class PermissionLifecycleTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        LifecycleHub.instances = []
        LifecycleHub.connect_ok = True
        LifecycleHub.no_responses = False
        self.hass = LifecycleHass()
        self.entry = Entry()
        self.entry.options = {ALLOW: True}

    async def test_legacy_and_invalid_entries_load_sensors_only(self):
        for permission in (None, False, 1, 'true'):
            if permission is not None:
                self.entry.data[ALLOW] = permission
            await SETUP['async_setup_entry'](self.hass, self.entry)
            hub = LifecycleHub.instances[-1]
            self.assertFalse(hub.control_enabled)
            self.assertEqual(hub.platforms, ['sensor'])
            self.assertTrue(any(e._key == 'boiler_hours' for e in self.hass.entities))
            await SETUP['async_unload_entry'](self.hass, self.entry)
            self.entry.data.pop(ALLOW, None)

    async def test_grant_revoke_and_reload_preserve_sensor_identity(self):
        await SETUP['async_setup_entry'](self.hass, self.entry)
        original = [e._attr_unique_id for e in self.hass.entities]
        self.entry.data[ALLOW] = True
        await SETUP['update_listener'](self.hass, self.entry)
        await SETUP['async_unload_entry'](self.hass, self.entry)
        await SETUP['async_setup_entry'](self.hass, self.entry)
        enabled = LifecycleHub.instances[-1]
        self.assertTrue(enabled.control_enabled)
        self.assertEqual([e._attr_unique_id for e in self.hass.entities], original)
        self.entry.data[ALLOW] = False
        await SETUP['update_listener'](self.hass, self.entry)
        self.assertFalse(enabled.control_enabled)
        await SETUP['async_unload_entry'](self.hass, self.entry)
        self.assertIn(('unload', ['sensor', 'number', 'switch', 'water_heater']), self.hass.events)
        await SETUP['async_setup_entry'](self.hass, self.entry)
        self.assertEqual(LifecycleHub.instances[-1].platforms, ['sensor'])
        self.assertEqual([e._attr_unique_id for e in self.hass.entities], original)

    async def test_real_hub_setup_refresh_reload_do_not_write(self):
        hubs = []
        class RuntimeHub(HUB.ParadigmaHub):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._client = WriteClient()
                hubs.append(self)

            @property
            def closed(self):
                return self._closed

        for permission in (False, True):
            self.entry.data[ALLOW] = permission
            with patch.dict(SETUP, {'ParadigmaHub': RuntimeHub}):
                await SETUP['async_setup_entry'](self.hass, self.entry)
                hub = hubs[-1]
                await hub.coordinator.async_refresh()
                self.assertEqual(hub._client.writes, [])
                identities = [e._attr_unique_id for e in self.hass.entities]
                self.assertIn('existing-entry_holding_32_27', identities)
                await SETUP['update_listener'](self.hass, self.entry)
                self.assertFalse(hub.control_enabled)
                await SETUP['async_unload_entry'](self.hass, self.entry)
                self.assertEqual(hub._client.writes, [])

    async def test_failed_platform_cleanup_retains_only_a_revoked_runtime(self):
        self.entry.data[ALLOW] = True
        self.hass.forward_error = RuntimeError('platform failure')
        self.hass.unload_ok = False
        with self.assertLogs(SETUP['_LOGGER'], level='ERROR'):
            with self.assertRaises(RuntimeError):
                await SETUP['async_setup_entry'](self.hass, self.entry)
        hub = LifecycleHub.instances[-1]
        self.assertFalse(hub.control_enabled)
        self.assertFalse(hub.closed)

    async def test_failed_reload_or_unload_keeps_writes_revoked(self):
        self.entry.data[ALLOW] = True
        await SETUP['async_setup_entry'](self.hass, self.entry)
        hub = LifecycleHub.instances[-1]
        self.hass.unload_ok = False
        self.assertFalse(await SETUP['async_unload_entry'](self.hass, self.entry))
        self.assertFalse(hub.control_enabled)
        self.assertFalse(hub.closed)
        async def fail_reload(entry_id):
            raise RuntimeError('reload failed')
        self.hass.config_entries.async_reload = fail_reload
        with self.assertRaises(RuntimeError):
            await SETUP['update_listener'](self.hass, self.entry)
        self.assertFalse(hub.control_enabled)
