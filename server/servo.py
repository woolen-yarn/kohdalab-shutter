"""Hardware-independent servo motion scheduling for the Pico W server."""

PCA9685_MODE1 = 0x00
PCA9685_PRE_SCALE = 0xFE
PCA9685_SLEEP = 0x10
PCA9685_AUTO_INCREMENT = 0x20


class DriverGuard:
    """Detect a PCA9685 that lost power on its own before trusting a new motion.

    A PCA9685 that browns out while the Pico stays powered returns to SLEEP with
    its power-on prescale and register mode, yet still ACKs every write. The
    baseline is read from the calibrated driver already on the Pico (the update
    tool preserves that file), so its own prescale and register mode are kept.
    """

    def __init__(self, i2c, address, pwm):
        self._i2c = i2c
        self._address = address
        self._pwm = pwm
        mode, prescale = self._read()
        if mode & PCA9685_SLEEP:
            raise OSError("PCA9685 is still asleep after initialization")
        self._mode = mode & PCA9685_AUTO_INCREMENT
        self._prescale = prescale

    def _read(self):
        mode = self._i2c.readfrom_mem(self._address, PCA9685_MODE1, 1)[0]
        prescale = self._i2c.readfrom_mem(self._address, PCA9685_PRE_SCALE, 1)[0]
        return mode, prescale

    def _configured(self):
        mode, prescale = self._read()
        return (
            not mode & PCA9685_SLEEP
            and (mode & PCA9685_AUTO_INCREMENT) == self._mode
            and prescale == self._prescale
        )

    def check(self):
        """Return True after a reinitialization; raise OSError if not trusted."""
        if self._configured():
            return False
        reset = getattr(self._pwm, "reset", None)
        if not callable(reset):
            raise OSError("PCA9685 lost its configuration; driver cannot reset")
        try:
            reset()
        except Exception as exc:
            # A preserved custom driver must not stop the servo/button loop.
            raise OSError("PCA9685 reinitialization failed: {}".format(exc)) from exc
        if not self._configured():
            raise OSError("PCA9685 reinitialization did not restore its configuration")
        return True


class ChannelConfigurationError(ValueError):
    """Raised when a channel definition could damage or misaddress hardware."""


def validate_channels(channels):
    """Validate channel definitions before any outputs are enabled."""
    if not channels:
        raise ChannelConfigurationError("At least one channel is required")

    required = ("label", "servo", "switch", "green", "red", "close", "open")
    labels = set()
    servo_outputs = set()
    gpio_outputs = set()

    for index, channel in enumerate(channels):
        missing = [key for key in required if key not in channel]
        if missing:
            raise ChannelConfigurationError(
                "Channel {} is missing: {}".format(index, ", ".join(missing))
            )

        label = channel["label"]
        if not isinstance(label, str) or not label.strip():
            raise ChannelConfigurationError(
                "Channel {} has an invalid label".format(index)
            )
        if label in labels:
            raise ChannelConfigurationError("Duplicate channel label: {}".format(label))
        labels.add(label)

        servo = channel["servo"]
        if (
            not isinstance(servo, int)
            or isinstance(servo, bool)
            or not 0 <= servo <= 15
        ):
            raise ChannelConfigurationError("{} servo must be in 0..15".format(label))
        if servo in servo_outputs:
            raise ChannelConfigurationError(
                "Duplicate PCA9685 channel: {}".format(servo)
            )
        servo_outputs.add(servo)

        for key in ("switch", "green", "red"):
            pin = channel[key]
            if not isinstance(pin, int) or isinstance(pin, bool) or pin < 0:
                raise ChannelConfigurationError(
                    "{} {} GPIO is invalid".format(label, key)
                )
            if pin in gpio_outputs:
                raise ChannelConfigurationError("Duplicate GPIO: {}".format(pin))
            gpio_outputs.add(pin)

        for key in ("close", "open"):
            angle = channel[key]
            if (
                not isinstance(angle, int)
                or isinstance(angle, bool)
                or not 0 <= angle <= 180
            ):
                raise ChannelConfigurationError(
                    "{} {} angle must be in 0..180".format(label, key)
                )
        if channel["close"] == channel["open"]:
            raise ChannelConfigurationError(
                "{} open and close angles must differ".format(label)
            )

        for key in ("soft_open", "soft_close"):
            if key in channel and not isinstance(channel[key], bool):
                raise ChannelConfigurationError(
                    "{} {} must be boolean".format(label, key)
                )


class ServoBoard:
    """Queue, slew and release servos without blocking the server event loop.

    ``angles`` contains the requested logical state for protocol compatibility.
    ``positions`` contains the latest angle actually written to the PWM driver.
    """

    def __init__(
        self,
        channels,
        pwm,
        ticks_ms,
        ticks_diff,
        step_degrees=3,
        step_interval_ms=20,
        release_delay_ms=500,
        max_active=1,
        release_pwm=True,
        guard=None,
    ):
        validate_channels(channels)
        if step_degrees <= 0:
            raise ValueError("step_degrees must be positive")
        if step_interval_ms < 0 or release_delay_ms < 0:
            raise ValueError("motion timings cannot be negative")
        if max_active < 1:
            raise ValueError("max_active must be at least one")

        self.channels = channels
        self._pwm = pwm
        self._ticks_ms = ticks_ms
        self._ticks_diff = ticks_diff
        self.step_degrees = step_degrees
        self.step_interval_ms = step_interval_ms
        self.release_delay_ms = release_delay_ms
        self.max_active = max_active
        self.release_pwm = release_pwm
        self._guard = guard

        self.angles = [channel["close"] for channel in channels]
        self.positions = list(self.angles)
        self.faults = [False] * len(channels)
        self._pending = list(range(len(channels)))
        self._active = {}

    def count(self):
        return len(self.channels)

    def valid_channel(self, index):
        return (
            isinstance(index, int)
            and not isinstance(index, bool)
            and 0 <= index < self.count()
        )

    def close_angle(self, index):
        return self.channels[index]["close"]

    def open_angle(self, index):
        return self.channels[index]["open"]

    def set(self, index, angle):
        if (
            not self.valid_channel(index)
            or not isinstance(angle, int)
            or isinstance(angle, bool)
        ):
            return False
        if not 0 <= angle <= 180:
            return False

        self.faults[index] = False
        if index in self._active:
            # Even a repeated command may be the first one after a chip reset.
            self._active[index]["verify"] = True
            self._active[index]["settle_at"] = (
                self._ticks_ms() if self.positions[index] == angle else None
            )
        elif index not in self._pending:
            self._pending.append(index)
        self.angles[index] = angle
        return True

    def open(self, index):
        if not self.valid_channel(index):
            return False
        return self.set(index, self.open_angle(index))

    def close(self, index):
        if not self.valid_channel(index):
            return False
        return self.set(index, self.close_angle(index))

    def toggle(self, index):
        if not self.valid_channel(index):
            return False
        if self.angles[index] == self.close_angle(index):
            return self.open(index)
        return self.close(index)

    def tick(self):
        """Advance active motions once and release settled servo outputs."""
        now = self._ticks_ms()
        finished = []
        starting = [i for i, state in self._active.items() if state.get("verify")]
        if starting or self._pending:
            # Before any step of this tick, so no motion writes to a reset chip.
            self._verify_driver(starting)

        for index, state in self._active.items():
            target = self.angles[index]
            position = self.positions[index]
            if position != target:
                step_degrees, step_interval_ms = self._motion_parameters(
                    index, position, target
                )
                if self._ticks_diff(now, state["last_step"]) < step_interval_ms:
                    continue
                distance = target - position
                step = min(abs(distance), step_degrees)
                position += step if distance > 0 else -step
                if not self._write_angle(index, position):
                    finished.append(index)
                    continue
                state["last_step"] = now
                state["settle_at"] = now if position == target else None
                continue

            if self._ticks_diff(now, state["settle_at"]) >= self.release_delay_ms:
                if self.release_pwm:
                    try:
                        self._pwm.disable(self.channels[index]["servo"])
                    except OSError:
                        self._mark_fault(index)
                finished.append(index)

        for index in finished:
            del self._active[index]

        while self._pending and len(self._active) < self.max_active:
            index = self._pending.pop(0)
            if not self._write_angle(index, self.positions[index]):
                continue
            self._active[index] = {
                "last_step": now,
                "settle_at": now
                if self.positions[index] == self.angles[index]
                else None,
            }

    def busy(self, index=None):
        if index is None:
            return bool(self._pending or self._active)
        if not self.valid_channel(index):
            return False
        return index in self._pending or index in self._active

    def status_text(self):
        return ",".join(
            "CH{}={}".format(index, angle) for index, angle in enumerate(self.positions)
        )

    def state_text(self):
        """Commanded position, target, calibration, and queued/active motion."""
        return ",".join(
            "CH{}={}/{}/{}/{}/{}".format(
                index,
                self.positions[index],
                self.angles[index],
                self.close_angle(index),
                self.open_angle(index),
                int(self.busy(index)),
            )
            for index in range(self.count())
        )

    def _write_angle(self, index, angle):
        try:
            self._pwm.set_servo_angle(self.channels[index]["servo"], angle)
        except OSError:
            self._mark_fault(index)
            try:
                self._pwm.disable(self.channels[index]["servo"])
            except OSError:
                # The I2C bus may still be unavailable. Wait for another command.
                pass
            return False
        self.positions[index] = angle
        return True

    def _verify_driver(self, starting):
        """Check the shared PCA9685 once before the new motions of this tick.

        ``starting`` are active channels that received a new target. Queued
        channels are new motions as well.
        """
        if self._guard is None:
            return
        try:
            restored = self._guard.check()
        except OSError:
            # The chip cannot be trusted: no queued or running motion may count
            # an acknowledged write as success. Each needs a new command.
            for index in list(self._active) + self._pending:
                self._mark_fault(index)
                self._release_quietly(index)
            self._active = {}
            self._pending = []
            return
        for index in starting:
            self._active[index]["verify"] = False
            if restored and self.positions[index] == self.angles[index]:
                # The remembered angle may match while the physical output is off.
                if not self._write_angle(index, self.angles[index]):
                    del self._active[index]
        if restored:
            # A reset left every output full-off. Do not resume other motions
            # from stale positions; they need a new command to drive again.
            for other in [i for i in self._active if i not in starting]:
                if self.positions[other] != self.angles[other]:
                    self._mark_fault(other)
                self._release_quietly(other)
                del self._active[other]

    def _release_quietly(self, index):
        try:
            self._pwm.disable(self.channels[index]["servo"])
        except OSError:
            pass

    def _mark_fault(self, index):
        self.faults[index] = True
        self.angles[index] = self.positions[index]

    def _motion_parameters(self, index, position, target):
        """Return the slew parameters for this channel's current target."""
        channel = self.channels[index]
        soft_target = (
            target == channel["open"] and channel.get("soft_open", False)
        ) or (target == channel["close"] and channel.get("soft_close", False))
        if soft_target and abs(target - position) <= 12:
            return min(self.step_degrees, 1), max(self.step_interval_ms, 40)
        return self.step_degrees, self.step_interval_ms
