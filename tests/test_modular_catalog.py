"""Targeted offline migration, selection and coordinator safety regressions."""
import asyncio
from types import SimpleNamespace
import unittest
from test_peleo_sensors import SENSOR, FakeHub, FakeHass
from test_p1_lifecycle import SETUP
from test_p3_control import make_hub
from test_peleo_config_flow import FLOW

C = SENSOR.CATALOG

class ModularTests(unittest.TestCase):
    def test_migration_preserves_every_legacy_sensor_and_identity(self):
        for old in ({}, {'allow_control': True, 'hk2_installed': True, 'room_sensor_installed': True, 'solar_installed': True, 'boiler_installed': False, 'private_unknown_option': 42}):
            new = C.migrate_data(old)
            self.assertEqual(C.selected_sensors(new), C.legacy_sensors(old))
            self.assertEqual(C.migrate_data(new),new)
            for key,value in old.items(): self.assertEqual(new[key],value)
            self.assertFalse({'external_flow_hk1','target_buffer_top','target_boiler'} & set(new['sensors']))
            for key in new['sensors']:
                d=C.REGISTERS[key].definition
                entity=SENSOR.ParadigmaSensor(SimpleNamespace(data={}),SimpleNamespace(entry_id='old'),d)
                self.assertEqual(entity._attr_unique_id,f'old_{d[4]}_{d[5]}')
                self.assertEqual(entity.device_info['identifiers'],{('paradigma','old')})

    def test_actual_entry_migration_version_and_options(self):
        entry=SimpleNamespace(version=1,data={'allow_control':True,'hk2_installed':True})
        class Entries:
            def async_update_entry(self,e,**changes):
                for k,v in changes.items(): setattr(e,k,v)
        self.assertTrue(asyncio.run(SETUP['async_migrate_entry'](SimpleNamespace(config_entries=Entries()),entry)))
        self.assertEqual(entry.version,2)
        self.assertEqual(set(C.allowed_addresses(entry.data)),{2,3,8})

    def test_targets_and_sentinels(self):
        for key,address in [('external_flow_hk1',2),('target_buffer_top',44),('target_boiler',45)]:
            d=C.REGISTERS[key].definition
            for raw,expected in [(543,54.3),(0,0),(0x8000,None),(0x7fff,None),(0xffff,None),(None,None)]:
                co=SimpleNamespace(data={f'holding_{address}':raw},last_update_success=True)
                e=SENSOR.ParadigmaSensor(co,SimpleNamespace(entry_id='old'),d)
                self.assertEqual(e.native_value,expected)
                self.assertEqual(e.available,expected is not None)

    def test_read_selection_has_no_write_grant_and_optional_failure_is_local(self):
        cfg=dict(model='systacomfort_ii',components=['hk1','buffer'],sensors=['flow_hk1','external_flow_hk1','target_buffer_top'],controls=[])
        hub=FakeHub()
        base=hub.read_holding_registers
        hub.read_holding_registers=lambda address,count: None if address==44 else base(address,count)
        co=SENSOR.ParadigmaDataCoordinator(FakeHass(hub),hub,cfg)
        data=asyncio.run(co._async_update_data())
        self.assertEqual(set(data),{'input_1','holding_2'})
        self.assertEqual(C.allowed_addresses(cfg),set())
        cfg['components']=['hk1']
        co=SENSOR.ParadigmaDataCoordinator(FakeHass(hub),hub,cfg)
        self.assertNotIn(('holding',44),co._read_plan)

    def test_hub_checks_each_function_and_blocks_raw_addresses(self):
        hub=make_hub(True)
        cfg=dict(model='systacomfort_ii',components=['hk1'],controls=['flow_hk1'])
        hub.address_permission=lambda address:address in C.allowed_addresses(cfg)
        self.assertTrue(hub.write_register(2,500))
        for address in (3,8,44,45,9992): self.assertFalse(hub.write_register(address,500))
        self.assertFalse(hub.write_register(2,801))
        self.assertFalse(hub.write_register(2,True))
        self.assertEqual(len(hub._client.writes),1)
        cfg['model']='systasmartc_ii'
        self.assertFalse(hub.write_register(2,500))

    def test_unverified_model_never_gets_new_functions(self):
        flow=FLOW['ConfigFlow']()
        flow.hass=__import__('test_peleo_config_flow').FakeHass()
        result=asyncio.run(flow.async_step_user(dict(name='Test',host='offline.example',port=502,slave_id=1,model='systasmartc_ii')))
        self.assertEqual(result['errors']['model'],'invalid_selection')

class SafetyMigrationRegressionTests(unittest.TestCase):
    def options_flow(self, data, options=None):
        entry = SimpleNamespace(entry_id="old", data=data.copy(), options=dict(options or {}))
        flow = FLOW["OptionsFlowHandler"](entry)
        flow.config_entry = entry
        flow.hass = __import__("test_peleo_config_flow").FakeHass()
        return entry, flow

    def test_legacy_snapshot_cannot_expand_with_later_hk2_selection(self):
        data = C.migrate_data({"allow_control": True, "hk2_installed": False})
        self.assertEqual(data["legacy_control_functions"], ["flow_hk1", "dhw_target"])
        data["components"].append("hk2")
        data["controls"].append("flow_hk2")
        data["hk2_installed"] = True
        self.assertEqual(C.allowed_addresses(data), {2, 8})
        self.assertEqual(C.migrate_data(data)["legacy_control_functions"], ["flow_hk1", "dhw_target"])
        hub = make_hub(True)
        hub.address_permission = lambda address: address in C.allowed_addresses(data)
        self.assertFalse(hub.write_register(3, 500))
        self.assertEqual(hub._client.calls, [])
        self.assertEqual(hub._client.writes, [])
        data["controls"] = ["flow_hk1"]
        self.assertEqual(C.allowed_addresses(data), {2})

    def test_unproven_or_malformed_legacy_evidence_is_not_a_grant(self):
        base = dict(model="legacy_unverified", components=["hk1", "hk2", "dhw"],
                    controls=["flow_hk1", "flow_hk2", "dhw_target"], legacy_control=True)
        self.assertEqual(C.allowed_addresses(base), set())
        self.assertEqual(C.migrate_data(base)["legacy_control_functions"], [])
        for value in (None, "flow_hk1", True):
            self.assertEqual(C.allowed_addresses({**base, "legacy_control_functions": value}), set())
        for value in (False, 1, "true"):
            self.assertEqual(C.allowed_addresses({**base, "legacy_control": value,
                                                 "legacy_control_functions": ["flow_hk1"]}), set())
        self.assertEqual(C.allowed_addresses({"allow_control": True, "hk2_installed": False}), {2, 8})
        for unit_id in (2, True, "1", None):
            self.assertEqual(C.migrate_data({"allow_control": True, "slave_id": unit_id})["controls"], [])

    def test_options_flow_rejects_new_legacy_function_and_requires_confirmation(self):
        old = dict(name="Old", host="offline.example", port=502, slave_id=1,
                   allow_control=True, hk2_installed=False)
        entry, flow = self.options_flow(old)
        asyncio.run(flow.async_step_init({}))
        flow._draft["components"].append("hk2")
        result = asyncio.run(flow.async_step_controls({"controls": ["flow_hk2"], "confirm_control": True}))
        self.assertEqual(result["errors"], {"base": "invalid_selection"})
        self.assertEqual(entry.data, old)
        result = asyncio.run(flow.async_step_controls({"controls": ["flow_hk1"]}))
        self.assertEqual(result["errors"], {"base": "confirm_control"})
        asyncio.run(flow.async_step_controls({"controls": ["flow_hk1"], "confirm_control": True}))
        asyncio.run(flow.async_step_summary({}))
        self.assertEqual(C.allowed_addresses(entry.data), {2})
        # Removing the grant cannot turn the historical snapshot into a new default.
        entry, flow = self.options_flow(entry.data)
        asyncio.run(flow.async_step_init({}))
        asyncio.run(flow.async_step_controls({"controls": []}))
        asyncio.run(flow.async_step_summary({}))
        self.assertEqual(C.allowed_addresses(entry.data), set())

    def test_supported_model_change_exposes_targets_without_granting_writes(self):
        old = dict(name="Old", host="offline.example", port=502, slave_id=1,
                   allow_control=True, boiler_installed=True)
        migrated = C.migrate_data(old)
        self.assertEqual(migrated["model"], "legacy_unverified")
        entry, flow = self.options_flow(migrated)
        asyncio.run(flow.async_step_init({"model": "systacomfort_ii"}))
        self.assertEqual(flow._draft["controls"], [])
        self.assertFalse(flow._draft["legacy_control"])
        targets = {"external_flow_hk1", "target_buffer_top", "target_boiler"}
        asyncio.run(flow.async_step_components({"components": migrated["components"]}))
        while flow._remaining:
            group = flow._remaining[0]
            chosen = [k for k in migrated["sensors"] if C.REGISTERS[k].component == group]
            chosen += [k for k in targets if C.REGISTERS[k].component == group]
            form = asyncio.run(flow.async_step_sensors())
            self.assertTrue(set(chosen) <= set(form["data_schema"]["sensors"]))
            asyncio.run(flow.async_step_sensors({"sensors": chosen}))
        asyncio.run(flow.async_step_controls({"controls": []}))
        asyncio.run(flow.async_step_summary({}))
        self.assertTrue(targets <= set(C.selected_sensors(entry.data)))
        self.assertTrue(set(migrated["sensors"]) <= set(C.selected_sensors(entry.data)))
        self.assertEqual(C.allowed_addresses(entry.data), set())
        hub = FakeHub()
        co = SENSOR.ParadigmaDataCoordinator(FakeHass(hub), hub, entry.data)
        self.assertTrue({("holding", 2), ("holding", 44), ("holding", 45)} <= set(co._read_plan))

    def test_model_downgrade_retains_old_sensors_but_hides_new_targets(self):
        data = C.migrate_data(dict(name="Old", host="offline.example", port=502, slave_id=1,
                                   boiler_installed=True))
        old_sensors = data["sensors"].copy()
        targets = ["external_flow_hk1", "target_buffer_top", "target_boiler"]
        data.update(model="systacomfort_ii", sensors=old_sensors + targets)
        entry, flow = self.options_flow(data)
        asyncio.run(flow.async_step_init({"model": "legacy_unverified"}))
        asyncio.run(flow.async_step_components({"components": data["components"]}))
        while flow._remaining:
            form = asyncio.run(flow.async_step_sensors())
            self.assertFalse(set(targets) & set(form["data_schema"]["sensors"]))
            chosen = [k for k in old_sensors if C.REGISTERS[k].component == flow._remaining[0]]
            asyncio.run(flow.async_step_sensors({"sensors": chosen}))
        asyncio.run(flow.async_step_controls({"controls": []}))
        asyncio.run(flow.async_step_summary({}))
        self.assertEqual(set(C.selected_sensors(entry.data)), set(old_sensors))

    def test_options_migration_and_saving_preserve_original_data_authority(self):
        data = dict(name="Old", host="offline.example", port=502, slave_id=1,
                    scan_interval=45, hk2_installed=False, solar_installed=True,
                    allow_control=False, custom_data="preserve")
        options = dict(host="stale.example", scan_interval=90, hk2_installed=True,
                       allow_control=True, unknown_option={"nested": [1, 2]})
        entry, _ = self.options_flow(data, options)
        entry.version = 1
        calls = []
        class Entries:
            def async_update_entry(self, e, **changes):
                calls.append(changes)
                for key, value in changes.items(): setattr(e, key, value)
        hass = SimpleNamespace(config_entries=Entries())
        self.assertTrue(asyncio.run(SETUP["async_migrate_entry"](hass, entry)))
        self.assertNotIn("options", calls[0])
        self.assertEqual(entry.options, options)
        for key, value in data.items(): self.assertEqual(entry.data[key], value)
        self.assertEqual(C.allowed_addresses(entry.data), set())
        self.assertFalse("hk2" in entry.data["components"])
        entry, flow = self.options_flow(entry.data, entry.options)
        asyncio.run(flow.async_step_init({"scan_interval": 60}))
        asyncio.run(flow.async_step_components({"components": []}))
        asyncio.run(flow.async_step_controls({"controls": []}))
        result = asyncio.run(flow.async_step_summary({}))
        self.assertEqual(entry.data["scan_interval"], 60)
        self.assertEqual(result["data"], options)
        self.assertEqual(entry.options, options)
        self.assertEqual(entry.data["custom_data"], "preserve")

    def test_supported_model_additional_control_requires_explicit_confirmation(self):
        data = C.migrate_data(dict(name="Old", host="offline.example", port=502, slave_id=1,
                                   allow_control=True, hk2_installed=False))
        entry, flow = self.options_flow(data)
        asyncio.run(flow.async_step_init({"model": "systacomfort_ii"}))
        flow._draft["components"].append("hk2")
        result = asyncio.run(flow.async_step_controls({"controls": ["flow_hk2"]}))
        self.assertEqual(result["errors"], {"base": "confirm_control"})
        self.assertEqual(C.allowed_addresses(entry.data), {2, 8})
        asyncio.run(flow.async_step_controls({"controls": ["flow_hk2"], "confirm_control": True}))
        asyncio.run(flow.async_step_summary({}))
        self.assertEqual(C.allowed_addresses(entry.data), {3})
        self.assertFalse(entry.data["legacy_control"])
        self.assertEqual(entry.data["legacy_control_functions"], [])

    def test_hub_missing_invalid_or_failed_individual_policy_blocks_direct_calls(self):
        for policy in (None, False, lambda address: 1, lambda address: "true", lambda address: None):
            hub = make_hub(True)
            hub.address_permission = policy
            self.assertFalse(hub.write_register(2, 500))
            self.assertEqual(hub._client.calls, [])
            self.assertEqual(hub._client.writes, [])
        hub = make_hub(True)
        del hub.address_permission
        self.assertFalse(hub.write_register(2, 500))
        def failed(address): raise RuntimeError("policy unavailable")
        hub.address_permission = failed
        self.assertFalse(hub.write_register(2, 500))
        self.assertEqual(hub._client.writes, [])
        hub.address_permission = lambda address: True
        self.assertFalse(hub.write_coil(4, True))
        self.assertFalse(hub.write_coil(6, True))

    def test_individual_grant_is_rechecked_after_each_live_precondition(self):
        for address, function in ((2, "flow_hk1"), (3, "flow_hk2"), (8, "dhw_target")):
            data = dict(model="systacomfort_ii", components=["hk1", "hk2", "dhw"], controls=[function])
            hub = make_hub(True)
            hub.address_permission = lambda target: target in C.allowed_addresses(data)
            hub._client.after_precondition = lambda: data.update(controls=[])
            self.assertFalse(hub.write_register(address, 500))
            self.assertNotEqual(hub._client.calls, [])
            self.assertEqual(hub._client.writes, [])

if __name__=='__main__': unittest.main()
