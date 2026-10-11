"""Native modular setup and options wizard; saving never writes Modbus."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_NAME, CONF_SCAN_INTERVAL
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig, SelectSelectorMode
from .const import DOMAIN, DEFAULT_NAME, DEFAULT_PORT, DEFAULT_SLAVE_ID, CONF_SLAVE_ID, DEFAULT_SCAN_INTERVAL
from .configuration import validate_config
from .catalog import COMPONENTS, MODELS, VERIFIED_MODELS, REGISTERS, CONTROLS, COMPONENT_NAMES, migrate_data, allowed_addresses
from .hub import ParadigmaHub


def select(options, key, multiple=True):
    return SelectSelector(SelectSelectorConfig(options=list(options), multiple=multiple,
        mode=SelectSelectorMode.DROPDOWN, translation_key=key))


class Wizard:
    """Shared steps, with one sensor form per chosen component."""
    def component_label(self, key):
        language = getattr(getattr(self.hass, "config", None), "language", "en")
        return COMPONENT_NAMES[key][0 if language == "de" else 1]

    async def connection(self, step, user_input):
        errors = {}
        if not hasattr(self, '_draft'):
            self._draft = migrate_data(self.config_entry.data) if isinstance(self, OptionsFlowHandler) else {}
        if user_input is not None:
            draft = {**self._draft, **user_input}
            draft.setdefault('model', 'systacomfort_ii')
            errors = validate_config(draft)
            if (draft.get('model') not in MODELS or
                    (not isinstance(self, OptionsFlowHandler) and draft.get('model') not in VERIFIED_MODELS)):
                errors['model'] = 'invalid_selection'
            if not errors:
                if isinstance(self, OptionsFlowHandler):
                    if any(draft.get(k) != migrate_data(self.config_entry.data).get(k) for k in (CONF_HOST, CONF_PORT, CONF_SLAVE_ID, 'model')):
                        draft['controls'] = []
                        draft['legacy_control'] = False
                        draft['legacy_control_functions'] = []
                else:
                    hub = ParadigmaHub(self.hass, draft[CONF_NAME], draft[CONF_HOST], draft[CONF_PORT], draft[CONF_SLAVE_ID])
                    try:
                        connected = await self.hass.async_add_executor_job(hub.connect)
                    finally:
                        await self.hass.async_add_executor_job(hub.close)
                    if not connected:
                        errors['base'] = 'cannot_connect'
                if not errors:
                    self._draft = draft
                    return await self.async_step_components()
        d = self._draft
        schema = {
            vol.Required(CONF_HOST, default=d.get(CONF_HOST, '')): str,
            vol.Required(CONF_PORT, default=d.get(CONF_PORT, DEFAULT_PORT)): int,
            vol.Required(CONF_SLAVE_ID, default=d.get(CONF_SLAVE_ID, DEFAULT_SLAVE_ID)): int,
            vol.Required('model', default=d.get('model', 'systacomfort_ii')): select(MODELS, 'models', False),
            vol.Required(CONF_SCAN_INTERVAL, default=d.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)): int,
        }
        if step == 'user':
            schema[vol.Required(CONF_NAME, default=DEFAULT_NAME)] = str
        return self.async_show_form(step_id=step, data_schema=vol.Schema(schema), errors=errors)

    async def async_step_components(self, user_input=None):
        if user_input is not None:
            chosen = user_input.get('components', [])
            if any(k not in COMPONENTS for k in chosen):
                return self.async_show_form(step_id='components', errors={'base': 'invalid_selection'})
            self._draft['components'] = chosen
            self._remaining = [c for c in COMPONENTS if c in chosen and c != 'room']
            self._selected = []
            return await self.async_step_sensors()
        return self.async_show_form(step_id='components', data_schema=vol.Schema({
            vol.Required('components', default=self._draft.get('components', ['general', 'boiler', 'buffer', 'hk1', 'dhw', 'circulation'])): select(COMPONENTS, 'components')}))

    async def async_step_sensors(self, user_input=None):
        if not self._remaining:
            self._draft['sensors'] = self._selected
            return await self.async_step_controls()
        group = self._remaining[0]
        keys = [k for k,r in REGISTERS.items() if r.component == group and (r.definition[6] != 'room_sensor_installed' or 'room' in self._draft['components'])]
        if self._draft['model'] not in VERIFIED_MODELS:
            # Unverified models retain known legacy reads, but gain no new ones.
            keys = [k for k in keys if REGISTERS[k].default and k in self._draft.get('sensors', [])]
        if user_input is not None:
            chosen = user_input.get('sensors', [])
            if any(k not in keys for k in chosen):
                return self.async_show_form(step_id='sensors', errors={'base': 'invalid_selection'})
            self._selected.extend(chosen)
            self._remaining.pop(0)
            return await self.async_step_sensors()
        defaults = [k for k in keys if k in self._draft.get('sensors', [k for k,r in REGISTERS.items() if r.default])]
        return self.async_show_form(step_id='sensors', data_schema=vol.Schema({
            vol.Required('sensors', default=defaults): select(keys, 'sensors')}),
            description_placeholders={'component': self.component_label(group)})

    async def async_step_controls(self, user_input=None):
        keys = [k for k,v in CONTROLS.items() if v[0] in self._draft['components'] and
                (self._draft['model'] in VERIFIED_MODELS or v[1] in allowed_addresses(self._draft))]
        errors = {}
        if user_input is not None:
            chosen = user_input.get('controls', [])
            if any(k not in keys for k in chosen):
                errors['base'] = 'invalid_selection'
            elif chosen and user_input.get('confirm_control') is not True:
                errors['base'] = 'confirm_control'
            else:
                self._draft['controls'] = chosen
                self._draft['allow_control'] = bool(chosen)
                return await self.async_step_summary()
        return self.async_show_form(step_id='controls', data_schema=vol.Schema({
            vol.Required('controls', default=[k for k in self._draft.get('controls', []) if k in keys]): select(keys, 'controls'),
            vol.Required('confirm_control', default=False): bool}), errors=errors)

    async def async_step_summary(self, user_input=None):
        if user_input is not None:
            d = self._draft
            for key, component in [('hk2_installed','hk2'), ('boiler_installed','boiler'), ('solar_installed','solar'), ('pool_installed','pool'), ('room_sensor_installed','room')]:
                d[key] = component in d['components']
            if isinstance(self, OptionsFlowHandler):
                hub = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
                if hub is not None and d != self.config_entry.data:
                    hub.revoke_control()
                # One update triggers one reload. Options are not a parallel config.
                self.hass.config_entries.async_update_entry(self.config_entry, data=d)
                # Preserve the historical options mirror and unknown values.
                # Returning the same options avoids a second options-triggered reload.
                return self.async_create_entry(title='', data=dict(self.config_entry.options))
            return self.async_create_entry(title=d[CONF_NAME], data=d)
        return self.async_show_form(step_id='summary', data_schema=vol.Schema({}), description_placeholders={
            'components': ', '.join(self.component_label(c) for c in self._draft['components']), 'sensor_count': str(len(self._draft['sensors'])),
            'controls': ', '.join(self.component_label(CONTROLS[k][0]) for k in self._draft['controls']) or '—'})


class ConfigFlow(Wizard, config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 2

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        return await self.connection('user', user_input)


class OptionsFlowHandler(Wizard, config_entries.OptionsFlow):
    def __init__(self, config_entry):
        pass  # HA supplies the read-only config_entry property.

    async def async_step_init(self, user_input=None):
        return await self.connection('init', user_input)
