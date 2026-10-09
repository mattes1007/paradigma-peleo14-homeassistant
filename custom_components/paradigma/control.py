"""Conservative write policy for TH-3000 V1.1 (SystaComfort II >= 2.16).

Addresses are zero-based. 44/45 are read-only; coil command sequencing is
not yet approved. No policy is inferred from the user's global permission.
"""
from decimal import Decimal, InvalidOperation
from types import MappingProxyType
from time import monotonic

# Raw deci-degrees. Existing UI limits are conservative application limits,
# not manufacturer guarantees. No off/release sentinel is accepted here.
REGISTER_LIMITS = MappingProxyType({2: (200, 800, 10), 3: (200, 800, 10),
                                    8: (300, 700, 1)})
CONTROL_REGISTERS = frozenset(REGISTER_LIMITS)
CONTROL_COILS = frozenset()  # Pair/override semantics still require approval.


def encode_temperature(value, minimum, maximum, step):
    """Validate without truncation, bool/string coercion or floating-point drift."""
    if type(value) not in (int, float):
        raise ValueError("Temperature must be a finite number")
    try:
        temperature = Decimal(str(value))
        raw = temperature * 10
        if (not temperature.is_finite() or not minimum <= temperature <= maximum
                or (temperature - Decimal(str(minimum))) % Decimal(str(step)) != 0
                or raw != raw.to_integral_value()):
            raise ValueError("Temperature outside permitted range or step")
    except InvalidOperation as err:
        raise ValueError("Invalid temperature") from err
    return int(raw)


def decode_temperature(values):
    """A missing/invalid response is unknown, never an invented setpoint."""
    if not isinstance(values, (list, tuple)) or len(values) != 1:
        return None
    raw = values[0]
    if type(raw) is not int or not 0 <= raw <= 65535 or raw in (0x7FFF, 0x8000, 0xFFFF):
        return None
    return (raw - 65536 if raw > 32767 else raw) / 10


OVERRIDE_LIFETIME = 300  # TH-3000: no claim survives the five-minute window.


class SetpointConfirmation:
    """Temporary evidence of a register match, never a heating/override state.

    Polling cannot extend the lifetime. There is no restored confirmation and
    no timer that writes or renews a command. HA publishes attributes on its
    next ordinary state update; property evaluation always checks the deadline.
    """
    def __init__(self):
        self._requested = None
        self._deadline = None
        self._acknowledged = False
        self._status = "not_requested"

    def begin(self, value):
        self._requested = value
        self._deadline = monotonic() + OVERRIDE_LIFETIME
        self._acknowledged = False
        self._status = "pending"

    def acknowledge(self):
        self._acknowledged = True
        self._status = "acknowledged"

    def fail(self):
        self._acknowledged = False
        self._status = "write_failed"

    def observe(self, value):
        if not self._acknowledged:
            return
        if monotonic() >= self._deadline:
            self._status = "expired"
        elif value is None:
            self._status = "readback_failed"
        elif value == self._requested:
            self._status = "readback_matches"
        else:
            self._status = "readback_mismatch"

    @property
    def attributes(self):
        status = self._status
        if self._acknowledged and monotonic() >= self._deadline:
            status = "expired"
        return {"setpoint_confirmation": status,
                "last_requested_setpoint": self._requested}
