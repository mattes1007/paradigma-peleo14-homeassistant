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
    from test_peleo_sensors import SENSOR
    catalog = SENSOR.CATALOG
    namespace.update({k: getattr(catalog, k) for k in ('MODELS', 'VERIFIED_MODELS', 'REGISTERS', 'CONTROLS', 'COMPONENTS', 'COMPONENT_NAMES', 'migrate_data', 'allowed_addresses')})
    namespace['select'] = lambda *a, **kw: list(a[0])
    classes = ast.Module(body=[node for node in source.body if isinstance(node, ast.ClassDef)], type_ignores=[])
    exec(compile(classes, 'config_flow.py', 'exec'), namespace)
    return namespace


FLOW = load_flow_classes()


class FakeHass:
    def __init__(self):
        self.data = {}
        self.config_entries = SimpleNamespace(async_update_entry=self.update_entry)

    @staticmethod
    async def async_add_executor_job(func, *args):
        return func(*args)

    @staticmethod
    def update_entry(entry, **kwargs):
        entry.data = kwargs['data']


class ConfigFlowTests(unittest.TestCase):
    def test_new_wizard_read_only_and_three_targets(self):
        flow = FLOW['ConfigFlow']()
        flow.hass = FakeHass()
        result = asyncio.run(flow.async_step_user(dict(name='PELEO', host='offline.example', port=502, slave_id=1, model='systacomfort_ii')))
        self.assertEqual(result['step_id'], 'components')
        result = asyncio.run(flow.async_step_components({'components': ['hk1','buffer','boiler']}))
        while flow._remaining:
            keys = [k for k,r in FLOW['REGISTERS'].items() if r.component == flow._remaining[0] and r.definition[6] != 'room_sensor_installed']
            result = asyncio.run(flow.async_step_sensors({'sensors': keys}))
        result = asyncio.run(flow.async_step_controls({'controls': [], 'confirm_control': False}))
        self.assertEqual(result['step_id'], 'summary')
        result = asyncio.run(flow.async_step_summary({}))
        self.assertFalse(result['data']['allow_control'])
        self.assertTrue({'external_flow_hk1','target_buffer_top','target_boiler'} <= set(result['data']['sensors']))
        self.assertEqual(FLOW['ConfigFlow'].VERSION, 2)

    def test_options_saved_only_at_summary(self):
        entry = SimpleNamespace(entry_id='existing-entry', options={}, data=dict(name='Old',host='offline.example',port=502,slave_id=1,allow_control=True))
        flow = FLOW['OptionsFlowHandler'](entry)
        flow.config_entry = entry
        flow.hass = FakeHass()
        old = entry.data.copy()
        asyncio.run(flow.async_step_init({'scan_interval': 40}))
        self.assertEqual(entry.data, old)
        asyncio.run(flow.async_step_components({'components': ['hk1']}))
        asyncio.run(flow.async_step_sensors({'sensors': ['flow_hk1']}))
        asyncio.run(flow.async_step_controls({'controls': ['flow_hk1'], 'confirm_control': True}))
        result = asyncio.run(flow.async_step_summary({}))
        self.assertEqual(result['data'], {})
        self.assertEqual(entry.data['controls'], ['flow_hk1'])
        self.assertEqual(entry.data['scan_interval'], 40)

    def test_translations_cover_wizard(self):
        import json
        for filename in ('strings.json','translations/de.json','translations/en.json'):
            d=json.loads((ROOT/'custom_components/paradigma'/filename).read_text())
            for section in ('config','options'):
                self.assertTrue({'components','sensors','controls','summary'} <= set(d[section]['step']))
            self.assertEqual(set(d['selector']['sensors']['options']),set(FLOW['REGISTERS']))


if __name__ == '__main__':
    unittest.main()
