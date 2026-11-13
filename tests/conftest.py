import pytest


@pytest.fixture
def channels():
    return (
        {
            "label": "CH00",
            "servo": 0,
            "switch": 2,
            "green": 3,
            "red": 4,
            "close": 0,
            "open": 90,
        },
        {
            "label": "CH01",
            "servo": 1,
            "switch": 5,
            "green": 6,
            "red": 7,
            "close": 10,
            "open": 70,
        },
    )


class FakeClock:
    def __init__(self):
        self.now = 0

    def ticks_ms(self):
        return self.now

    @staticmethod
    def ticks_diff(new, old):
        return new - old

    def advance(self, milliseconds):
        self.now += milliseconds


class FakePwm:
    def __init__(self):
        self.writes = []
        self.disabled = []

    def set_servo_angle(self, channel, angle):
        self.writes.append((channel, angle))

    def disable(self, channel):
        self.disabled.append(channel)


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def pwm():
    return FakePwm()
