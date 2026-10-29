from machine import I2C, Pin, unique_id
import ubinascii
from discovery import DiscoveryResponder
from pca9685 import PCA9685
from servo import ServoBoard
from sessions import DeviceLabel, Sessions
from settings import (
    AUTO_START_SERVER,
    BUTTON_DEBOUNCE_MS,
    CHANNELS,
    COMMAND_READ_TIMEOUT_MS,
    DISCOVERY_PORT,
    I2C_BUS,
    I2C_FREQ,
    I2C_SCL_PIN,
    I2C_SDA_PIN,
    LONG_PRESS_MS,
    PCA9685_ADDRESS,
    PCA9685_ANGLE_OFFSET,
    SERVO_MAX_ACTIVE,
    SERVO_RELEASE_DELAY_MS,
    SERVO_RELEASE_PWM,
    SERVO_STEP_DEGREES,
    SERVO_STEP_INTERVAL_MS,
    SERVER_PORT,
    STATIC_IFCONFIG,
    USE_STATIC_IP,
)
import network
import socket
import time

try:
    import ujson as json
except ImportError:
    import json

try:
    from settings import DEVICE_LABEL
except ImportError:
    DEVICE_LABEL = "Pico W Shutter"

try:
    from wifi_config import SSID, PASSWORD
except ImportError:
    SSID = ""
    PASSWORD = ""


class LedDeck:
    NORMAL = 0
    BLINK = 1
    FAST = 2

    def __init__(self, channels, servos):
        self.channels = channels
        self.servos = servos
        self.red = [Pin(channel["red"], Pin.OUT) for channel in channels]
        self.green = [Pin(channel["green"], Pin.OUT) for channel in channels]
        self.mode = self.NORMAL
        self._phase = False
        self._last_ms = time.ticks_ms()
        self._blink_started = self._last_ms
        self.claimed = set()

    def reflect(self):
        if self.mode != self.NORMAL:
            return
        for index, angle in enumerate(self.servos.positions):
            self.red[index].value(1 if angle == self.servos.close_angle(index) else 0)
            self.green[index].value(1 if angle == self.servos.open_angle(index) else 0)
            if angle not in (
                self.servos.close_angle(index),
                self.servos.open_angle(index),
            ):
                self.red[index].value(1)
                self.green[index].value(1)

    def set_mode(self, mode):
        if self.mode == mode:
            if mode == self.NORMAL:
                self.reflect()
            return

        self.mode = mode
        self._phase = False
        self._last_ms = time.ticks_ms()
        self._blink_started = self._last_ms
        if mode == self.NORMAL:
            self.reflect()

    def set_claimed(self, channels):
        claimed = set(channels)
        if claimed != self.claimed:
            self.claimed = claimed
            self._last_ms = time.ticks_ms() - 50

    def _state_led(self, index, enabled):
        angle = self.servos.positions[index]
        if angle == self.servos.open_angle(index):
            self.green[index].value(enabled)
            self.red[index].value(0)
        elif angle == self.servos.close_angle(index):
            self.red[index].value(enabled)
            self.green[index].value(0)
        else:
            self.red[index].value(enabled)
            self.green[index].value(enabled)

    def tick(self):
        if self.mode == self.NORMAL:
            return

        now = time.ticks_ms()
        interval = 60 if self.mode == self.FAST else 50
        if time.ticks_diff(now, self._last_ms) < interval:
            return

        self._last_ms = now

        if self.mode == self.FAST:
            self._phase = not self._phase
            for red, green in zip(self.red, self.green):
                red.value(self._phase)
                green.value(self._phase)
            return

        elapsed = time.ticks_diff(now, self._blink_started) % 1200
        for index in range(len(self.channels)):
            if index in self.claimed:
                # Connected channel: two short flashes, then a long pause.
                self._state_led(index, elapsed < 100 or 200 <= elapsed < 300)
            else:
                self._state_led(index, (elapsed // 250) % 2 == 0)


class ButtonDeck:
    def __init__(self, channels, callback):
        self.switches = [
            Pin(channel["switch"], Pin.IN, Pin.PULL_UP) for channel in channels
        ]
        self._raw = [pin.value() for pin in self.switches]
        self._stable = list(self._raw)
        self._changed_at = [time.ticks_ms()] * len(channels)
        self._pressed_at = [None] * len(channels)
        self._long_pressing = [False] * len(channels)
        self.callback = callback

    def poll(self):
        now = time.ticks_ms()
        for index, pin in enumerate(self.switches):
            raw = pin.value()
            if raw != self._raw[index]:
                self._raw[index] = raw
                self._changed_at[index] = now
                continue

            if raw == self._stable[index]:
                if not raw and self._pressed_at[index] is not None:
                    if time.ticks_diff(now, self._pressed_at[index]) >= LONG_PRESS_MS:
                        if not self._long_pressing[index]:
                            self._long_pressing[index] = True
                            print("Long press CH{}".format(index))
                continue

            if time.ticks_diff(now, self._changed_at[index]) < BUTTON_DEBOUNCE_MS:
                continue

            self._stable[index] = raw
            if not raw:
                self._pressed_at[index] = now
                continue

            if self._pressed_at[index] is not None:
                duration = time.ticks_diff(now, self._pressed_at[index])
                is_long_press = self._long_pressing[index] or duration >= LONG_PRESS_MS
                self._pressed_at[index] = None
                self._long_pressing[index] = False
                self.callback(index, is_long_press)

    def long_pressing(self):
        return any(self._long_pressing)


class WifiServer:
    def __init__(self, servos, leds, sessions):
        self.servos = servos
        self.leds = leds
        self.sessions = sessions
        self.sock = None
        self.discovery = DiscoveryResponder(
            socket,
            ubinascii.hexlify(unique_id()).decode(),
            SERVER_PORT,
            DISCOVERY_PORT,
        )
        self.running = False

    def start(self):
        if self.running:
            return True
        self.leds.set_mode(LedDeck.FAST)
        if not self._connect_ap():
            print("Wi-Fi start failed")
            self.leds.set_mode(LedDeck.NORMAL)
            return False

        try:
            self.sock = socket.socket()
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind(("0.0.0.0", SERVER_PORT))
            self.sock.listen(8)
            self.sock.settimeout(0)
        except Exception as exc:
            print("TCP server start failed:", exc)
            if self.sock:
                try:
                    self.sock.close()
                except Exception:
                    pass
                self.sock = None
            self.discovery.stop()
            self.leds.set_mode(LedDeck.NORMAL)
            return False
        self.running = True
        self.leds.set_mode(LedDeck.BLINK)

        if not self.discovery.start():
            print("UDP discovery unavailable; TCP control remains available")

        ip = network.WLAN(network.STA_IF).ifconfig()[0]
        print("Server listening on {}:{}".format(ip, SERVER_PORT))
        return True

    def stop(self):
        if not self.running:
            return False
        self.running = False
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None
        self.discovery.stop()
        self.sessions.clear()
        self.leds.set_claimed(())
        self.leds.set_mode(LedDeck.NORMAL)
        print("Server stopped")
        return True

    def poll(self):
        if not self.running:
            return

        self.discovery.poll()
        self.leds.set_claimed(self.sessions.locked_channels())

        # Keep the cooperative servo/LED loop responsive even when several
        # desktop clients poll the controller at once.
        for _ in range(8):
            try:
                conn, _addr = self.sock.accept()
            except OSError:
                break

            try:
                command = self._readline(conn)
                self._handle(command, conn)
            except Exception as exc:
                print("Server error:", exc)
                try:
                    conn.write(b"ERROR\n")
                except Exception:
                    pass
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

    def _readline(self, conn, max_length=1024):
        conn.settimeout(0.05)
        started = time.ticks_ms()
        buffer = bytearray()
        while len(buffer) < max_length:
            if time.ticks_diff(time.ticks_ms(), started) >= COMMAND_READ_TIMEOUT_MS:
                return ""
            try:
                chunk = conn.recv(1)
            except OSError:
                self.servos.tick()
                self.leds.tick()
                if time.ticks_diff(time.ticks_ms(), started) >= COMMAND_READ_TIMEOUT_MS:
                    break
                continue
            if not chunk:
                return ""
            if chunk == b"\n":
                break
            buffer += chunk
        # Commands are line framed. Never operate on a truncated request.
        if len(buffer) >= max_length:
            return ""
        return bytes(buffer).decode().strip()

    def _connect_ap(self):
        if not SSID or not PASSWORD:
            print("Wi-Fi config missing. Upload wifi_config.py with SSID and PASSWORD.")
            return False

        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)

        if not wlan.isconnected():
            print("Connecting Wi-Fi...")
            wlan.connect(SSID, PASSWORD)
            started = time.ticks_ms()
            while not wlan.isconnected():
                if time.ticks_diff(time.ticks_ms(), started) > 10_000:
                    print("Wi-Fi timeout")
                    return False
                self.servos.tick()
                self.leds.tick()
                time.sleep(0.3)

        if USE_STATIC_IP:
            wlan.ifconfig(STATIC_IFCONFIG)

        print("Wi-Fi", wlan.ifconfig())
        return True

    def _handle(self, command, conn):
        if command.startswith("SESSION "):
            try:
                body = json.loads(command[8:])
            except Exception:
                body = None
            result = self.sessions.request(body, self._session_operate)
            self.leds.set_claimed(self.sessions.locked_channels())
            conn.write(json.dumps(result).encode() + b"\n")
            return

        command = command.upper()
        parts = command.split()
        if not parts:
            conn.write(b"UNKNOWN\n")
            return

        operation = parts[0]
        # MicroPython stream.write completes a blocking write; send may be short.
        if operation == "STATE" and len(parts) == 1:
            conn.write(self.servos.state_text().encode() + b"\n")
            return

        if operation == "STATUS":
            conn.write(self.servos.status_text().encode() + b"\n")
            return

        if operation not in ("OPEN", "CLOSE", "TOGGLE") or len(parts) != 2:
            conn.write(b"UNKNOWN\n")
            return

        try:
            channel = int(parts[1])
        except ValueError:
            conn.write(b"ERR\n")
            return

        if self.sessions.is_locked(channel):
            conn.write(b"LOCKED\n")
            return
        if operation == "OPEN":
            ok = self.servos.open(channel)
        elif operation == "CLOSE":
            ok = self.servos.close(channel)
        else:
            ok = self.servos.toggle(channel)

        if ok:
            self.leds.reflect()
            conn.write(b"OK\n")
        else:
            conn.write(b"ERR\n")

    def _session_operate(self, action, channels):
        for channel in channels:
            if action == "open":
                ok = self.servos.open(channel)
            elif action == "close":
                ok = self.servos.close(channel)
            else:
                ok = self.servos.toggle(channel)
            if not ok:
                return False
        self.leds.reflect()
        return True


i2c = I2C(I2C_BUS, sda=Pin(I2C_SDA_PIN), scl=Pin(I2C_SCL_PIN), freq=I2C_FREQ)
pwm = PCA9685(i2c, address=PCA9685_ADDRESS, angle_offset=PCA9685_ANGLE_OFFSET)
servos = ServoBoard(
    CHANNELS,
    pwm,
    time.ticks_ms,
    time.ticks_diff,
    step_degrees=SERVO_STEP_DEGREES,
    step_interval_ms=SERVO_STEP_INTERVAL_MS,
    release_delay_ms=SERVO_RELEASE_DELAY_MS,
    max_active=SERVO_MAX_ACTIVE,
    release_pwm=SERVO_RELEASE_PWM,
)
leds = LedDeck(CHANNELS, servos)
device_id = ubinascii.hexlify(unique_id()).decode()
device_label = DeviceLabel(DEVICE_LABEL)
sessions = Sessions(
    CHANNELS,
    device_id,
    device_label.value,
    time.ticks_ms,
    time.ticks_diff,
    device_label.save,
)
server = WifiServer(servos, leds, sessions)
leds.reflect()


def on_button(channel, is_long_press):
    if is_long_press:
        if server.running:
            server.stop()
        else:
            server.start()
        return

    if not sessions.is_locked(channel):
        servos.toggle(channel)
        leds.reflect()


buttons = ButtonDeck(CHANNELS, on_button)
print("Hold any switch for 3s to start/stop server. Short press toggles a channel.")


def sync_led_mode():
    if buttons.long_pressing():
        leds.set_mode(LedDeck.FAST)
    elif server.running:
        leds.set_mode(LedDeck.BLINK)
    else:
        leds.set_mode(LedDeck.NORMAL)


if AUTO_START_SERVER:
    server.start()

while True:
    buttons.poll()
    servos.tick()
    leds.reflect()
    sync_led_mode()
    leds.tick()
    server.poll()
    time.sleep(0.02)
