"""PCA9685 brown-out recovery against a register-level chip model."""

import pytest

from server.pca9685 import PCA9685
from server.servo import DriverGuard, ServoBoard

POWER_ON_MODE1 = 0x11  # SLEEP | ALLCALL, auto-increment disabled
POWER_ON_PRESCALE = 0x1E


class RegisterChip:
    """Minimal PCA9685 register file: auto-increment, SLEEP and power loss."""

    def __init__(self):
        self.power_cycle()
        self.writes = 0

    def power_cycle(self):
        self.registers = bytearray(256)
        self.registers[0x00] = POWER_ON_MODE1
        self.registers[0xFE] = POWER_ON_PRESCALE
        for channel in range(16):
            self.registers[0x09 + 4 * channel] = 0x10  # LEDn full off

    def writeto_mem(self, address, register, data):
        assert address == 0x40
        self.writes += 1
        auto_increment = self.registers[0x00] & 0x20
        for offset, value in enumerate(bytes(data)):
            target = register + offset if auto_increment else register
            if target == 0xFE and not self.registers[0x00] & 0x10:
                continue  # PRE_SCALE is writable only while asleep.
            self.registers[target] = value & 0x7F if target == 0x00 else value

    def readfrom_mem(self, address, register, count):
        assert address == 0x40
        return bytes(self.registers[register : register + count])

    def output(self, channel):
        """Return the effective pulse end tick, or None while the output is off."""
        base = 0x06 + 4 * channel
        if self.registers[0x00] & 0x10 or self.registers[base + 3] & 0x10:
            return None
        return self.registers[base + 2] | (self.registers[base + 3] & 0x0F) << 8


class PreservedDriver:
    """An older calibrated driver that has no reset() method."""

    def __init__(self, chip):
        self._driver = PCA9685(chip)

    def set_servo_angle(self, channel, angle):
        self._driver.set_servo_angle(channel, angle)

    def disable(self, channel):
        self._driver.disable(channel)


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr("server.pca9685.sleep", lambda _seconds: None)


def make_board(channels, clock, driver=None, chip=None):
    chip = chip or RegisterChip()
    driver = driver or PCA9685(chip)
    board = ServoBoard(
        channels,
        driver,
        clock.ticks_ms,
        clock.ticks_diff,
        step_degrees=30,
        step_interval_ms=20,
        release_delay_ms=100,
        max_active=len(channels),
        guard=DriverGuard(chip, 0x40, driver),
    )
    return board, chip, driver


def settle(board, clock, ticks=12):
    for _ in range(ticks):
        board.tick()
        clock.advance(20)


def test_standalone_pca9685_power_loss_is_reinitialized_before_next_motion(
    channels, clock
):
    board, chip, _driver = make_board(channels, clock)
    settle(board, clock)
    assert not board.busy()
    assert chip.output(0) is None  # released while idle: no I2C traffic

    # No I2C error was ever seen; only the PCA9685 browned out while idle.
    chip.power_cycle()
    assert board.open(0)
    settle(board, clock)

    assert board.faults == [False, False]
    assert chip.registers[0xFE] == 121
    assert chip.registers[0x00] & 0x30 == 0x20
    assert board.positions == [90, 10]
    board.open(0)
    board.tick()
    assert chip.output(0) == 307  # 1500 us at 50 Hz, written with auto-increment
    assert chip.output(1) is None  # other channel stays released, not re-driven


def test_power_loss_without_reset_support_stays_faulted_and_never_reports_success(
    channels, clock
):
    chip = RegisterChip()
    board, chip, _driver = make_board(channels, clock, PreservedDriver(chip), chip)
    settle(board, clock)

    chip.power_cycle()
    writes = chip.writes
    assert board.open(0)
    board.tick()

    assert board.faults == [True, False]
    assert board.positions == [0, 10]
    assert board.angles == [0, 10]
    assert not board.busy(0)
    assert chip.registers[0x00] == POWER_ON_MODE1  # untouched, still asleep
    assert chip.writes == writes + 1  # only the best-effort full-off release

    # Every further command re-checks and keeps the fault instead of moving.
    assert board.open(0)
    settle(board, clock)
    assert board.faults == [True, False]
    assert board.positions == [0, 10]


def raise_value_error():
    raise ValueError("custom driver bug")


@pytest.mark.parametrize("reset", [lambda: None, raise_value_error])
def test_reinitialization_that_does_not_restore_registers_keeps_the_fault(
    channels, clock, monkeypatch, reset
):
    board, chip, driver = make_board(channels, clock)
    settle(board, clock)
    chip.power_cycle()
    monkeypatch.setattr(driver, "reset", reset)

    assert board.open(1)
    board.tick()
    assert board.faults == [False, True]
    assert board.positions == [0, 10]
    assert not board.busy()


def test_reinitialization_stops_other_motion_on_the_shared_chip(channels, clock):
    board, chip, _driver = make_board(channels, clock)
    settle(board, clock)

    assert board.open(0)
    board.tick()
    clock.advance(20)
    board.tick()
    assert board.positions[0] == 30 and board.busy(0)

    chip.power_cycle()  # CH0 is mid-motion; its output is now full-off
    assert board.open(1)
    board.tick()

    # CH0 was not resumed from a stale position; CH1 proceeds on a restored chip.
    assert board.faults == [True, False]
    assert board.angles[0] == board.positions[0] == 30
    assert not board.busy(0)
    settle(board, clock)
    assert chip.output(0) is None
    assert board.positions == [30, 70]
    assert board.faults == [True, False]


def test_reinitialization_releases_a_settled_channel_without_faulting_it(
    channels, clock
):
    board, chip, _driver = make_board(channels, clock)
    settle(board, clock)
    assert board.open(0)
    for _ in range(4):
        board.tick()
        clock.advance(20)
    assert board.positions[0] == 90 and board.busy(0)  # holding before release

    chip.power_cycle()
    assert board.open(1)
    board.tick()
    assert board.faults == [False, False]
    assert not board.busy(0)
    assert chip.output(0) is None
    settle(board, clock)
    assert board.positions == [90, 70]


def test_retargeting_an_active_channel_checks_the_driver_first(channels, clock):
    chip = RegisterChip()
    board, chip, _driver = make_board(channels, clock, PreservedDriver(chip), chip)
    settle(board, clock)
    assert board.open(0)
    board.tick()
    clock.advance(20)
    board.tick()
    assert board.busy(0)
    assert board.open(0)  # same target: a configured driver stays healthy
    board.tick()
    assert board.faults == [False, False]

    chip.power_cycle()
    assert board.close(0)
    board.tick()
    assert board.faults[0]
    assert not board.busy(0)


def test_healthy_driver_is_checked_once_per_tick(channels, clock):
    board, chip, _driver = make_board(channels, clock)
    reads = []
    original = chip.readfrom_mem

    def counted(address, register, count):
        reads.append(register)
        return original(address, register, count)

    chip.readfrom_mem = counted
    board.tick()  # both boot motions start in one tick
    assert reads == [0x00, 0xFE]
    assert board.faults == [False, False]


def test_guard_rejects_a_driver_left_asleep_at_boot():
    chip = RegisterChip()
    with pytest.raises(OSError, match="asleep"):
        DriverGuard(chip, 0x40, object())


def test_untrusted_driver_faults_the_new_and_running_motions(channels, clock):
    board, chip, _driver = make_board(channels, clock)
    settle(board, clock)
    assert board.open(1)
    board.tick()
    clock.advance(20)
    board.tick()
    assert board.positions == [0, 40]

    def fail(*_args):
        raise OSError("I2C")

    chip.readfrom_mem = fail
    chip.writeto_mem = fail  # the best-effort release fails as well
    assert board.open(0)
    board.tick()
    assert board.faults == [True, True]
    assert board.positions == [0, 40]
    assert board.angles == [0, 40]
    assert not board.busy()


@pytest.mark.parametrize("write_fails", [False, True])
def test_repeat_at_settled_target_after_reset_reapplies_output(
    channels, clock, monkeypatch, write_fails
):
    board, chip, driver = make_board(channels, clock)
    settle(board, clock)
    assert board.open(0)
    for _ in range(4):
        board.tick()
        clock.advance(20)
    assert board.positions[0] == 90 and board.busy(0)

    chip.power_cycle()
    assert chip.output(0) is None
    if write_fails:

        def fail_write(_channel, _angle):
            raise OSError("I2C PWM write failed")

        monkeypatch.setattr(driver, "set_servo_angle", fail_write)
    assert board.open(0)
    board.tick()
    assert (chip.output(0) is None) == write_fails
    assert board.faults[0] == write_fails
    assert board.busy(0) != write_fails
