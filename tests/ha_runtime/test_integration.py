"""Integration QA with HA's real flows, entries, registries and entity platforms."""
from copy import deepcopy

from homeassistant.config_entries import ConfigEntryState
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.paradigma.const import DOMAIN

CONNECTION = dict(name="Paradigma Heizung", host="controller.invalid", port=502,
                  slave_id=1, scan_interval=30, model="systacomfort_ii")
COMPONENTS = ["general", "boiler", "buffer", "hk1", "hk2", "dhw", "circulation", "solar", "pool", "room"]
TARGETS = ["external_flow_hk1", "target_buffer_top", "target_boiler"]


def entry_data(**changes):
    data = dict(CONNECTION, components=COMPONENTS.copy(),
                sensors=["outdoor_temp", "flow_hk1", "buffer_top", *TARGETS], controls=[], allow_control=False)
    return {**data, **changes}


async def finish_selection(manager, result, sensors, controls=None):
    """Submit each real form's validated keys without replacing HA flow handling."""
    while result.get("step_id") == "sensors":
        available = result["data_schema"].schema["sensors"].config["options"]
        chosen = [key for key in sensors if key in available]
        result = await manager.async_configure(result["flow_id"], {"sensors": chosen})
    assert result["step_id"] == "controls"
    result = await manager.async_configure(result["flow_id"], {
        "controls": controls or [], "confirm_control": bool(controls)})
    assert result["step_id"] == "summary"
    return await manager.async_configure(result["flow_id"], {})


async def setup_entry(hass, data=None, options=None, version=2):
    entry = MockConfigEntry(domain=DOMAIN, title="Paradigma Heizung", data=data or entry_data(),
                            options=options or {}, version=version)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    return entry


async def test_real_first_installation_and_targets(hass, simulated_modbus):
    manager = hass.config_entries.flow
    result = await manager.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    bad = await manager.async_configure(result["flow_id"], {**CONNECTION, "model": "systasmartc_ii"})
    assert bad["errors"] == {"model": "invalid_selection"}
    assert not simulated_modbus
    result = await manager.async_configure(result["flow_id"], CONNECTION)
    assert result["step_id"] == "components"
    result = await manager.async_configure(result["flow_id"], {"components": COMPONENTS})
    result = await finish_selection(manager, result, ["outdoor_temp", *TARGETS])
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    entry = result["result"]
    assert entry.version == 2
    assert entry.data["controls"] == []
    registry = er.async_get(hass)
    for address, expected in ((2, "54.3"), (44, "60.0"), (45, "72.0")):
        entity_id = registry.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_holding_{address}")
        assert entity_id
        assert hass.states.get(entity_id).state == expected
    # One short connection-test client, closed before the sole runtime client.
    assert len(simulated_modbus) == 2
    assert not simulated_modbus[0].connected
    assert sum(client.connected for client in simulated_modbus) == 1
    assert all(not client.writes for client in simulated_modbus)
    assert not any(entity.domain in ("number", "water_heater", "switch")
                   for entity in registry.entities.values())


async def test_real_options_reload_sensor_changes_no_duplicates(hass, simulated_modbus):
    entry = await setup_entry(hass, entry_data(sensors=["outdoor_temp", "flow_hk1"]))
    registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    original_device_ids = {device.id for device in device_registry.devices}
    original_flow_id = registry.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_input_1")
    for wanted in (["flow_hk1", *TARGETS], ["outdoor_temp", "flow_hk1"]):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["step_id"] == "init"
        result = await hass.config_entries.options.async_configure(result["flow_id"], {k: v for k, v in CONNECTION.items() if k != "name"})
        result = await hass.config_entries.options.async_configure(result["flow_id"], {"components": COMPONENTS})
        result = await finish_selection(hass.config_entries.options, result, wanted)
        assert result["type"] is FlowResultType.CREATE_ENTRY
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED
        assert set(entry.data["sensors"]) == set(wanted)
        assert {device.id for device in device_registry.devices} == original_device_ids
        assert registry.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_input_1") == original_flow_id
        identities = [entity.unique_id for entity in registry.entities.values() if entity.config_entry_id == entry.entry_id]
        assert len(identities) == len(set(identities))
        assert sum(client.connected for client in simulated_modbus) == 1
        assert all(not client.writes for client in simulated_modbus)
    assert len(simulated_modbus) == 3  # first setup plus exactly two reloads
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert not any(client.connected for client in simulated_modbus)


async def test_real_v1_migration_registry_options_and_legacy_permissions(hass, simulated_modbus):
    old = {key: value for key, value in CONNECTION.items() if key != "model"}
    old.update(allow_control=True, hk2_installed=False, boiler_installed=True, solar_installed=True,
               custom_setting="keep")
    options = dict(allow_control=False, hk2_installed=True, scan_interval=120,
                   unknown_option={"value": "keep"})
    entry = MockConfigEntry(domain=DOMAIN, title="Paradigma Heizung", data=old, options=options, version=1)
    entry.add_to_hass(hass)
    device_registry = dr.async_get(hass)
    old_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, entry.entry_id)},
        name="Paradigma Heizung", manufacturer="Paradigma", model="SystaSmartC II")
    registry = er.async_get(hass)
    old_sensor = registry.async_get_or_create("sensor", DOMAIN, f"{entry.entry_id}_input_1",
                                               suggested_object_id="paradigma_heizung_vorlauf_hk1",
                                               config_entry=entry, device_id=old_device.id)
    old_hours = registry.async_get_or_create("sensor", DOMAIN, f"{entry.entry_id}_holding_32_27",
                                              suggested_object_id="paradigma_heizung_peleo_14_betriebsstunden",
                                              config_entry=entry, device_id=old_device.id)
    old_number = registry.async_get_or_create("number", DOMAIN, f"{entry.entry_id}_num_2",
                                               suggested_object_id="paradigma_heizung_soll_vorlauf_hk1",
                                               config_entry=entry, device_id=old_device.id)
    old_water = registry.async_get_or_create("water_heater", DOMAIN, f"{entry.entry_id}_wh_ww",
                                              suggested_object_id="paradigma_heizung_warmwasser",
                                              config_entry=entry, device_id=old_device.id)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.version == 2
    assert entry.data["model"] == "legacy_unverified"
    assert entry.data["legacy_control_functions"] == ["flow_hk1", "dhw_target"]
    assert entry.options == options
    for key, value in old.items():
        assert entry.data[key] == value
    assert not set(TARGETS) & set(entry.data["sensors"])
    assert hass.states.get(old_sensor.entity_id).state == "23.0"
    assert hass.states.get(old_hours.entity_id).state == "123"
    assert hass.states.get(old_number.entity_id).state == "54.3"
    assert hass.states.get(old_water.entity_id) is not None
    assert {device.id for device in device_registry.devices} == {old_device.id}
    assert registry.async_get(old_sensor.entity_id).device_id == old_device.id
    hub = hass.data[DOMAIN][entry.entry_id]
    assert hub.can_write_register(2)
    assert hub.can_write_register(8)
    assert not hub.can_write_register(3)
    # A crafted expansion still cannot broaden the original legacy authority.
    changed = deepcopy(dict(entry.data))
    changed["components"].append("hk2")
    changed["controls"].append("flow_hk2")
    hass.config_entries.async_update_entry(entry, data=changed)
    assert not hub.write_register(3, 500)
    await hass.async_block_till_done()
    hub = hass.data[DOMAIN][entry.entry_id]
    assert hub.can_write_register(2)
    assert not hub.can_write_register(3)
    assert all(not client.writes for client in simulated_modbus)


async def test_real_sentinel_and_optional_register_availability(hass, simulated_modbus):
    entry = await setup_entry(hass)
    registry = er.async_get(hass)
    hub = hass.data[DOMAIN][entry.entry_id]
    client = simulated_modbus[0]
    for address in (2, 44, 45):
        entity_id = registry.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_holding_{address}")
        for sentinel in (0x8000, 0x7FFF, 0xFFFF):
            client.holding[address] = sentinel
            await hub.coordinator.async_refresh()
            await hass.async_block_till_done()
            assert hass.states.get(entity_id).state == "unavailable"
        client.holding[address] = 0
        await hub.coordinator.async_refresh()
        await hass.async_block_till_done()
        assert hass.states.get(entity_id).state == "0.0"
    client.missing.add(44)
    await hub.coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hub.coordinator.last_update_success
    target = registry.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_holding_44")
    assert hass.states.get(target).state == "unavailable"
    outdoor = registry.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_input_0")
    assert hass.states.get(outdoor).state == "23.0"
    assert not client.writes


async def test_real_controls_flow_and_hub_permissions(hass, simulated_modbus):
    entry = await setup_entry(hass)
    hub = hass.data[DOMAIN][entry.entry_id]
    for address in (2, 3, 8, 44, 45):
        assert not hub.write_register(address, 500)
    assert not hub.write_coil(4, True)
    assert not simulated_modbus[0].writes
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"], {k: v for k, v in CONNECTION.items() if k != "name"})
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"components": COMPONENTS})
    while result["step_id"] == "sensors":
        result = await hass.config_entries.options.async_configure(result["flow_id"], {"sensors": []})
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"controls": ["flow_hk1"], "confirm_control": False})
    assert result["errors"] == {"base": "confirm_control"}
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"controls": ["flow_hk1"], "confirm_control": True})
    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()
    hub = hass.data[DOMAIN][entry.entry_id]
    assert hub.can_write_register(2)
    for address in (3, 8, 44, 45):
        assert not hub.write_register(address, 500)
    assert hub.write_register(2, 500)  # Only simulated transport; explicit single-function grant.
    assert simulated_modbus[-1].writes == [(2, [500], 1)]
    assert not hub.write_register(2, 801)
    registry = er.async_get(hass)
    assert registry.async_get_entity_id("number", DOMAIN, f"{entry.entry_id}_num_2")
    assert not registry.async_get_entity_id("number", DOMAIN, f"{entry.entry_id}_num_3")
    assert not registry.async_get_entity_id("water_heater", DOMAIN, f"{entry.entry_id}_wh_ww")


async def test_real_translations_form_labels_and_entity_names(hass, simulated_modbus):
    from homeassistant.helpers.translation import async_get_translations
    entry = await setup_entry(hass)
    for language in ("de", "en"):
        config = await async_get_translations(hass, language, "config", {DOMAIN})
        options = await async_get_translations(hass, language, "options", {DOMAIN})
        selectors = await async_get_translations(hass, language, "selector", {DOMAIN})
        entities = await async_get_translations(hass, language, "entity", {DOMAIN})
        prefix = f"component.{DOMAIN}."
        assert config[prefix + "config.step.user.data.model"]
        assert options[prefix + "options.step.init.data.model"]
        for category, result in (("config", config), ("options", options)):
            for step, field in (("components", "components"), ("sensors", "sensors"),
                                ("controls", "confirm_control")):
                assert result[prefix + f"{category}.step.{step}.data.{field}"]
            assert result[prefix + f"{category}.step.summary.description"]
        for key in TARGETS:
            assert selectors[prefix + f"selector.sensors.options.{key}"]
            assert entities[prefix + f"entity.sensor.{key}.name"]
    assert (await async_get_translations(hass, "de", "entity", {DOMAIN}))[
        f"component.{DOMAIN}.entity.sensor.target_boiler.name"] == "Kesselsolltemperatur"
    assert entry.state is ConfigEntryState.LOADED


async def test_real_migrated_options_edit_preserves_mirror_and_one_reload(hass, simulated_modbus):
    old = {key: value for key, value in CONNECTION.items() if key != "model"}
    old.update(allow_control=True, boiler_installed=True, hk2_installed=False)
    options = dict(scan_interval=90, hk2_installed=True, unknown_option={"keep": [1, 2]})
    entry = await setup_entry(hass, old, options, version=1)
    old_registry = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_input_1")
    old_devices = {device.id for device in dr.async_get(hass).devices}
    original_sensor_ids = set(entry.data["sensors"])
    manager = hass.config_entries.options
    result = await manager.async_init(entry.entry_id)
    result = await manager.async_configure(result["flow_id"], {
        "host": "controller.invalid", "port": 502, "slave_id": 1,
        "scan_interval": 60, "model": "legacy_unverified"})
    result = await manager.async_configure(result["flow_id"], {"components": list(entry.data["components"])})
    result = await finish_selection(manager, result, original_sensor_ids, ["flow_hk1"])
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options == options
    assert entry.data["scan_interval"] == 60
    assert set(entry.data["sensors"]) == original_sensor_ids
    assert entry.data["controls"] == ["flow_hk1"]
    assert len(simulated_modbus) == 2  # exactly one options reload
    assert sum(client.connected for client in simulated_modbus) == 1
    assert {device.id for device in dr.async_get(hass).devices} == old_devices
    assert er.async_get(hass).async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_input_1") == old_registry
    hub = hass.data[DOMAIN][entry.entry_id]
    assert hub.can_write_register(2)
    assert not hub.can_write_register(3)
    assert not hub.can_write_register(8)
    assert hub.coordinator.update_interval.total_seconds() == 60
    assert all(not client.writes for client in simulated_modbus)
