"""Paradigma Modbus Hub."""
import logging
import threading
from time import monotonic
from pymodbus.exceptions import ModbusException
from pymodbus.client import ModbusTcpClient

from .control import REGISTER_LIMITS, CONTROL_COILS

_LOGGER = logging.getLogger(__name__)

class ParadigmaHub:
    def __init__(self, hass, name, host, port, slave_id, *, allow_control=False, permission_check=None):
        self._hass = hass
        self._host = host
        self._port = port
        self._slave_id = int(slave_id)
        # Preserve library timeout/retry defaults for the shared write platforms.
        self._client = ModbusTcpClient(host=host, port=port)
        self._lock = threading.Lock()
        self._closed = False
        self._allow_control = allow_control is True
        self._permission_check = permission_check
        self._denied_writes = set()
        self._retry_after = 0.0
        self._transport_failed = False
        self._failed_reads = set()
        self.name = name
        self.coordinator = None
        self.platforms = []

    def _transport_error(self, error):
        """Called with the client lock held; rate-limit outages across platforms."""
        log = _LOGGER.debug if self._transport_failed else _LOGGER.warning
        log("Modbus transport %s:%s (device %s): %s; retry after 5 seconds",
            self._host, self._port, self._slave_id, error)
        self._transport_failed = True
        self._retry_after = monotonic() + 5
        self._client.close()

    def _connect_locked(self):
        if self._closed or monotonic() < self._retry_after:
            return False
        try:
            if not self._client.connected and not self._client.connect():
                self._transport_error("connection failed")
                return False
            return True
        except (OSError, ModbusException) as err:
            self._transport_error(err)
            return False

    def connect(self):
        with self._lock:
            return self._connect_locked()

    def close(self):
        with self._lock:
            self._closed = True
            self._client.close()

    def _read_error(self, key, error):
        log = _LOGGER.debug if key in self._failed_reads else _LOGGER.warning
        log("Modbus %s address %s count %s (%s:%s, device %s): %s",
            *key, self._host, self._port, self._slave_id, error)
        self._failed_reads.add(key)

    def _read_modbus(self, func_name, address, count):
        """Read with the PyModbus 3.13.1 keyword API and shared client lock."""
        key = (func_name, address, count)
        with self._lock:
            if not self._connect_locked():
                return None
            try:
                res = getattr(self._client, func_name)(
                    address=address, count=count, device_id=self._slave_id
                )
                if res is None:
                    self._transport_error("no response")
                    return None
                if isinstance(res, ModbusException):
                    raise res
                if not callable(getattr(res, "isError", None)):
                    self._read_error(key, "invalid response object")
                    return None
                if res.isError():
                    # Exception responses indicate a reachable device, not a lost socket.
                    self._read_error(key, res)
                    return None
                values = getattr(res, "bits" if func_name == "read_coils" else "registers", None)
                if not isinstance(values, (list, tuple)) or len(values) < count:
                    self._read_error(key, "incomplete response")
                    return None
                if func_name == "read_coils" and any(
                    type(value) not in (bool, int) or value not in (0, 1) for value in values
                ):
                    self._read_error(key, "invalid coil response")
                    return None
                if func_name != "read_coils" and (
                    len(values) != count
                    or any(type(value) is not int or not 0 <= value <= 65535 for value in values)
                ):
                    self._read_error(key, "invalid register response")
                    return None
                if self._transport_failed:
                    _LOGGER.info("Modbus communication restored (%s:%s, device %s)",
                                 self._host, self._port, self._slave_id)
                    self._transport_failed = False
                if key in self._failed_reads:
                    _LOGGER.info("Modbus read restored: %s address %s count %s", *key)
                    self._failed_reads.remove(key)
                return res
            except (OSError, ModbusException) as err:
                self._read_error(key, err)
                self._transport_error(err)
                return None

    def read_input_registers(self, address, count):
        res = self._read_modbus("read_input_registers", address, count)
        return res.registers if res is not None else None

    def read_holding_registers(self, address, count):
        res = self._read_modbus("read_holding_registers", address, count)
        return res.registers if res is not None else None

    def read_coils(self, address, count):
        res = self._read_modbus("read_coils", address, count)
        return res.bits if res is not None else None

    @property
    def control_enabled(self):
        """Check the current entry as well as the permission of this runtime."""
        if self._closed or self._allow_control is not True:
            return False
        try:
            return self._permission_check is None or self._permission_check() is True
        except Exception:
            return False

    def revoke_control(self):
        """Revoke before reload; an old runtime can never re-enable itself."""
        # Revoke immediately without blocking the HA event loop on network I/O.
        # An already transmitted request cannot be recalled.
        self._allow_control = False

    def can_write_register(self, address):
        return (self.control_enabled and self._slave_id == 1
                and type(address) is int and address in REGISTER_LIMITS)

    def can_write_coil(self, address):
        return self.control_enabled and type(address) is int and address in CONTROL_COILS

    def _write_denied(self, kind, address):
        key = (kind, repr(address))
        log = _LOGGER.debug if key in self._denied_writes else _LOGGER.warning
        log("Modbus write blocked: %s address %s; read-only or unapproved function",
            kind, address)
        self._denied_writes.add(key)
        return False

    def write_register(self, address, value):
        """Acknowledge one permitted FC 0x10 write; no claim of plant adoption.

        Readback belongs to the entity. No write is performed for an absent,
        invalid or revoked permission, a read-only address or invalid raw value.
        """
        with self._lock:
            if not self.can_write_register(address):
                return self._write_denied("holding", address)
            minimum, maximum, step = REGISTER_LIMITS[address]
            if type(value) is not int or not minimum <= value <= maximum or (value - minimum) % step:
                _LOGGER.warning("Invalid Modbus setpoint: holding address %s value %r", address, value)
                return False
            # TH-3000: a DHW target is effective only with the release override.
            if address == 8:
                released = self._read_precondition_locked("read_coils", 4, 2)
                if released != [True, False]:
                    _LOGGER.warning("DHW setpoint blocked: release override not confirmed")
                    return False
            if address in (2, 3):
                limit = self._read_precondition_locked("read_holding_registers", 9 if address == 2 else 10, 1)
                if (limit is None or limit[0] in (0x7FFF, 0x8000, 0xFFFF)
                        or not 0 < limit[0] <= 32766 or value > limit[0]):
                    _LOGGER.warning("Heating circuit setpoint blocked: configured flow limit not satisfied")
                    return False
            if not self._connect_locked():
                return False
            if not self.can_write_register(address):
                return self._write_denied("holding", address)
            try:
                response = self._client.write_registers(
                    address=address, values=[value], device_id=self._slave_id
                )
                if response is None:
                    self._transport_error("no write response")
                    return False
                if isinstance(response, ModbusException):
                    raise response
                if not callable(getattr(response, "isError", None)) or response.isError() is not False:
                    _LOGGER.warning("Modbus write rejected: holding address %s: %s", address, response)
                    return False
                if (getattr(response, "function_code", None) != 0x10
                        or type(getattr(response, "address", None)) is not int
                        or getattr(response, "address", None) != address
                        or type(getattr(response, "count", None)) is not int
                        or getattr(response, "count", None) != 1):
                    _LOGGER.warning("Invalid Modbus write acknowledgement: holding address %s", address)
                    return False
                return True
            except (OSError, ModbusException) as err:
                _LOGGER.warning("Modbus write failed: holding address %s: %s", address, err)
                self._transport_error(err)
                return False
            except Exception:
                _LOGGER.exception("Unexpected Modbus write error: holding address %s", address)
                return False

    def _read_precondition_locked(self, function, address, count):
        """Read a documented write precondition with the client lock held."""
        if not self._connect_locked():
            return None
        try:
            response = getattr(self._client, function)(address=address, count=count, device_id=self._slave_id)
            if response is None:
                self._transport_error("no write precondition response")
                return None
            if isinstance(response, ModbusException):
                raise response
            if not callable(getattr(response, "isError", None)) or response.isError() is not False:
                return None
            coils = function == "read_coils"
            values = getattr(response, "bits" if coils else "registers", None)
            if not isinstance(values, (list, tuple)) or len(values) < count:
                return None
            if coils:
                if any(type(value) not in (bool, int) or value not in (0, 1) for value in values):
                    return None
                return [bool(value) for value in values[:count]]
            if len(values) != count or any(type(value) is not int or not 0 <= value <= 65535 for value in values):
                return None
            return values
        except (OSError, ModbusException) as err:
            self._transport_error(err)
            return None
        except Exception:
            _LOGGER.exception("Invalid Modbus write precondition response at address %s", address)
            return None

    def write_coil(self, address, value):
        """Fail closed: none of the legacy coil command sequences is approved."""
        with self._lock:
            return self._write_denied("coil", address)
