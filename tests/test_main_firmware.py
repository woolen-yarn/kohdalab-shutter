"""Run the complete, unmodified Pico ``server/main.py`` against stand-in modules.

The firmware is compiled under its own path, so coverage measures the real file.
MicroPython-only imports (``machine``, ``network``, ``ubinascii`` and the Pico's
flat sibling modules) are served by a private ``__import__``; ``sys.modules`` is
never modified. No GPIO, I2C, Wi-Fi or socket is touched.
"""

import binascii
import builtins
import json
from collections import deque
from pathlib import Path
from types import ModuleType

import pytest

from server.sessions import Sessions

MAIN = Path(__file__).parents[1] / "server" / "main.py"
CHANNELS = (
    {"label": "Input", "red": 1, "green": 2, "switch": 5},
    {"label": "Output", "red": 3, "green": 4, "switch": 6},
)
STATIC = ("192.0.2.10", "255.255.255.0", "192.0.2.1", "192.0.2.53")
ALL_INTERFACES = ".".join(["0"] * 4)
TOKEN = "a" * 32
FIXTURE_WLAN_KEY = "fixture-only"
STATE = "CH0=90/90/0/90/0"
STATUS = "CH0=90,CH1=0"


class StopFirmware(Exception):
    """Raised by the fake ``time.sleep`` to leave the firmware's endless loop."""


def module(name, **attributes):
    stand_in = ModuleType(name)
    for key, value in attributes.items():
        setattr(stand_in, key, value)
    return stand_in


class Pin:
    OUT = 1
    IN = 0
    PULL_UP = 2

    def __init__(self, number, _mode=None, _pull=None):
        self.number = number
        self.level = 1
        self.values = []

    def value(self, value=None):
        if value is None:
            return self.level
        self.level = value
        self.values.append(value)
        return None


class Servos:
    """Stands in for ``servo.ServoBoard`` and records every motion request."""

    def __init__(self, *args, **kwargs):
        self.args, self.kwargs = args, kwargs
        self.positions = [90, 0]
        self.faults = [False, False]
        self.actions = []
        self.ticks = 0
        self.ok = True

    def tick(self):
        self.ticks += 1

    @staticmethod
    def open_angle(_channel):
        return 90

    @staticmethod
    def close_angle(_channel):
        return 0

    def _move(self, action, channel):
        self.actions.append((action, channel))
        return self.ok

    def open(self, channel):
        return self._move("open", channel)

    def close(self, channel):
        return self._move("close", channel)

    def toggle(self, channel):
        return self._move("toggle", channel)

    @staticmethod
    def state_text():
        return STATE

    @staticmethod
    def status_text():
        return STATUS


class Label:
    """Stands in for ``sessions.DeviceLabel`` without touching the filesystem."""

    def __init__(self, default):
        self.value = default
        self.channel_labels = {}
        self.saved = []

    def save(self, value):
        self.saved.append(value)

    def save_config(self, patch):
        self.saved.append(patch)


class Discovery:
    def __init__(self, socket_module, device_id, tcp_port, port):
        self.args = (socket_module, device_id, tcp_port, port)
        self.available = True
        self.started = self.stopped = self.polls = 0

    def start(self):
        self.started += 1
        return self.available

    def stop(self):
        self.stopped += 1

    def poll(self):
        self.polls += 1


class Wifi:
    def __init__(self, clock):
        self.clock = clock
        self.connected = True
        self.fail = set()
        self.connects = []
        self.disconnects = []
        self.configurations = []

    def _check(self, name):
        if name in self.fail:
            raise OSError(name)

    def active(self, enabled):
        self._check("active")
        self.enabled = enabled

    def isconnected(self):
        return self.connected

    def connect(self, _ssid, _password):
        self.connects.append(self.clock.now)
        self._check("connect")

    def disconnect(self):
        self.disconnects.append(self.clock.now)
        self.connected = False
        self._check("disconnect")

    def ifconfig(self, config=None):
        if config is not None:
            self._check("ifconfig")
            self.configurations.append(config)
        return (STATIC[0],)


class Listener:
    def __init__(self, faults):
        self.faults = faults
        self.connections = deque()
        self.closed = False
        self.options = []

    def setsockopt(self, *option):
        self.options.append(option)

    def bind(self, address):
        if "bind" in self.faults:
            raise OSError("address in use")
        self.address = address

    def listen(self, backlog):
        self.backlog = backlog

    def settimeout(self, timeout):
        self.timeout = timeout

    def accept(self):
        if self.connections:
            return self.connections.popleft(), ("192.0.2.20", 4321)
        raise OSError("EAGAIN")

    def close(self):
        self.closed = True
        if "close" in self.faults:
            raise OSError("close")


class Connection:
    """A client socket replaying scripted ``recv`` results, then timing out."""

    def __init__(self, clock, *chunks, advance=0, fail=()):
        self.clock = clock
        self.chunks = deque(chunks)
        self.advance = advance
        self.fail = set(fail)
        self.writes = []
        self.timeouts = []
        self.closed = False

    def settimeout(self, timeout):
        self.timeouts.append(timeout)

    def recv(self, size):
        self.clock.now += self.advance
        if not self.chunks:
            raise OSError("timed out")
        chunk = self.chunks.popleft()
        if isinstance(chunk, Exception):
            raise chunk
        assert len(chunk) <= size
        return chunk

    def write(self, data):
        if "write" in self.fail:
            raise RuntimeError("write")
        self.writes.append(data)

    def close(self):
        self.closed = True
        if "close" in self.fail:
            raise RuntimeError("close")


class Firmware:
    """Boot ``server/main.py`` once; its endless loop stops at the first sleep."""

    def __init__(
        self,
        *,
        auto_start=False,
        pca_error=False,
        ujson=True,
        device_label="Bench",
        wifi_config=True,
        static_ip=False,
    ):
        self.now = 0
        self.wifi = Wifi(self)
        self.socket_faults = set()
        self.listeners = []
        settings = module(
            "settings",
            AUTO_START_SERVER=auto_start,
            BUTTON_DEBOUNCE_MS=50,
            CHANNELS=CHANNELS,
            COMMAND_READ_TIMEOUT_MS=1000,
            DISCOVERY_PORT=12346,
            I2C_BUS=0,
            I2C_FREQ=400_000,
            I2C_SCL_PIN=17,
            I2C_SDA_PIN=16,
            LONG_PRESS_MS=3000,
            PCA9685_ADDRESS=0x40,
            PCA9685_ANGLE_OFFSET=0,
            SERVO_MAX_ACTIVE=2,
            SERVO_RELEASE_DELAY_MS=500,
            SERVO_RELEASE_PWM=True,
            SERVO_STEP_DEGREES=3,
            SERVO_STEP_INTERVAL_MS=20,
            SERVER_PORT=12345,
            STATIC_IFCONFIG=STATIC,
            USE_STATIC_IP=static_ip,
        )
        if device_label is not None:
            settings.DEVICE_LABEL = device_label

        def pca9685(i2c, address, angle_offset):
            if pca_error:
                raise OSError("PCA9685 unavailable")
            return ("pwm", i2c, address, angle_offset)

        ujson_module = module("ujson", loads=json.loads, dumps=json.dumps)
        wifi_module = module("wifi_config", SSID="lab", PASSWORD=FIXTURE_WLAN_KEY)
        self.modules = {
            "machine": module(
                "machine",
                I2C=lambda bus, sda, scl, freq: ("i2c", bus, sda, scl, freq),
                Pin=Pin,
                unique_id=lambda: b"\x0a\xff",
            ),
            "ubinascii": module("ubinascii", hexlify=binascii.hexlify),
            "discovery": module("discovery", DiscoveryResponder=Discovery),
            "pca9685": module("pca9685", PCA9685=pca9685),
            "servo": module(
                "servo",
                DriverGuard=lambda _i2c, address, _pwm: ("guard", address),
                ServoBoard=Servos,
            ),
            "sessions": module("sessions", DeviceLabel=Label, Sessions=Sessions),
            "settings": settings,
            "network": module("network", WLAN=lambda _interface: self.wifi, STA_IF=0),
            "socket": module(
                "socket", socket=self._socket, SOL_SOCKET=1, SO_REUSEADDR=4
            ),
            "time": module(
                "time",
                ticks_ms=self.ticks_ms,
                ticks_diff=self.ticks_diff,
                sleep=self.sleep,
            ),
            "ujson": ujson_module if ujson else None,
            "wifi_config": wifi_module if wifi_config else None,
        }
        self.ns = {
            "__builtins__": {**vars(builtins), "__import__": self._import},
            "__name__": "main",
        }
        code = compile(MAIN.read_text(encoding="utf-8"), str(MAIN), "exec")
        with pytest.raises(StopFirmware):
            exec(code, self.ns)  # noqa: S102 - runs the repository's own firmware

    def _import(self, name, globals=None, locals=None, fromlist=(), level=0):
        if name in self.modules:
            stand_in = self.modules[name]
            if stand_in is None:
                raise ImportError(name)
            return stand_in
        return builtins.__import__(name, globals, locals, fromlist, level)

    def _socket(self, *_args):
        listener = Listener(self.socket_faults)
        self.listeners.append(listener)
        return listener

    def ticks_ms(self):
        return self.now

    @staticmethod
    def ticks_diff(new, old):
        return new - old

    def sleep(self, _seconds):
        self.now += 20
        raise StopFirmware

    def poll(self, moment):
        self.now = moment
        self.ns["poll_controller"]()

    @property
    def server(self):
        return self.ns["server"]

    @property
    def servos(self):
        return self.ns["servos"]

    @property
    def leds(self):
        return self.ns["leds"]

    @property
    def buttons(self):
        return self.ns["buttons"]

    @property
    def sessions(self):
        return self.ns["sessions"]


def levels(leds):
    pairs = zip(leds.red, leds.green, strict=True)
    return [(red.level, green.level) for red, green in pairs]


def test_optional_modules_fall_back_and_missing_wifi_config_keeps_server_off(capsys):
    firmware = Firmware(ujson=False, device_label=None, wifi_config=False)
    assert firmware.ns["json"] is json
    assert firmware.ns["DEVICE_LABEL"] == "Pico W Shutter"
    assert firmware.ns["SSID"] == "" and firmware.ns["PASSWORD"] == ""
    assert firmware.sessions.label == "Pico W Shutter"
    assert not firmware.server.start()
    assert not firmware.server.running and not firmware.server.reconnecting
    assert "Wi-Fi config missing" in capsys.readouterr().out


def test_boot_wires_settings_and_auto_start_listens(capsys):
    firmware = Firmware(auto_start=True, static_ip=True)
    assert firmware.ns["json"].__name__ == "ujson"
    assert firmware.servos.args[0] is CHANNELS
    assert firmware.servos.kwargs == {
        "step_degrees": 3,
        "step_interval_ms": 20,
        "release_delay_ms": 500,
        "max_active": 2,
        "release_pwm": True,
        "guard": ("guard", 0x40),
    }
    assert firmware.sessions.device_id == "0aff"
    assert firmware.sessions.label == "Bench"
    assert firmware.sessions.faults is firmware.servos.faults
    assert firmware.server.discovery.args[1:] == ("0aff", 12345, 12346)
    assert firmware.server.running and firmware.server.discovery.polls == 1
    listener = firmware.listeners[0]
    assert listener.address == (ALL_INTERFACES, 12345)
    assert listener.backlog == 8 and listener.timeout == 0
    assert firmware.wifi.configurations == [STATIC]
    assert firmware.leds.mode == firmware.leds.BLINK
    out = capsys.readouterr().out
    assert "Hold any switch for 3s" in out
    assert "Server listening on 192.0.2.10:12345" in out


def test_pca9685_failure_only_flashes_fault_leds(capsys):
    firmware = Firmware(pca_error=True)
    assert "servos" not in firmware.ns and "server" not in firmware.ns
    assert firmware.leds.servos is None
    assert levels(firmware.leds) == [(True, False), (True, False)]
    assert "PCA9685 initialization failed" in capsys.readouterr().out


def test_start_reports_wifi_errors_and_reconnects_in_the_background(capsys):
    firmware = Firmware()
    server, wifi = firmware.server, firmware.wifi
    wifi.fail.add("active")
    assert not server.start()
    assert "Wi-Fi start failed: active" in capsys.readouterr().out

    wifi.fail = {"connect"}
    wifi.connected = False
    firmware.now = 100
    assert server.start()
    assert server.reconnecting and not server.running
    assert firmware.leds.mode == firmware.leds.RECONNECTING
    assert server.start()  # already reconnecting
    assert wifi.connects == [100]
    assert "Wi-Fi reconnect attempt failed: connect" in capsys.readouterr().out


def test_tcp_start_failure_closes_the_socket_and_restores_leds(capsys):
    firmware = Firmware()
    firmware.socket_faults.update({"bind", "close"})
    firmware.leds.set_mode(firmware.leds.BLINK)
    assert not firmware.server.start()
    assert firmware.server.sock is None and firmware.listeners[0].closed
    assert firmware.server.discovery.stopped == 1
    assert firmware.leds.mode == firmware.leds.NORMAL
    assert "TCP server start failed: address in use" in capsys.readouterr().out


def test_wifi_watchdog_reconnects_and_recovers(capsys):
    firmware = Firmware(static_ip=True)
    server, wifi = firmware.server, firmware.wifi
    firmware.now = 0
    assert server.start()
    tcp = server.sock
    firmware.poll(1999)  # watchdog interval not reached
    firmware.poll(2000)  # connected and running: nothing to do
    assert server.running and server.sock is tcp

    wifi.connected = False
    firmware.poll(4000)
    assert server.reconnecting and not server.running and tcp.closed
    assert firmware.leds.mode == firmware.leds.RECONNECTING
    firmware.poll(6000)  # next connect attempt is not due yet
    assert wifi.connects == [4000]
    firmware.poll(14000)
    assert wifi.connects == [4000, 14000]

    wifi.connected = True
    wifi.fail.add("ifconfig")
    firmware.poll(16000)
    assert server.reconnecting and server.sock is None
    wifi.fail.clear()
    firmware.socket_faults.add("bind")
    firmware.poll(18000)
    assert server.reconnecting and server.sock is None
    assert firmware.leds.mode == firmware.leds.RECONNECTING

    firmware.socket_faults.clear()
    server.discovery.available = False
    firmware.poll(20000)
    assert server.running and not server.reconnecting
    assert firmware.leds.mode == firmware.leds.BLINK
    assert wifi.configurations == [STATIC, STATIC, STATIC]
    out = capsys.readouterr().out
    assert "Wi-Fi disconnected; reconnecting" in out
    assert "Wi-Fi IP setup failed: ifconfig" in out
    assert "TCP server start failed: address in use" in out
    assert "UDP discovery unavailable; TCP control remains available" in out


def test_stop_handles_idle_running_and_reconnecting_servers(capsys):
    firmware = Firmware()
    server, wifi = firmware.server, firmware.wifi
    assert not server.stop()
    assert server.start() and server.stop()
    assert not server.running and firmware.leds.mode == firmware.leds.NORMAL
    assert wifi.disconnects == []

    wifi.connected = False
    assert server.start() and server.reconnecting
    wifi.fail.add("disconnect")
    assert server.stop()
    assert not server.reconnecting and not server.running
    assert wifi.disconnects == [firmware.now]
    assert "Wi-Fi disconnect failed: disconnect" in capsys.readouterr().out


def test_poll_serves_at_most_eight_connections_per_pass():
    firmware = Firmware(auto_start=True)
    listener = firmware.listeners[0]
    connections = [Connection(firmware, b"STATUS\n") for _ in range(9)]
    listener.connections.extend(connections)
    firmware.poll(40)
    assert [conn.writes for conn in connections[:8]] == [[b"CH0=90,CH1=0\n"]] * 8
    assert all(conn.closed and conn.timeouts == [0.02] for conn in connections[:8])
    assert list(listener.connections) == [connections[8]]


def test_poll_replies_error_and_survives_failing_client_sockets(capsys):
    firmware = Firmware(auto_start=True)
    invalid = Connection(firmware, RuntimeError("recv"))
    broken = Connection(firmware, RuntimeError("recv"), fail={"write", "close"})
    firmware.listeners[0].connections.extend([invalid, broken])
    firmware.poll(40)
    assert invalid.writes == [b"ERROR\n"] and invalid.closed
    assert broken.writes == [] and broken.closed
    assert capsys.readouterr().out.count("Server error:") == 2


def test_invalid_utf8_is_rejected_by_firmware():
    firmware = Firmware(auto_start=True)
    connection = Connection(firmware, b"\xff\n")
    firmware.listeners[0].connections.append(connection)
    firmware.poll(40)
    assert connection.writes == [b"UNKNOWN\n"] and connection.closed
    assert firmware.servos.actions == []


def test_slow_client_keeps_local_controls_serviced():
    firmware = Firmware(auto_start=True)
    slow = Connection(firmware, OSError("EAGAIN"), b"STATE\n", advance=20)
    firmware.listeners[0].connections.append(slow)
    ticks = firmware.servos.ticks
    firmware.poll(40)
    assert slow.writes == [STATE.encode() + b"\n"]
    assert firmware.servos.ticks == ticks + 2


def test_local_stop_while_reading_drops_the_request_and_ends_the_pass():
    firmware = Firmware(auto_start=True)
    server = firmware.server
    stalled = Connection(firmware, advance=20)
    queued = Connection(firmware, b"OPEN 0\n")
    firmware.listeners[0].connections.extend([stalled, queued])
    server.poll(server.stop)
    assert not server.running
    assert stalled.writes == [] and stalled.closed
    assert queued.writes == [] and not queued.closed
    assert firmware.servos.actions == []


def test_readline_frames_one_line_and_rejects_partial_or_late_requests():
    firmware = Firmware()
    server = firmware.server
    split = Connection(firmware, b"OP", OSError("EAGAIN"), b"EN 0\nextra")
    assert server._readline(split) == "OPEN 0"
    assert split.timeouts == [0.02]
    assert server._readline(Connection(firmware, b"")) == ""
    assert server._readline(Connection(firmware, b"abcd"), max_length=4) == ""
    assert server._readline(Connection(firmware, b"OPEN 0\n", advance=1000)) == ""

    ticks = firmware.servos.ticks
    started = firmware.now
    assert server._readline(Connection(firmware, advance=20)) == ""
    assert firmware.now - started >= 1000
    assert firmware.servos.ticks > ticks
    assert firmware.servos.actions == []


def test_session_requests_reply_with_json_and_operate_owned_channels():
    firmware = Firmware()
    server, servos = firmware.server, firmware.servos
    conn = Connection(firmware)

    def session(body):
        server._handle("SESSION " + json.dumps(body), conn)
        return json.loads(conn.writes[-1])

    server._handle("SESSION {not json", conn)
    assert json.loads(conn.writes[-1]) == {"ok": False, "error": "invalid_request"}
    assert session([]) == {"ok": False, "error": "invalid_request"}
    rejected = session({"op": "claim", "token": "x", "channels": [0]})
    assert rejected == {"ok": False, "error": "invalid_request"}

    claim = session({"op": "claim", "token": TOKEN, "channels": [0]})
    assert claim["ok"] and claim["poll_supported"] is True
    assert firmware.leds.claimed == {0}
    poll = session({"op": "poll", "token": TOKEN})
    assert poll["ok"] and poll["state"] == STATE
    assert poll["info"]["channels"][0]["locked"]
    lost = session({"op": "poll", "token": "b" * 32})
    assert lost == {"ok": False, "error": "lease_lost"}

    for action in ("open", "close", "toggle"):
        body = {"op": "operate", "token": TOKEN, "action": action, "channels": [0]}
        assert session(body) == {"ok": True}
    assert servos.actions == [("open", 0), ("close", 0), ("toggle", 0)]
    servos.ok = False
    body = {"op": "operate", "token": TOKEN, "action": "open", "channels": [0]}
    assert session(body) == {
        "ok": False,
        "error": "invalid_request",
        "commanded": [],
        "failed": [0],
        "not_attempted": [],
    }

    assert session({"op": "release", "token": TOKEN}) == {"ok": True}
    assert session({"op": "claim", "token": TOKEN, "channels": [0, 1]})["ok"]
    servos.open = lambda channel: channel == 0
    assert session(dict(body, channels=[0, 1])) == {
        "ok": False,
        "error": "invalid_request",
        "commanded": [0],
        "failed": [1],
        "not_attempted": [],
    }


@pytest.mark.parametrize(
    ("command", "reply"),
    [
        ("", b"UNKNOWN\n"),
        ("state", STATE.encode() + b"\n"),
        ("STATE 1", b"UNKNOWN\n"),
        ("status", STATUS.encode() + b"\n"),
        ("MOVE 1", b"UNKNOWN\n"),
        ("OPEN", b"UNKNOWN\n"),
        ("OPEN one", b"ERR\n"),
        ("open 0", b"OK\n"),
        ("CLOSE 1", b"OK\n"),
        ("toggle 0", b"OK\n"),
    ],
)
def test_raw_commands_reply_on_one_line(command, reply):
    firmware = Firmware()
    conn = Connection(firmware)
    firmware.server._handle(command, conn)
    assert conn.writes == [reply]


def test_raw_motion_respects_leases_and_reports_servo_rejection():
    firmware = Firmware()
    server, servos = firmware.server, firmware.servos
    conn = Connection(firmware)
    assert firmware.sessions.claim(TOKEN, [0])["ok"]
    server._handle("OPEN 0", conn)
    servos.ok = False
    server._handle("OPEN 1", conn)
    assert conn.writes == [b"LOCKED\n", b"ERR\n"]
    assert servos.actions == [("open", 1)]


def test_buttons_toggle_locally_and_long_press_switches_the_server():
    firmware = Firmware()
    server, on_button = firmware.server, firmware.ns["on_button"]
    on_button(1, False)
    assert firmware.servos.actions == [("toggle", 1)]
    on_button(0, True)
    assert server.running
    on_button(0, True)
    assert not server.running
    firmware.wifi.connected = False
    on_button(0, True)
    assert server.reconnecting
    on_button(0, True)
    assert not server.reconnecting and not server.running


def test_led_mode_follows_long_press_then_server_state():
    firmware = Firmware()
    sync, leds, server = firmware.ns["sync_led_mode"], firmware.leds, firmware.server
    sync()
    assert leds.mode == leds.NORMAL
    server.reconnecting = True
    sync()
    assert leds.mode == leds.RECONNECTING
    server.running = True
    sync()
    assert leds.mode == leds.BLINK
    firmware.buttons._long_pressing[0] = True
    sync()
    assert leds.mode == leds.FAST


def test_button_debounce_short_and_long_presses(capsys):
    firmware = Firmware()
    events = []
    buttons = firmware.ns["ButtonDeck"](CHANNELS, lambda *event: events.append(event))
    switch = buttons.switches[0]

    def hold(level, *moments):
        switch.value(level)
        for moment in moments:
            firmware.now = moment
            buttons.poll()

    hold(0, 100, 120, 150)  # edge, bounce window, debounced press
    hold(1, 200, 250)
    assert events == [(0, False)]
    hold(0, 300, 350, 1000, 3350, 3400)
    assert buttons.long_pressing()
    hold(1, 3450, 3500)
    assert events == [(0, False), (0, True)]
    assert not buttons.long_pressing()
    assert capsys.readouterr().out.count("Long press CH0") == 1

    buttons._raw[1] = buttons._stable[1] = 0  # held down since boot
    for moment in (3600, 3650):
        firmware.now = moment
        buttons.poll()
    assert buttons._stable[1] == 1
    assert events == [(0, False), (0, True)]


def test_led_reflect_mirrors_positions_only_in_normal_mode():
    firmware = Firmware()
    servos = firmware.servos
    leds = firmware.ns["LedDeck"](CHANNELS, servos)
    leds.reflect()
    assert levels(leds) == [(0, 1), (1, 0)]

    servos.positions = [45, 90]
    servos.faults[1] = True
    leds.set_mode(leds.NORMAL)  # unchanged NORMAL mode still refreshes
    assert levels(leds) == [(1, 1), (1, 0)]

    servos.positions[0] = 0
    leds.set_mode(leds.BLINK)
    leds.set_mode(leds.BLINK)
    leds.reflect()
    assert levels(leds)[0] == (1, 1)
    leds.set_mode(leds.NORMAL)
    assert levels(leds)[0] == (1, 0)

    detached = firmware.ns["LedDeck"](CHANNELS, None)
    detached.reflect()
    assert all(pin.values == [] for pin in detached.red + detached.green)

    leds.set_claimed([0])
    stamp = leds._last_ms
    firmware.now += 500
    leds.set_claimed((0,))
    assert leds._last_ms == stamp and leds.claimed == {0}


def test_led_tick_patterns_for_each_mode():
    firmware = Firmware()
    servos = firmware.servos
    firmware.now = 0
    leds = firmware.ns["LedDeck"](CHANNELS, servos)

    def tick(moment):
        firmware.now = moment
        leds.tick()
        return levels(leds)

    tick(10)  # no blink step due
    tick(50)  # NORMAL mode leaves steady LEDs to reflect()
    assert all(pin.values == [] for pin in leds.red + leds.green)

    servos.faults[1] = True
    assert tick(100)[1] == (False, True)  # fault flash has priority

    leds.set_mode(leds.RECONNECTING)
    assert tick(150)[0] == (0, True)
    assert tick(1150)[0] == (0, False)

    servos.faults[1] = False
    firmware.now = 1200
    leds.set_mode(leds.BLINK)
    leds.set_claimed([0])  # claimed channel double-flashes, others blink
    assert tick(1200) == [(0, True), (True, 0)]
    assert tick(1350) == [(0, False), (True, 0)]
    assert tick(1450) == [(0, True), (False, 0)]

    leds.set_mode(leds.FAST)
    assert tick(1480) == [(0, True), (False, 0)]  # fast step not due yet
    assert tick(1510) == [(True, True), (True, True)]
