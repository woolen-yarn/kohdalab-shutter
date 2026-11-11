"""GUI API client state waiting, without connecting to a GUI or device."""

from unittest.mock import Mock

import pytest

from bindings.python import kohdalab_shutter as binding


@pytest.mark.parametrize("observed", ["Open", "Close", "Moving", "Unknown"])
@pytest.mark.parametrize("timeout", [None, 0, 10])
def test_wait_for_state_fault_fails_before_matching_or_waiting(
    monkeypatch, observed, timeout
):
    shutter = binding.GuiShutter()
    status = Mock(
        return_value={
            "connected": True,
            "channels": {"0": {"state": observed, "fault": True}},
        }
    )
    sleep = Mock(side_effect=AssertionError("fault must not wait"))
    monkeypatch.setattr(shutter, "status", status)
    monkeypatch.setattr(binding.time, "sleep", sleep)

    with pytest.raises(binding.GuiShutterError) as error:
        shutter.wait_for_state(0, "Open", timeout=timeout)
    assert error.value.code == "fault"
    status.assert_called_once_with()
    sleep.assert_not_called()


@pytest.mark.parametrize("fault_field", [{}, {"fault": False}])
def test_wait_for_state_polls_legacy_and_healthy_channels(monkeypatch, fault_field):
    shutter = binding.GuiShutter()
    finished = {
        "connected": True,
        "channels": {
            "0": {"state": "Open", **fault_field},
            "1": {"state": "Close", "fault": True},
        },
    }
    status = Mock(
        side_effect=[
            {"connected": True, "channels": {"0": {"state": "Moving", **fault_field}}},
            finished,
        ]
    )
    sleep = Mock()
    monkeypatch.setattr(shutter, "status", status)
    monkeypatch.setattr(binding.time, "sleep", sleep)

    assert shutter.wait_for_state(0, "Open") is finished
    assert status.call_count == 2
    sleep.assert_called_once_with(0.05)


@pytest.mark.parametrize(
    "snapshot, code",
    [
        ({"connected": True, "channels": {"0": {"state": "Close"}}}, "timeout"),
        ({"connected": True, "channels": {"0": {"state": "Unknown"}}}, "unknown_state"),
        ({"connected": False}, "disconnected"),
    ],
)
def test_wait_for_state_legacy_errors(monkeypatch, snapshot, code):
    shutter = binding.GuiShutter()
    monkeypatch.setattr(shutter, "status", Mock(return_value=snapshot))
    with pytest.raises(binding.GuiShutterError) as error:
        shutter.wait_for_state(0, "Open", timeout=0)
    assert error.value.code == code
