"""The Paradigma integration."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .configuration import validate_config
from .const import DOMAIN, CONF_SLAVE_ID, PLATFORMS
from .hub import ParadigmaHub
from .sensor import ParadigmaDataCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Connect and read before any platform can use the shared client."""
    errors = validate_config(entry.data, check_interval=False)
    if errors:
        raise ConfigEntryError(f"Invalid Paradigma configuration: {errors}")
    if entry.entry_id in hass.data.get(DOMAIN, {}):
        raise ConfigEntryError("Previous Paradigma runtime still exists; unload it before retrying setup")
    hub = ParadigmaHub(hass, entry.data[CONF_NAME], entry.data[CONF_HOST],
                      entry.data[CONF_PORT], entry.data[CONF_SLAVE_ID])
    coordinator = ParadigmaDataCoordinator(hass, hub, entry.data, entry)
    hub.coordinator = coordinator
    try:
        if not await hass.async_add_executor_job(hub.connect):
            raise ConfigEntryNotReady("Cannot connect to the Paradigma Modbus endpoint")
        await coordinator.async_config_entry_first_refresh()
    except BaseException:
        await coordinator.async_shutdown()
        await hass.async_add_executor_job(hub.close)
        raise

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = hub
    try:
        device_registry = dr.async_get(hass)
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data[CONF_NAME],
            manufacturer="Paradigma",
            model="SystaSmartC II",
            sw_version="Modbus V1.1",
            configuration_url=f"http://{entry.data[CONF_HOST]}",
        )
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except BaseException:
        # Preserve the client if a partially loaded platform cannot be unloaded.
        try:
            unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
        except Exception:
            _LOGGER.exception("Could not clean up platforms for entry %s", entry.entry_id)
            unloaded = False
        if unloaded:
            await coordinator.async_shutdown()
            await hass.async_add_executor_job(hub.close)
            hass.data[DOMAIN].pop(entry.entry_id, None)
        else:
            _LOGGER.error("Platform setup failed and cleanup could not unload entry %s; shared client retained",
                          entry.entry_id)
        raise
    entry.async_on_unload(entry.add_update_listener(update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload all platforms before closing their shared connection."""
    hub = hass.data[DOMAIN][entry.entry_id]
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    await hub.coordinator.async_shutdown()
    await hass.async_add_executor_job(hub.close)
    hass.data[DOMAIN].pop(entry.entry_id)
    return True


async def update_listener(hass: HomeAssistant, entry: ConfigEntry):
    await hass.config_entries.async_reload(entry.entry_id)
