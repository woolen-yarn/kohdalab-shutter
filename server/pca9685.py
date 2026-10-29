from time import sleep


class PCA9685:
    def __init__(
        self,
        i2c,
        address=0x40,
        angle_offset=0,
        servo_min_us=500,
        servo_max_us=2500,
        frequency_hz=50,
    ):
        self.i2c = i2c
        self.address = address
        self.angle_offset = angle_offset
        self.servo_min_us = servo_min_us
        self.servo_max_us = servo_max_us
        self.frequency_hz = frequency_hz
        self.reset()

    def write(self, register, value):
        self.i2c.writeto_mem(self.address, register, bytes([value]))

    def reset(self):
        self.write(0x00, 0x00)
        sleep(0.01)

        prescale = int(round(25_000_000 / (4096 * self.frequency_hz)) - 1)
        old_mode = int.from_bytes(
            self.i2c.readfrom_mem(self.address, 0x00, 1), "little"
        )

        self.write(0x00, (old_mode & 0x7F) | 0x10)
        self.write(0xFE, prescale)
        self.write(0x00, old_mode)
        sleep(0.005)
        self.write(0x00, old_mode | 0xA1)

    def set_pwm(self, channel, on_tick, off_tick):
        if not 0 <= channel <= 15:
            raise ValueError("PCA9685 channel must be in 0..15")
        if not 0 <= on_tick <= 4095 or not 0 <= off_tick <= 4095:
            raise ValueError("PWM ticks must be in 0..4095")
        register = 0x06 + 4 * channel
        self.i2c.writeto_mem(
            self.address,
            register,
            bytearray(
                [
                    on_tick & 0xFF,
                    on_tick >> 8,
                    off_tick & 0xFF,
                    off_tick >> 8,
                ]
            ),
        )

    def set_servo_angle(self, channel, angle):
        angle = max(0, min(180, angle + self.angle_offset))
        pulse_us = (
            self.servo_min_us + (self.servo_max_us - self.servo_min_us) * angle / 180
        )
        period_us = 1_000_000 / self.frequency_hz
        off_tick = int(pulse_us * 4096 / period_us)
        self.set_pwm(channel, 0, off_tick)

    def disable(self, channel):
        """Set the PCA9685 full-off bit for one channel."""
        if not 0 <= channel <= 15:
            raise ValueError("PCA9685 channel must be in 0..15")
        register = 0x06 + 4 * channel
        self.i2c.writeto_mem(self.address, register, bytearray([0, 0, 0, 0x10]))
