"""Exercise production flow classes with offline framework interfaces."""
import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Marker(str):
    def __new__(cls, key, default=None):
        obj = super().__new__(cls, key)
        obj.default = default
        return obj


class Flow:
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__()

    def async_show_form(self, **kwargs):
        return kwargs

    def async_create_entry(self, **kwargs):
        return kwargs


class FakeHub:
    """Only a local connection-test substitute; never opens a socket."""
    def __init__(self, *args):
        self.args = args

    def connect(self):
        return True

    def close(self):
        pass


def load_flow_classes():
    # Execute the unchanged production class bodies, replacing imports only.
    source = ast.parse((ROOT / 'custom_components/paradigma/config_flow.py').read_text())
    constants = ast.parse((ROOT / 'custom_components/paradigma/const.py').read_text())
    namespace = {
        'config_entries': SimpleNamespace(ConfigFlow=Flow, OptionsFlow=Flow),
        'callback': lambda func: func,
        'vol': SimpleNamespace(Required=Marker, Optional=Marker, Schema=lambda schema: schema),
        'ParadigmaHub': FakeHub,
        'CONF_HOST': 'host', 'CONF_PORT': 'port', 'CONF_NAME': 'name',
        'CONF_SCAN_INTERVAL': 'scan_interval',
    }
    for node in constants.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            for target in node.targets:
                namespace[target.id] = node.value.value
    config_source = ast.parse((ROOT / 'custom_components/paradigma/configuration.py').read_text())
    import logging
    namespace['_LOGGER'] = logging.getLogger('test_configuration')
    config_nodes = [node for node in config_source.body if isinstance(node, (ast.FunctionDef, ast.Assign)) and not (isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == '_LOGGER' for t in node.targets))]
    exec(compile(ast.Module(body=config_nodes, type_ignores=[]), 'configuration.py', 'exec'), namespace)
    classes = ast.Module(body=[node for node in source.body if isinstance(node, ast.ClassDef)], type_ignores=[])
    exec(compile(classes, 'config_flow.py', 'exec'), namespace)
    return namespace


FLOW = load_flow_classes()


class FakeHass:
    def __init__(self):
        self.config_entries = SimpleNamespace(async_update_entry=self.update_entry)

    @staticmethod
    async def async_add_executor_job(func, *args):
        return func(*args)

    @staticmethod
    def update_entry(entry, **kwargs):
        entry.data = kwargs['data']


class ConfigFlowTests(unittest.TestCase):
    def test_new_installation_schema_and_sensor_defaults(self):
        flow = FLOW['ConfigFlow']()
        flow.hass = FakeHass()
        form = asyncio.run(flow.async_step_user())
        schema = form['data_schema']
        self.assertNotIn('wood_installed', schema)
        self.assertEqual(next(k.default for k in schema if k == 'name'), 'PELEO 14')
        data = {str(key): key.default for key in schema}
        data['host'] = 'offline.example'
        result = asyncio.run(flow.async_step_user(data))
        self.assertEqual(result['data'], data)
        self.assertEqual(result['title'], 'PELEO 14')
        self.assertEqual(FLOW['DOMAIN'], 'paradigma')
        self.assertEqual(FLOW['ConfigFlow'].VERSION, 1)

    def test_old_options_can_be_opened_and_saved(self):
        for boiler in (False, True):
            entry = SimpleNamespace(data={
                'name': 'Bestehender Name', 'host': 'offline.example',
                'port': 502, 'slave_id': 1, 'wood_installed': True,
                'boiler_installed': boiler, 'solar_installed': False,
            })
            original = entry.data.copy()
            flow = FLOW['OptionsFlowHandler'](entry)
            # HA supplies this property; the test does not validate that framework.
            flow.config_entry = entry
            flow.hass = FakeHass()
            form = asyncio.run(flow.async_step_init())
            self.assertNotIn('wood_installed', form['data_schema'])
            self.assertEqual(next(k.default for k in form['data_schema'] if k == 'boiler_installed'), boiler)
            result = asyncio.run(flow.async_step_init({'pool_installed': True}))
            for key, value in original.items():
                self.assertEqual(entry.data[key], value)
            self.assertTrue(entry.data['pool_installed'])
            self.assertEqual(result['data'], entry.data)

    def test_every_schema_field_has_translation(self):
        import json
        flow = FLOW['ConfigFlow']()
        flow.hass = FakeHass()
        user_schema = asyncio.run(flow.async_step_user())['data_schema']
        options = FLOW['OptionsFlowHandler'](None)
        options.config_entry = SimpleNamespace(data={})
        options.hass = FakeHass()
        option_schema = asyncio.run(options.async_step_init())['data_schema']
        for name in ('strings.json', 'translations/de.json', 'translations/en.json'):
            data = json.loads((ROOT / 'custom_components/paradigma' / name).read_text())
            self.assertEqual(set(user_schema), set(data['config']['step']['user']['data']))
            self.assertEqual(set(option_schema), set(data['options']['step']['init']['data']))


if __name__ == '__main__':
    unittest.main()
