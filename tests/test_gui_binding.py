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


def busy_then(result, failures=2):
    replies = [binding.GuiShutterError("busy", "busy")] * failures + [result]
    return Mock(side_effect=replies)


def test_close_all_retries_explicit_busy_with_the_same_request_id(monkeypatch):
    shutter = binding.GuiShutter()
    shutter._lease = "lease"
    request = busy_then({"id": "job"})
    sleep = Mock()
    monkeypatch.setattr(shutter, "_request", request)
    monkeypatch.setattr(binding.time, "sleep", sleep)

    assert shutter.close_all() == {"id": "job"}
    ids = {call.kwargs["request_id"] for call in request.call_args_list}
    assert request.call_count == 3 and len(ids) == 1
    assert [call.args for call in sleep.call_args_list] == [(0.05,), (0.1,)]


def test_busy_retry_is_bounded_and_other_errors_are_not_retried(monkeypatch):
    shutter = binding.GuiShutter()
    shutter._lease = "lease"
    now = [0.0]

    def sleep(seconds):
        now[0] += seconds

    monkeypatch.setattr(binding.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(binding.time, "sleep", sleep)
    busy = Mock(side_effect=binding.GuiShutterError("busy", "busy"))
    monkeypatch.setattr(shutter, "_request", busy)
    with pytest.raises(binding.GuiShutterError) as error:
        shutter.toggle(0)
    assert error.value.code == "busy"
    assert now[0] <= binding.GuiShutter._BUSY_RETRY_SECONDS
    assert len({call.kwargs["request_id"] for call in busy.call_args_list}) == 1

    for code in ("capacity", "timeout", "transport", "ownership_lost"):
        failed = Mock(side_effect=binding.GuiShutterError(code, code))
        monkeypatch.setattr(shutter, "_request", failed)
        with pytest.raises(binding.GuiShutterError):
            shutter.close(0)
        failed.assert_called_once()


def test_busy_connect_is_returned_at_once(monkeypatch):
    shutter = binding.GuiShutter()
    shutter._lease = "lease"
    request = busy_then({"id": "job"}, failures=1)
    monkeypatch.setattr(shutter, "_request", request)
    with pytest.raises(binding.GuiShutterError):
        shutter.connect(host="127.0.0.1", channels=[0])
    request.assert_called_once()
