"""Paradigma Modbus Hub."""
import logging
import threading
from time import monotonic
from pymodbus.exceptions import ModbusException
from pymodbus.client import ModbusTcpClient

_LOGGER = logging.getLogger(__name__)

class ParadigmaHub:
    def __init__(self, hass, name, host, port, slave_id):
        self._hass = hass
        self._host = host
        self._port = port
        self._slave_id = int(slave_id)
        # Preserve library timeout/retry defaults for the shared write platforms.
        self._client = ModbusTcpClient(host=host, port=port)
        self._lock = threading.Lock()
        self._closed = False
        self._retry_after = 0.0
        self._transport_failed = False
        self._failed_reads = set()
        self.name = name
        self.coordinator = None

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

    def write_register(self, address, value):
        """Write Single Register - Forced as Multiple (FC 0x10)."""
        with self._lock:
            try:
                try:
                    res = self._client.write_registers(address=address, values=[value], device_id=self._slave_id)
                except TypeError:
                    try:
                        res = self._client.write_registers(address, [value], slave=self._slave_id)
                    except TypeError:
                        res = self._client.write_registers(address, [value], unit=self._slave_id)
                
                return not res.isError()
            except Exception as e:
                _LOGGER.error(f"Fehler beim Schreiben (Register {address}): {e}")
                return False

    def write_coil(self, address, value):
        """Write Single Coil."""
        with self._lock:
            try:
                try:
                    self._client.write_coil(address, value, device_id=self._slave_id)
                except TypeError:
                    try:
                        self._client.write_coil(address, value, slave=self._slave_id)
                    except TypeError:
                        self._client.write_coil(address, value, unit=self._slave_id)
                return True
            except Exception:
                return False
