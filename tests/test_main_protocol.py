"""Exercise Pico request handling without importing MicroPython hardware modules."""

import ast
import json
from pathlib import Path

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
    pins = {}

    def __init__(self, number, _mode):
        self.number = number
        self.values = []
        self.pins[number] = self

    def value(self, value):
        self.values.append(value)


class FakeServos:
    def __init__(self):
        self.positions = [0, 90]
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
    {"label": "Input", "red": 1, "green": 2},
    {"label": "Output", "red": 3, "green": 4},
]
TOKEN = "a" * 32


def pico_symbols(clock):
    source = ast.parse((Path(__file__).parents[1] / "server/main.py").read_text())
    selected = [
        node
        for node in source.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef))
        and node.name in {"LedDeck", "WifiServer", "on_button"}
    ]
    namespace = {
        "time": FakeTime(clock),
        "Pin": FakePin,
        "json": json,
        "COMMAND_READ_TIMEOUT_MS": 1000,
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


def test_double_blink_and_button_do_not_change_a_claimed_channel():
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
    # Re-execute only the button function with its runtime collaborators.
    button_node = next(
        node
        for node in ast.parse(
            (Path(__file__).parents[1] / "server/main.py").read_text()
        ).body
        if isinstance(node, ast.FunctionDef) and node.name == "on_button"
    )
    exec(compile(ast.Module([button_node], []), "main.py", "exec"), symbols)  # noqa: S102
    symbols["on_button"](0, False)
    symbols["on_button"](1, False)
    assert servos.actions[-1] == ("toggle", 1)


def test_incomplete_continuous_request_hits_deadline_without_acting():
    clock = Clock()
    symbols = pico_symbols(clock)
    server = object.__new__(symbols["WifiServer"])
    server.servos = FakeServos()
    server.leds = type("Leds", (), {"tick": lambda self: None})()
    assert server._readline(SlowConnection(clock)) == ""
    assert clock.now >= 1000
