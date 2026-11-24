"""Drive the legacy Python GUI offscreen with a fake Pico client and no threads."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from client import gui  # noqa: E402
from client.protocol import ChannelState  # noqa: E402

CLOSED = ChannelState(0, 0, 0, 90, False)
OPENED = ChannelState(90, 90, 0, 90, False)


class FakeClient:
    """Stands in for ``ShutterClient``; never opens a socket."""

    def __init__(self, host, port):
        self.host, self.port = host, port
        self.state = ({0: 0, 1: 90}, {0: CLOSED, 1: OPENED})
        self.error = None
        self.failures = {}
        self.sent = []

    def snapshot(self):
        if self.error is not None:
            raise self.error
        return self.state

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


class Pool:
    """Runs client tasks on the calling thread, immediately or on demand."""

    def __init__(self):
        self.inline = True
        self.started = []
        self.pending = []

    def start(self, task):
        self.started.append(task.name)
        if self.inline:
            task.run()
        else:
            self.pending.append(task)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app, monkeypatch):
    errors = []
    monkeypatch.setattr(gui, "ShutterClient", FakeClient)
    monkeypatch.setattr(
        QMessageBox,
        "critical",
        lambda _parent, title, text: errors.append((title, text)),
    )
    window = gui.App()
    window.thread_pool = Pool()
    window.errors = errors
    yield window
    window.poll_timer.stop()
    window.close()
    window.deleteLater()


def badges(window):
    return [card.badge.text() for card in window.channel_cards.values()]


def test_client_task_reports_result_or_error(app):
    seen = []
    client = object()
    context = {"operation": "open"}
    succeeded = gui.ClientTask("job", client, lambda value: value, context)
    succeeded.signals.finished.connect(lambda *args: seen.append(args))
    succeeded.run()

    error = RuntimeError("boom")

    def fail(_client):
        raise error

    failed = gui.ClientTask("job", client, fail)
    failed.signals.finished.connect(lambda *args: seen.append(args))
    failed.run()
    assert seen == [("job", client, None, context), ("job", None, error, None)]


def test_channel_card_shows_state_error_and_enablement(app):
    card = gui.ChannelCard(2)
    assert card.title.text() == "CH2"
    card.set_state(90, "OPEN")
    assert card.angle.text() == "90 deg"
    assert (card.badge.text(), card.badge.objectName()) == ("OPEN", "badgeOpen")
    card.set_state(None, "MOVING")
    assert card.angle.text() == "- deg"
    assert (card.badge.text(), card.badge.objectName()) == ("MOVING", "badgeUnknown")
    card.set_error()
    assert (card.badge.text(), card.badge.objectName()) == ("ERROR", "badgeError")
    buttons = (card.close_button, card.open_button, card.toggle_button)
    card.set_actions_enabled(False)
    assert not any(button.isEnabled() for button in buttons)
    card.set_actions_enabled(True)
    assert all(button.isEnabled() for button in buttons)
    card.deleteLater()


def test_connect_shows_channels_and_disconnect_resets(window):
    window.host_input.setText("  ")
    window.port_input.setValue(4321)
    window.connect_to_server()
    client = window.client
    assert (client.host, client.port) == (gui.DEFAULT_HOST, 4321)
    address = f"{gui.DEFAULT_HOST}:4321"
    assert window.connection_label.text() == f"Connected to {address}"
    assert window.windowTitle() == f"Kohda Lab Shutter - {address}"
    assert sorted(window.channel_cards) == [0, 1]
    assert badges(window) == ["CLOSE", "OPEN"]
    assert window.channel_cards[1].angle.text() == "90 deg"
    summary = "2 channels | open 1 | close 1 | moving 0 | unknown 0"
    assert window.summary_label.text() == summary
    assert window.statusBar().currentMessage() == "Status updated"
    assert window.poll_timer.isActive()
    assert window.empty_label.isHidden()
    assert window.disconnect_button.isEnabled() and window.open_all_button.isEnabled()
    assert not window.connect_button.isEnabled() and not window.host_input.isEnabled()

    window.disconnect_from_server()
    assert window.client is None and window.channel_cards == {}
    assert window.current_status == {} and window.current_state is None
    assert not window.poll_timer.isActive()
    assert not window.empty_label.isHidden()
    assert window.summary_label.text() == "No channels"
    assert window.last_update_label.text() == "Last update: -"
    assert window.connection_label.text() == "Disconnected"
    assert window.windowTitle() == "Kohda Lab Shutter"
    assert window.connect_button.isEnabled()
    assert not window.disconnect_button.isEnabled()


def test_connect_failure_is_reported_and_duplicate_connects_are_ignored(window):
    window.thread_pool.inline = False
    window.connect_to_server()
    window.connect_to_server()
    assert window.thread_pool.started == ["connect"]
    assert window.connection_label.text() == "Connecting..."
    assert not window.connect_button.isEnabled()

    task = window.thread_pool.pending.pop()
    task.client.error = OSError("unreachable")
    task.run()
    assert window.client is None and not window.connect_inflight
    assert window.errors == [("Connect failed", "unreachable")]
    assert window.connection_label.text() == "Connection failed"
    assert window.statusBar().currentMessage() == "Connection failed"
    assert window.connect_button.isEnabled()


def test_refresh_updates_marks_errors_and_respects_inflight_work(window):
    pool = window.thread_pool
    window.refresh_status()
    assert pool.started == []

    window.connect_to_server()
    client = window.client
    client.state = ({0: 90, 1: 90}, None)  # firmware without STATE
    window.refresh_action.trigger()
    assert pool.started == ["connect", "refresh"]
    assert badges(window) == ["UNKNOWN", "UNKNOWN"]
    assert window.channel_cards[0].angle.text() == "90 deg"

    client.error = OSError("timeout")
    window.refresh_status()
    assert badges(window) == ["ERROR", "ERROR"]
    assert window.last_update_label.text() == "Last update: failed"
    assert window.connection_label.text() == "Communication error: timeout"
    assert window.statusBar().currentMessage() == "Communication error"

    client.error = None
    pool.inline = False
    window.refresh_status()
    window.refresh_status(force=True)  # one refresh at a time
    assert pool.started.count("refresh") == 3
    pool.pending.pop().run()
    assert not window.refresh_inflight and badges(window) == ["UNKNOWN", "UNKNOWN"]

    window.command_inflight = True
    window.refresh_status()  # polling yields to a running command
    assert pool.started.count("refresh") == 3
    window.refresh_status(force=True)  # the toolbar action does not
    assert pool.started.count("refresh") == 4


def test_commands_report_partial_failures_and_block_duplicates(window):
    pool = window.thread_pool
    window.run_command("open", [0])  # not connected
    assert pool.started == []

    window.connect_to_server()
    client = window.client
    window.run_command("open", [])  # nothing selected
    assert pool.started == ["connect"]
    window.channel_cards[1].toggle_button.click()
    window.channel_cards[0].open_button.click()
    window.channel_cards[0].close_button.click()
    window.open_all_button.click()
    window.close_all_button.click()
    assert client.sent == [
        ("toggle", 1),
        ("open", 0),
        ("close", 0),
        ("open", 0),
        ("open", 1),
        ("close", 0),
        ("close", 1),
    ]
    assert window.errors == []

    client.failures = {1: RuntimeError("LOCKED")}
    window.run_command("close", [0, 1])
    client.error = OSError("gone")
    window.run_command("close", [0, 1])
    client.failures = {}
    window.run_command("close", [0])
    assert window.errors == [
        ("Command failed", "CH1: LOCKED"),
        ("Command failed", "CH1: LOCKED\nStatus refresh failed: gone"),
        ("Command failed", "gone"),
    ]
    assert window.statusBar().currentMessage() == "Command failed"
    assert window.open_all_button.isEnabled()

    client.error = None
    pool.inline = False
    started = len(pool.started)
    window.run_command("open", [0])
    window.run_command("open", [1])  # one command batch at a time
    assert len(pool.started) == started + 1
    assert window.connection_label.text() == "Open..."
    assert not window.open_all_button.isEnabled()
    assert not window.channel_cards[0].open_button.isEnabled()
    pool.pending.pop().run()
    assert not window.command_inflight and window.open_all_button.isEnabled()
    assert client.sent[-1] == ("open", 0)


def test_channel_list_rebuilds_and_known_channels_fall_back_to_cards(window):
    window.connect_to_server()
    window.client.state = ({2: 0}, None)
    window.refresh_status()
    assert list(window.channel_cards) == [2]
    assert window.channel_cards[2].open_button.isEnabled()
    window.current_status = {}
    assert window._known_channels() == [2]

    window.client = None
    window._show_snapshot(({3: 10}, None))
    assert list(window.channel_cards) == [3]
    assert not window.channel_cards[3].open_button.isEnabled()
    assert window.statusBar().currentMessage() == "Status updated"

    window._task_finished("unknown", None, RuntimeError("ignored"), None)
    assert window.errors == [] and list(window.channel_cards) == [3]


def test_main_runs_the_fusion_window_until_the_event_loop_exits(monkeypatch):
    calls = []

    class FakeApplication:
        def __init__(self, argv):
            calls.append(("argv", argv))

        def setStyle(self, style):
            calls.append(("style", style))

        def exec(self):
            return 3

    class FakeWindow:
        def show(self):
            calls.append(("show",))

    monkeypatch.setattr(gui, "QApplication", FakeApplication)
    monkeypatch.setattr(gui, "App", FakeWindow)
    monkeypatch.setattr(gui.sys, "argv", ["kohdalab-shutter-gui"])
    with pytest.raises(SystemExit) as stopped:
        gui.main()
    assert stopped.value.code == 3
    assert calls == [
        ("argv", ["kohdalab-shutter-gui"]),
        ("style", "Fusion"),
        ("show",),
    ]
