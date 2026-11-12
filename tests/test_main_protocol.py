"""Exercise Pico request handling without importing MicroPython hardware modules."""

import ast
import json

import pytest
from collections import deque
from types import SimpleNamespace
from pathlib import Path

from server.discovery import DiscoveryResponder
from server.servo import ServoBoard
from server.sessions import Sessions


class Clock:
    def __init__(self):
        self.now = 0

    def ticks_ms(self):
        return self.now

    @staticmethod
    def ticks_diff(now, then):
        return now - then


class FakeTime:
    def __init__(self, clock):
        self.clock = clock

    def ticks_ms(self):
        return self.clock.ticks_ms()

    def ticks_diff(self, now, then):
        return self.clock.ticks_diff(now, then)


class FakePin:
    OUT = 1
    IN = 0
    PULL_UP = 2
    pins = {}

    def __init__(self, number, _mode=None, _pull=None):
        self.number = number
        self.level = 1
        self.values = []
        self.pins[number] = self

    def value(self, value=None):
        if value is None:
            return self.level
        self.level = value
        self.values.append(value)


class FakeServos:
    def __init__(self):
        self.positions = [0, 90]
        self.faults = [False, False]
        self.actions = []
        self.ticks = 0

    def tick(self):
        self.ticks += 1

    @staticmethod
    def close_angle(_channel):
        return 0

    @staticmethod
    def open_angle(_channel):
        return 90

    def open(self, channel):
        self.actions.append(("open", channel))
        return True

    def close(self, channel):
        self.actions.append(("close", channel))
        return True

    def toggle(self, channel):
        self.actions.append(("toggle", channel))
        return True

    @staticmethod
    def state_text():
        return "STATE"

    @staticmethod
    def status_text():
        return "STATUS"


class Connection:
    def __init__(self):
        self.writes = []

    def write(self, value):
        self.writes.append(value)


class SlowConnection:
    def __init__(self, clock):
        self.clock = clock
        self.timeouts = []

    def settimeout(self, value):
        self.timeouts.append(value)

    def recv(self, _size):
        self.clock.now += 100
        return b"x"


CHANNELS = [
    {"label": "Input", "red": 1, "green": 2, "switch": 5},
    {"label": "Output", "red": 3, "green": 4, "switch": 6},
]
TOKEN = "a" * 32


def pico_symbols(clock):
    source = ast.parse((Path(__file__).parents[1] / "server/main.py").read_text())
    selected = [
        node
        for node in source.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef))
        and node.name
        in {
            "LedDeck",
            "ButtonDeck",
            "WifiServer",
            "on_button",
            "sync_led_mode",
            "service_local",
            "poll_controller",
        }
    ]
    namespace = {
        "time": FakeTime(clock),
        "Pin": FakePin,
        "json": json,
        "COMMAND_READ_TIMEOUT_MS": 1000,
        "BUTTON_DEBOUNCE_MS": 50,
        "LONG_PRESS_MS": 3000,
    }
    exec(compile(ast.Module(selected, []), "main.py", "exec"), namespace)  # noqa: S102
    return namespace


def test_session_json_preserves_lowercase_token_and_raw_command_is_locked():
    clock = Clock()
    symbols = pico_symbols(clock)
    manager = Sessions(
        CHANNELS, "id", "Bench", clock.ticks_ms, clock.ticks_diff, lambda _: None
    )
    servos = FakeServos()
    leds = type(
        "Leds",
        (),
        {"reflect": lambda self: None, "set_claimed": lambda self, _channels: None},
    )()
    server = object.__new__(symbols["WifiServer"])
    server.sessions, server.servos, server.leds = manager, servos, leds

    connection = Connection()
    server._handle(
        "SESSION " + json.dumps({"op": "claim", "token": TOKEN, "channels": [0]}),
        connection,
    )
    assert json.loads(connection.writes[-1]) == {
        "ok": True,
        "channels": [0],
        "lease_ms": 15000,
        "poll_supported": True,
    }
    server._handle("OPEN 0", connection)
    assert connection.writes[-1] == b"LOCKED\n"
    server._handle(
        "SESSION "
        + json.dumps(
            {"op": "operate", "token": TOKEN, "action": "open", "channels": [0]}
        ),
        connection,
    )
    assert json.loads(connection.writes[-1]) == {"ok": True}
    assert servos.actions == [("open", 0)]


def test_double_blink_and_physical_buttons_work_without_releasing_claim():
    clock = Clock()
    symbols = pico_symbols(clock)
    FakePin.pins = {}
    servos = FakeServos()
    leds = symbols["LedDeck"](CHANNELS, servos)
    leds.set_mode(leds.BLINK)
    leds.set_claimed([0])
    for moment, expected in ((50, 1), (100, 0), (200, 1), (300, 0)):
        clock.now = moment
        leds.tick()
        assert FakePin.pins[1].values[-1] == expected

    manager = Sessions(
        CHANNELS, "id", "Bench", clock.ticks_ms, clock.ticks_diff, lambda _: None
    )
    assert manager.claim(TOKEN, [0])["ok"]
    symbols.update(
        {
            "server": type("Server", (), {"running": True})(),
            "sessions": manager,
            "servos": servos,
            "leds": leds,
        }
    )
    symbols["on_button"](0, False)
    symbols["on_button"](1, False)
    assert servos.actions == [("toggle", 0), ("toggle", 1)]
    assert manager.locked_channels() == {0}
    assert manager.claim("b" * 32, [0])["error"] == "busy"


def test_physical_toggle_is_visible_to_connected_client(channels, pwm, clock):
    symbols = pico_symbols(clock)
    servos = ServoBoard(channels, pwm, clock.ticks_ms, clock.ticks_diff)
    manager = Sessions(
        channels,
        "id",
        "Bench",
        clock.ticks_ms,
        clock.ticks_diff,
        lambda _: None,
    )
    assert manager.claim(TOKEN, [0])["ok"]
    server = object.__new__(symbols["WifiServer"])
    server.servos = servos
    server.sessions = manager
    server.leds = type(
        "Leds", (), {"reflect": lambda self: None, "set_claimed": lambda self, _: None}
    )()
    server.running = True
    symbols.update(server=server, servos=servos, leds=server.leds, sessions=manager)
    connection = Connection()

    symbols["on_button"](0, False)
    server._handle("STATE", connection)
    assert connection.writes[-1].startswith(b"CH0=0/90/0/90/1,")
    # A repeated local press uses the new target; the owning PC can still operate.
    symbols["on_button"](0, False)
    server._handle("STATE", connection)
    assert connection.writes[-1].startswith(b"CH0=0/0/0/90/1,")
    server._handle("OPEN 0", connection)
    assert connection.writes[-1] == b"LOCKED\n"
    server._handle(
        "SESSION "
        + json.dumps(
            {"op": "operate", "token": TOKEN, "action": "open", "channels": [0]}
        ),
        connection,
    )
    assert json.loads(connection.writes[-1]) == {"ok": True}
    assert servos.angles[0] == 90
    assert manager.locked_channels() == {0}


def test_session_info_tracks_servo_fault(channels, pwm, clock, monkeypatch):
    symbols = pico_symbols(clock)
    servos = ServoBoard(channels, pwm, clock.ticks_ms, clock.ticks_diff)
    server = object.__new__(symbols["WifiServer"])
    server.servos = servos
    server.leds = symbols["LedDeck"](channels, servos)
    server.sessions = Sessions(
        channels,
        "id",
        "Bench",
        clock.ticks_ms,
        clock.ticks_diff,
        lambda _: None,
        faults=servos.faults,
    )
    conn = Connection()

    def fail_write(_channel, _angle):
        raise OSError("I2C")

    with monkeypatch.context() as fault:
        fault.setattr(pwm, "set_servo_angle", fail_write)
        server._handle("OPEN 0", conn)
        assert conn.writes[-1] == b"OK\n"
        servos.tick()
        server._handle('SESSION {"op":"info"}', conn)
        assert [ch["fault"] for ch in json.loads(conn.writes[-1])["channels"]] == [
            True,
            True,
        ]

    symbols.update(server=server, servos=servos, leds=server.leds)
    symbols["on_button"](0, False)
    servos.tick()
    server._handle('SESSION {"op":"info"}', conn)
    assert [ch["fault"] for ch in json.loads(conn.writes[-1])["channels"]] == [
        False,
        True,
    ]


class Wifi:
    def __init__(self, clock):
        self.clock = clock
        self.connected = True
        self.connect_times = []
        self.disconnect_times = []
        self.configurations = []

    def active(self, enabled):
        assert enabled

    def isconnected(self):
        return self.connected

    def connect(self, _ssid, _password):
        self.connect_times.append(self.clock.now)

    def disconnect(self):
        self.disconnect_times.append(self.clock.now)
        self.connected = False

    def ifconfig(self, config=None):
        if config is not None:
            self.configurations.append(config)
        return ("192.0.2.10",)


class ListeningSocket:
    def __init__(self, *_args):
        self.connections = deque()
        self.closed = False

    def bind(self, address):
        self.address = address

    def setsockopt(self, *_args):
        pass

    def listen(self, _backlog):
        pass

    def settimeout(self, timeout):
        assert timeout == 0

    def recvfrom(self, _size):
        raise OSError("No datagram")

    def accept(self):
        if self.connections:
            return self.connections.popleft(), ("192.0.2.20", 4321)
        raise OSError("No connection")

    def close(self):
        self.closed = True


def start_controller(clock):
    wifi = Wifi(clock)
    symbols = pico_symbols(clock)
    symbols.update(
        network=SimpleNamespace(WLAN=lambda _: wifi, STA_IF=0),
        socket=SimpleNamespace(
            socket=ListeningSocket,
            AF_INET=2,
            SOCK_DGRAM=2,
            SOL_SOCKET=1,
            SO_REUSEADDR=2,
        ),
        DiscoveryResponder=DiscoveryResponder,
        ubinascii=SimpleNamespace(hexlify=lambda _: b"a0ff"),
        unique_id=lambda: b"test",
        SERVER_PORT=12345,
        DISCOVERY_PORT=12346,
        SSID="test",
        PASSWORD="test",  # noqa: S106 - synthetic WLAN fixture
        USE_STATIC_IP=True,
        STATIC_IFCONFIG=("192.0.2.10", "255.255.255.0", "192.0.2.1", "192.0.2.53"),
    )
    servos = FakeServos()
    leds = symbols["LedDeck"](CHANNELS, servos)
    sessions = Sessions(
        CHANNELS, "a0ff", "Bench", clock.ticks_ms, clock.ticks_diff, lambda _: None
    )
    server = symbols["WifiServer"](servos, leds, sessions)
    buttons = symbols["ButtonDeck"](CHANNELS, symbols["on_button"])
    symbols.update(server=server, servos=servos, leds=leds, buttons=buttons)
    assert server.start()
    return server, buttons, wifi, symbols["poll_controller"]


@pytest.mark.parametrize("discovery_available", [True, False])
def test_wifi_reconnect_keeps_buttons_and_servo_ticks_running(
    monkeypatch, discovery_available, capsys
):
    clock = Clock()
    server, buttons, wifi, poll = start_controller(clock)
    assert server.sessions.claim(TOKEN, [0])["ok"]
    tcp, udp = server.sock, server.discovery.sock

    def at(moment):
        clock.now = moment
        poll()

    wifi.connected = False
    at(1999)
    assert server.running and not tcp.closed and not udp.closed
    at(2000)
    assert server.reconnecting and not server.running
    assert tcp.closed and udp.closed
    assert server.sessions.renew(TOKEN)["error"] == "lease_lost"
    assert wifi.connect_times == [2000]
    assert server.servos.actions == []
    assert server.leds.mode == server.leds.RECONNECTING

    ticks = server.servos.ticks
    buttons.switches[0].value(0)
    at(2100)
    at(2150)
    buttons.switches[0].value(1)
    at(2200)
    at(2250)
    assert server.servos.actions == [("toggle", 0)]
    assert server.servos.ticks == ticks + 4
    assert server.leds.red[0].level == 1
    at(3000)
    assert server.leds.red[0].level == 0
    for moment in range(4000, 12000, 2000):
        at(moment)
    assert wifi.connect_times == [2000]
    at(12000)
    assert wifi.connect_times == [2000, 12000]

    wifi.connected = True
    with monkeypatch.context() as unavailable:
        if not discovery_available:
            unavailable.setattr(server.discovery, "start", lambda: False)
        at(14000)
    recovered_tcp = server.sock
    assert server.running and not server.reconnecting
    assert recovered_tcp is not None and recovered_tcp is not tcp
    assert not recovered_tcp.closed
    if discovery_available:
        assert server.discovery.sock is not None and server.discovery.sock is not udp
    else:
        assert server.discovery.sock is None
        assert (
            "UDP discovery unavailable; TCP control remains available"
            in capsys.readouterr().out
        )
    at(16000)
    assert server.running and not server.reconnecting
    assert server.sock is recovered_tcp
    assert wifi.configurations == [wifi.configurations[0]] * 2

    class StateConnection(Connection):
        data = iter(b"STATE\n")
        closed = False

        def settimeout(self, _value):
            pass

        def recv(self, _size):
            return bytes([next(self.data)])

        def close(self):
            self.closed = True

    connection = StateConnection()
    server.sock.connections.append(connection)
    at(16020)
    assert connection.writes == [b"STATE\n"]
    assert connection.closed


def test_session_poll_renews_and_returns_state_and_faults():
    clock = Clock()
    server, _, _, _ = start_controller(clock)
    conn = Connection()

    def request(body):
        server._handle("SESSION " + json.dumps(body), conn)
        return json.loads(conn.writes[-1])

    assert request({"op": "claim", "token": TOKEN, "channels": [0]})["poll_supported"]
    clock.now = 14000
    result = request({"op": "poll", "token": TOKEN})
    assert result["ok"] and result["state"] == "STATE"
    assert result["info"]["channels"][0]["locked"]
    assert result["info"]["channels"][0]["fault"] is False
    clock.now = 28000
    assert request({"op": "poll", "token": TOKEN})["ok"]
    clock.now = 44000
    assert request({"op": "poll", "token": TOKEN}) == {
        "ok": False,
        "error": "lease_lost",
    }


def test_initial_wifi_connect_failure_retries_without_stopping_local_control(
    monkeypatch,
):
    clock = Clock()
    server, buttons, wifi, poll = start_controller(clock)
    assert server.stop()
    wifi.connected = False
    connect = wifi.connect

    def fail_connect(*args):
        connect(*args)
        raise OSError("Wi-Fi unavailable")

    with monkeypatch.context() as unavailable:
        unavailable.setattr(wifi, "connect", fail_connect)
        assert server.start()
    assert server.reconnecting and not server.running

    buttons.switches[0].value(0)
    for moment in (10, 60):
        clock.now = moment
        poll()
    buttons.switches[0].value(1)
    for moment in (110, 160, 10000):
        clock.now = moment
        poll()
    assert server.servos.actions == [("toggle", 0)]
    assert wifi.connect_times == [0, 10000]

    wifi.connected = True
    clock.now = 12000
    poll()
    assert server.running and not server.reconnecting


def test_long_press_cancels_reconnect():
    clock = Clock()
    server, buttons, wifi, poll = start_controller(clock)
    wifi.connected = False
    clock.now = 2000
    poll()
    assert server.reconnecting
    buttons.switches[0].value(0)
    for moment in (2100, 2150, 5150):
        clock.now = moment
        poll()
    assert server.leds.mode == server.leds.FAST
    buttons.switches[0].value(1)
    for moment in (5200, 5250, 15000):
        clock.now = moment
        poll()
    assert not server.reconnecting and not server.running
    assert server.leds.mode == server.leds.NORMAL
    assert wifi.connect_times == [2000]
    assert wifi.disconnect_times == [5250]


def test_fault_led_priority_over_network_modes_and_below_long_press():
    clock = Clock()
    symbols = pico_symbols(clock)
    servos = FakeServos()
    leds = symbols["LedDeck"](CHANNELS, servos)
    servos.faults[0] = True
    for mode, start in (
        (leds.NORMAL, 0),
        (leds.BLINK, 200),
        (leds.RECONNECTING, 400),
    ):
        clock.now = start
        leds.set_mode(mode)
        clock.now = start + 100
        leds.tick()
        first = (leds.red[0].level, leds.green[0].level)
        clock.now += 100
        leds.tick()
        second = (leds.red[0].level, leds.green[0].level)
        assert {first, second} == {(0, 1), (1, 0)}
    leds.set_mode(leds.FAST)
    clock.now += 60
    leds.tick()
    assert all(pin.level == 1 for pin in leds.red + leds.green)


def test_startup_i2c_failure_flashes_all_channels_without_starting_server():
    clock = Clock()
    symbols = pico_symbols(clock)
    source = ast.parse((Path(__file__).parents[1] / "server/main.py").read_text())
    first_hardware = next(
        index
        for index, node in enumerate(source.body)
        if isinstance(node, ast.Try)
        and any(
            isinstance(statement, ast.Assign)
            and isinstance(statement.value, ast.Call)
            and isinstance(statement.value.func, ast.Name)
            and statement.value.func.id == "PCA9685"
            for statement in node.body
        )
    )

    class StopLoop(Exception):
        pass

    def sleep(_seconds):
        clock.now += 20
        if clock.now >= 200:
            raise StopLoop

    def fail_init(*_args, **_kwargs):
        raise OSError("PCA9685 unavailable")

    symbols.update(
        CHANNELS=CHANNELS,
        I2C=lambda *_args, **_kwargs: object(),
        I2C_BUS=0,
        I2C_SDA_PIN=7,
        I2C_SCL_PIN=8,
        I2C_FREQ=400_000,
        PCA9685=fail_init,
        PCA9685_ADDRESS=0x40,
        PCA9685_ANGLE_OFFSET=0,
    )
    symbols["time"].sleep = sleep
    with pytest.raises(StopLoop):
        exec(  # noqa: S102
            compile(ast.Module(source.body[first_hardware:], []), "main.py", "exec"),
            symbols,
        )
    assert "servos" not in symbols and "server" not in symbols
    leds = symbols["leds"]
    assert all(pin.values[0] and not pin.values[-1] for pin in leds.red)
    assert all(not pin.values[0] and pin.values[-1] for pin in leds.green)


def test_incomplete_continuous_request_hits_deadline_without_acting():
    clock = Clock()
    symbols = pico_symbols(clock)
    server = object.__new__(symbols["WifiServer"])
    server.servos = FakeServos()
    server.leds = type("Leds", (), {"tick": lambda self: None})()
    assert server._readline(SlowConnection(clock)) == ""
    assert clock.now >= 1000


def test_complete_maximum_unicode_label_patch_exceeds_old_limit_but_is_accepted():
    clock = Clock()
    symbols = pico_symbols(clock)
    server = object.__new__(symbols["WifiServer"])
    server.servos = FakeServos()
    server.leds = type("Leds", (), {"tick": lambda self: None})()
    command = "SESSION " + json.dumps(
        {
            "op": "set_config",
            "token": TOKEN,
            "label": "測定" * 16,
            "channel_labels": {str(ch): "😀" * 24 for ch in range(16)},
        }
    )
    assert len(command.encode()) > 4096

    class FullConnection:
        def __init__(self):
            self.data = (command + "\n").encode()
            self.reads = 0

        def settimeout(self, _timeout):
            pass

        def recv(self, size):
            self.reads += 1
            chunk, self.data = self.data[:size], self.data[size:]
            return chunk

    connection = FullConnection()
    assert server._readline(connection) == command
    assert connection.reads == (len(command.encode()) + 256) // 256


def test_open_without_newline_times_out_and_returns_unknown():
    clock = Clock()
    symbols = pico_symbols(clock)
    server = object.__new__(symbols["WifiServer"])
    server.servos = FakeServos()
    server.leds = symbols["LedDeck"](CHANNELS, server.servos)
    server.sessions = Sessions(
        CHANNELS, "id", "Bench", clock.ticks_ms, clock.ticks_diff, lambda _: None
    )

    class StalledConnection(Connection):
        def __init__(self):
            super().__init__()
            self.data = iter(b"OPEN 1")

        def settimeout(self, timeout):
            self.timeout = timeout

        def recv(self, _size):
            byte = next(self.data, None)
            if byte is not None:
                return bytes([byte])
            clock.now += round(self.timeout * 1000)
            raise OSError("timed out")

    connection = StalledConnection()
    server._handle(server._readline(connection), connection)
    assert connection.writes == [b"UNKNOWN\n"]
    assert server.servos.actions == []
    assert server.servos.ticks > 0
    assert clock.now == 1000
