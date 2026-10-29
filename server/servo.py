"""Hardware-independent servo motion scheduling for the Pico W server."""


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

        self.angles = [channel["close"] for channel in channels]
        self.positions = list(self.angles)
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

        self.angles[index] = angle
        if index in self._active:
            self._active[index]["settle_at"] = (
                self._ticks_ms() if self.positions[index] == angle else None
            )
        elif index not in self._pending:
            self._pending.append(index)
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

        for index, state in self._active.items():
            target = self.angles[index]
            position = self.positions[index]
            if position != target:
                if self._ticks_diff(now, state["last_step"]) < self.step_interval_ms:
                    continue
                distance = target - position
                step = min(abs(distance), self.step_degrees)
                position += step if distance > 0 else -step
                self.positions[index] = position
                self._write_angle(index, position)
                state["last_step"] = now
                state["settle_at"] = now if position == target else None
                continue

            if self._ticks_diff(now, state["settle_at"]) >= self.release_delay_ms:
                if self.release_pwm:
                    self._pwm.disable(self.channels[index]["servo"])
                finished.append(index)

        for index in finished:
            del self._active[index]

        while self._pending and len(self._active) < self.max_active:
            index = self._pending.pop(0)
            self._write_angle(index, self.positions[index])
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

    def _write_angle(self, index, angle):
        self._pwm.set_servo_angle(self.channels[index]["servo"], angle)
