"""Configuration validation without network access or registry migrations."""
import logging

from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL

from .const import CONF_SLAVE_ID, DEFAULT_SCAN_INTERVAL, CONF_ALLOW_CONTROL

_LOGGER = logging.getLogger(__name__)
MIN_SCAN_INTERVAL = 10
MAX_SCAN_INTERVAL = 3600


def validate_config(data, *, check_interval=True, check_permission=True):
    """Return translated field errors; retain stored values and unknown options."""
    errors = {}
    host = data.get(CONF_HOST)
    if not isinstance(host, str) or not host or any(char.isspace() for char in host):
        errors[CONF_HOST] = "invalid_host"
    for key, minimum, maximum, error in (
        (CONF_PORT, 1, 65535, "invalid_port"),
        (CONF_SLAVE_ID, 1, 255, "invalid_slave_id"),
    ):
        value = data.get(key)
        if type(value) is not int or not minimum <= value <= maximum:
            errors[key] = error
    if check_permission and CONF_ALLOW_CONTROL in data and type(data[CONF_ALLOW_CONTROL]) is not bool:
        errors[CONF_ALLOW_CONTROL] = "invalid_allow_control"
    if check_interval:
        value = data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        if type(value) is not int or not MIN_SCAN_INTERVAL <= value <= MAX_SCAN_INTERVAL:
            errors[CONF_SCAN_INTERVAL] = "invalid_scan_interval"
    return errors


def scan_interval(data):
    """Keep old entries loadable even if their previously ignored interval is invalid."""
    value = data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    if type(value) is not int or not MIN_SCAN_INTERVAL <= value <= MAX_SCAN_INTERVAL:
        _LOGGER.warning("Invalid stored scan_interval %r; using %s seconds until options are corrected",
                        value, DEFAULT_SCAN_INTERVAL)
        return DEFAULT_SCAN_INTERVAL
    return value


def control_allowed(data):
    """Only the literal boolean True authorizes control; legacy entries fail closed."""
    return data.get(CONF_ALLOW_CONTROL) is True
