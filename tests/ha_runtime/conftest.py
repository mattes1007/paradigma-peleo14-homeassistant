"""Actual HA fixtures; only Modbus transport is simulated. No network access."""
from types import SimpleNamespace
from unittest.mock import patch

import pytest

pytest_plugins = ["pytest_homeassistant_custom_component"]


class SimulatedModbusClient:
    def __init__(self, *, host, port):
        self.host = host
        self.port = port
        self.connected = False
        self.closed = 0
        self.calls = []
        self.writes = []
        self.holding = {2: 543, 3: 400, 8: 500, 9: 800, 10: 800, 44: 600, 45: 720}
        self.missing = set()

    def connect(self):
        self.connected = True
        return True

    def close(self):
        self.connected = False
        self.closed += 1

    def read_input_registers(self, *, address, count, device_id):
        self.calls.append(("input", address, count, device_id))
        return SimpleNamespace(registers=[230] * count, isError=lambda: False)

    def read_holding_registers(self, *, address, count, device_id):
        self.calls.append(("holding", address, count, device_id))
        if address in self.missing:
            return SimpleNamespace(isError=lambda: True)
        values = [0, 123] if count == 2 else [self.holding.get(address, 0)]
        return SimpleNamespace(registers=values, isError=lambda: False)

    def read_coils(self, *, address, count, device_id):
        self.calls.append(("coil", address, count, device_id))
        return SimpleNamespace(bits=[True, False], isError=lambda: False)

    def write_registers(self, *, address, values, device_id):
        self.writes.append((address, values, device_id))
        self.holding[address] = values[0]
        return SimpleNamespace(function_code=0x10, address=address, count=1, isError=lambda: False)

    def write_coil(self, *args, **kwargs):
        raise AssertionError("Coil writes must never reach the client")


@pytest.fixture(autouse=True)
def simulated_modbus(enable_custom_integrations):
    clients = []
    def factory(**kwargs):
        client = SimulatedModbusClient(**kwargs)
        clients.append(client)
        return client
    with patch("custom_components.paradigma.hub.ModbusTcpClient", side_effect=factory):
        yield clients
    assert all(client.host == "controller.invalid" for client in clients)
