"""Per-channel state for the legacy Python GUI, without a Pico or a display."""

import pytest

from client import gui
from client.protocol import ChannelState, ProtocolError, parse_state, state_name
from client.transport import CommandError, ShutterClient, ShutterConnectionError


def test_parses_state_with_custom_and_reversed_calibration():
    state = parse_state("CH0=90/90/90/0/0, ch1=0/0/90/0/0,CH2=40/70/10/70/1")
    assert state[0] == ChannelState(90, 90, 90, 0, False)
    assert state_name(state[0]) == "CLOSE"  # closed at 90 degrees
    assert state_name(state[1]) == "OPEN"  # open at 0 degrees
    assert state_name(state[2]) == "MOVING"


@pytest.mark.parametrize(
    ("entry", "name"),
    [
        (None, "UNKNOWN"),  # firmware without STATE
        (ChannelState(10, 10, 10, 70, False), "CLOSE"),
        (ChannelState(70, 70, 10, 70, False), "OPEN"),
        (ChannelState(70, 70, 10, 70, True), "MOVING"),
        (ChannelState(40, 70, 10, 70, False), "MOVING"),
        (ChannelState(40, 40, 10, 70, False), "UNKNOWN"),
    ],
)
def test_state_name_uses_each_channels_endpoints(entry, name):
    assert state_name(entry) == name


@pytest.mark.parametrize(
    ("response", "message"),
    [
        ("", "Empty"),
        ("CH0", "Malformed"),
        ("X0=0/0/0/90/0", "Malformed"),
        ("CH0=0/0/0/90", "Malformed"),
        ("CHx=0/0/0/90/0", "Invalid"),
        ("CH0=0/0/a/90/0", "Invalid"),
        ("CH-1=0/0/0/90/0", "range"),
        ("CH0=0/0/0/181/0", "range"),
        ("CH0=0/0/0/90/2", "range"),
        ("CH0=0/0/0/90/0,CH0=0/0/0/90/0", "Duplicate"),
    ],
)
def test_rejects_malformed_state(response, message):
    with pytest.raises(ProtocolError, match=message):
        parse_state(response)


class Responder:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.sent = []

    def __call__(self, command, retry=True):
        self.sent.append(command)
        return self.responses.pop(0)


def test_snapshot_uses_state_and_falls_back_to_unknown_on_old_firmware(monkeypatch):
    client = ShutterClient("pico.local")
    send = Responder("CH0=90/90/90/0/0,CH1=0/0/90/0/0")
    monkeypatch.setattr(client, "send", send)
    positions, state = client.snapshot()
    assert positions == {0: 90, 1: 0}
    assert state_name(state[0]) == "CLOSE" and state_name(state[1]) == "OPEN"
    assert send.sent == ["STATE"]

    send = Responder("UNKNOWN", "CH0=0,CH1=90")
    monkeypatch.setattr(client, "send", send)
    assert client.snapshot() == ({0: 0, 1: 90}, None)
    assert send.sent == ["STATE", "STATUS"]


class FakeClient:
    def __init__(self, failures=(), snapshot_error=None):
        self.failures = dict(failures)
        self.snapshot_error = snapshot_error
        self.sent = []

    def _send(self, operation, channel):
        self.sent.append((operation, channel))
        if channel in self.failures:
            raise self.failures[channel]
        return "OK"

    def open(self, channel):
        return self._send("open", channel)

    def close(self, channel):
        return self._send("close", channel)

    def toggle(self, channel):
        return self._send("toggle", channel)

    def snapshot(self):
        if self.snapshot_error:
            raise self.snapshot_error
        return {0: 0}, None


def test_close_all_attempts_every_channel_and_reports_failures_together():
    client = FakeClient({1: CommandError("Pico rejected CLOSE 1: LOCKED")})
    snapshot, failures = gui.run_operation(client, "close", [0, 1, 2, 3])
    assert client.sent == [("close", ch) for ch in range(4)]
    assert failures == ["CH1: Pico rejected CLOSE 1: LOCKED"]
    assert snapshot == ({0: 0}, None)  # state is refreshed after a partial failure


def test_lost_connection_stops_the_batch_and_names_unsent_channels():
    client = FakeClient(
        {1: ShutterConnectionError("down")}, snapshot_error=ShutterConnectionError("x")
    )
    snapshot, failures = gui.run_operation(client, "close", [0, 1, 2, 3])
    assert client.sent == [("close", 0), ("close", 1)]
    assert failures == [
        "CH1: down",
        "Not sent (connection lost): CH2, CH3",
        "Status refresh failed: x",
    ]
    assert snapshot is None

    client = FakeClient({3: ShutterConnectionError("down")})
    assert gui.send_operation(client, "open", [2, 3]) == ["CH3: down"]


def test_successful_batch_propagates_a_refresh_error():
    client = FakeClient(snapshot_error=ShutterConnectionError("x"))
    with pytest.raises(ShutterConnectionError):
        gui.run_operation(client, "toggle", [0])
    assert client.sent == [("toggle", 0)]
