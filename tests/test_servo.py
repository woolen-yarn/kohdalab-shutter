import pytest

from server import settings
from server.servo import ChannelConfigurationError, ServoBoard, validate_channels


def make_board(channels, pwm, clock, **kwargs):
    return ServoBoard(
        channels,
        pwm,
        clock.ticks_ms,
        clock.ticks_diff,
        step_degrees=30,
        step_interval_ms=20,
        release_delay_ms=100,
        **kwargs,
    )


def test_slews_releases_and_serializes_channels(channels, pwm, clock):
    board = make_board(channels, pwm, clock)
    assert board.count() == 2
    assert board.busy()
    assert board.busy(0)
    assert not board.busy(99)
    assert board.status_text() == "CH0=0,CH1=10"
    assert board.close(1)
    assert board.close(1)

    board.tick()
    assert pwm.writes == [(0, 0)]
    assert board.open(0)
    assert board.status_text() == "CH0=0,CH1=10"

    clock.advance(19)
    board.tick()
    assert pwm.writes == [(0, 0)]

    for expected in (30, 60, 90):
        clock.advance(20)
        board.tick()
        assert pwm.writes[-1] == (0, expected)

    clock.advance(99)
    board.tick()
    assert pwm.disabled == []
    clock.advance(1)
    board.tick()
    assert pwm.disabled == [0]
    assert pwm.writes[-1] == (1, 10)

    clock.advance(100)
    board.tick()
    assert pwm.disabled == [0, 1]
    assert not board.busy()
    assert board.status_text() == "CH0=90,CH1=10"


def test_retargets_active_motion_and_reasserts_released_channel(channels, pwm, clock):
    board = make_board(channels[:1], pwm, clock)
    board.tick()
    assert board.open(0)
    clock.advance(20)
    board.tick()
    assert board.positions == [30]
    assert board.close(0)
    clock.advance(20)
    board.tick()
    assert board.positions == [0]
    assert board.toggle(0)
    assert board.angles == [90]
    assert board.toggle(0)
    assert board.angles == [0]

    clock.advance(100)
    board.tick()
    assert pwm.disabled == [0]
    assert board.close(0)
    board.tick()
    assert pwm.writes[-1] == (0, 0)


def test_multiple_active_channels_can_hold_pwm(channels, pwm, clock):
    board = make_board(channels, pwm, clock, max_active=2, release_pwm=False)
    board.tick()
    assert pwm.writes == [(0, 0), (1, 10)]
    clock.advance(100)
    board.tick()
    assert not board.busy()
    assert pwm.disabled == []


def test_firmware_default_advances_all_configured_channels_in_parallel(pwm, clock):
    board = make_board(
        settings.CHANNELS,
        pwm,
        clock,
        max_active=settings.SERVO_MAX_ACTIVE,
    )
    assert settings.SERVO_MAX_ACTIVE == len(settings.CHANNELS)

    board.tick()
    for index in range(board.count()):
        assert board.open(index)

    clock.advance(board.step_interval_ms)
    board.tick()

    assert board.positions == [
        channel["close"]
        + (
            min(abs(channel["open"] - channel["close"]), board.step_degrees)
            * (1 if channel["open"] > channel["close"] else -1)
        )
        for channel in settings.CHANNELS
    ]
    assert pwm.disabled == []


@pytest.mark.parametrize("index", [-1, 2, True, 1.5])
def test_rejects_invalid_channel(channels, pwm, clock, index):
    board = make_board(channels, pwm, clock)
    assert not board.valid_channel(index)
    assert not board.open(index)
    assert not board.close(index)
    assert not board.toggle(index)


@pytest.mark.parametrize("angle", [-1, 181, True, "90", 90.0])
def test_rejects_invalid_angle(channels, pwm, clock, angle):
    board = make_board(channels, pwm, clock)
    assert not board.set(0, angle)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"step_degrees": 0}, "step_degrees"),
        ({"step_interval_ms": -1}, "timings"),
        ({"release_delay_ms": -1}, "timings"),
        ({"max_active": 0}, "max_active"),
    ],
)
def test_rejects_invalid_motion_settings(channels, pwm, clock, kwargs, message):
    defaults = {
        "step_degrees": 3,
        "step_interval_ms": 20,
        "release_delay_ms": 100,
        "max_active": 1,
    }
    defaults.update(kwargs)
    with pytest.raises(ValueError, match=message):
        ServoBoard(channels, pwm, clock.ticks_ms, clock.ticks_diff, **defaults)


def invalid_channel(channels, mutation):
    candidate = [dict(channel) for channel in channels]
    mutation(candidate)
    return candidate


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda value: value[0].pop("open"), "missing"),
        (lambda value: value[0].update(label=""), "invalid label"),
        (lambda value: value[1].update(label="CH00"), "Duplicate channel label"),
        (lambda value: value[0].update(servo=True), "servo"),
        (lambda value: value[0].update(servo=16), "servo"),
        (lambda value: value[1].update(servo=0), "Duplicate PCA9685"),
        (lambda value: value[0].update(switch=True), "GPIO is invalid"),
        (lambda value: value[0].update(green=-1), "GPIO is invalid"),
        (lambda value: value[1].update(red=2), "Duplicate GPIO"),
        (lambda value: value[0].update(close=True), "angle"),
        (lambda value: value[0].update(close=0.0), "angle"),
        (lambda value: value[0].update(open=181), "angle"),
        (lambda value: value[0].update(open=0), "must differ"),
    ],
)
def test_validates_channel_configuration(channels, mutation, message):
    candidate = invalid_channel(channels, mutation)
    with pytest.raises(ChannelConfigurationError, match=message):
        validate_channels(candidate)


def test_requires_channels():
    with pytest.raises(ChannelConfigurationError, match="At least one"):
        validate_channels(())


def test_state_includes_custom_calibration_targets_and_motion(channels, pwm, clock):
    board = make_board(channels, pwm, clock, max_active=2)
    assert board.state_text() == "CH0=0/0/0/90/1,CH1=10/10/10/70/1"
    board.tick()
    clock.advance(100)
    board.tick()
    assert board.state_text() == "CH0=0/0/0/90/0,CH1=10/10/10/70/0"
    board.open(1)
    assert "CH1=10/70/10/70/1" in board.state_text()
