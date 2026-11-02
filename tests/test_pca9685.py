import pytest

from server.pca9685 import PCA9685


class FakeI2c:
    def __init__(self):
        self.writes = []

    def writeto_mem(self, address, register, value):
        self.writes.append((address, register, bytes(value)))

    def readfrom_mem(self, address, register, count):
        assert (address, register, count) == (0x40, 0, 1)
        return b"\x01"


def test_initializes_and_writes_servo(monkeypatch):
    monkeypatch.setattr("server.pca9685.sleep", lambda _seconds: None)
    i2c = FakeI2c()
    driver = PCA9685(i2c, angle_offset=10)
    assert i2c.writes[0] == (0x40, 0, b"\x00")
    assert i2c.writes[-1] == (0x40, 0, b"\xa1")

    driver.set_servo_angle(2, -20)
    assert i2c.writes[-1] == (0x40, 0x0E, bytes([0, 0, 102, 0]))
    driver.set_servo_angle(2, 200)
    assert i2c.writes[-1] == (0x40, 0x0E, bytes([0, 0, 0, 2]))
    driver.disable(2)
    assert i2c.writes[-1] == (0x40, 0x0E, bytes([0, 0, 0, 16]))


@pytest.mark.parametrize(
    ("method", "args", "message"),
    [
        ("set_pwm", (-1, 0, 1), "channel"),
        ("set_pwm", (0, -1, 1), "ticks"),
        ("set_pwm", (0, 0, 4096), "ticks"),
        ("disable", (16,), "channel"),
    ],
)
def test_rejects_invalid_output(monkeypatch, method, args, message):
    monkeypatch.setattr("server.pca9685.sleep", lambda _seconds: None)
    driver = PCA9685(FakeI2c())
    with pytest.raises(ValueError, match=message):
        getattr(driver, method)(*args)


def test_disabled_channel_can_be_reenabled_without_reset_and_other_channel_is_untouched(
    monkeypatch,
):
    monkeypatch.setattr("server.pca9685.sleep", lambda _: None)
    i2c = FakeI2c()
    driver = PCA9685(i2c, servo_min_us=610, servo_max_us=2310)
    initial_writes = len(i2c.writes)
    for _ in range(20):
        driver.disable(2)
        assert i2c.writes[-1][2][3] == 0x10
        driver.set_servo_angle(2, 90)
        assert i2c.writes[-1][2][3] & 0x10 == 0
    assert all(register == 0x0E for _, register, _ in i2c.writes[initial_writes:])
    assert driver.servo_min_us == 610 and driver.servo_max_us == 2310
