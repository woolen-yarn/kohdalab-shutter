from machine import I2C, Pin
from pca9685 import PCA9685
from settings import (
    AUTO_START_SERVER,
    CHANNELS,
    I2C_BUS,
    I2C_FREQ,
    I2C_SCL_PIN,
    I2C_SDA_PIN,
    LONG_PRESS_MS,
    PCA9685_ADDRESS,
    PCA9685_ANGLE_OFFSET,
    SERVER_PORT,
    STATIC_IFCONFIG,
    USE_STATIC_IP,
)
import network
import socket
import time

try:
    from wifi_config import SSID, PASSWORD
except ImportError:
    SSID = ""
    PASSWORD = ""


class ServoBoard:
    def __init__(self, channels):
        self.channels = channels
        i2c = I2C(I2C_BUS, sda=Pin(I2C_SDA_PIN), scl=Pin(I2C_SCL_PIN), freq=I2C_FREQ)
        self._pwm = PCA9685(i2c, address=PCA9685_ADDRESS, angle_offset=PCA9685_ANGLE_OFFSET)
        self.angles = [channel["close"] for channel in channels]
        self.update_all()

    def count(self):
        return len(self.channels)

    def valid_channel(self, index):
        return 0 <= index < self.count()

    def close_angle(self, index):
        return self.channels[index]["close"]

    def open_angle(self, index):
        return self.channels[index]["open"]

    def set(self, index, angle):
        if not self.valid_channel(index):
            return False
        self.angles[index] = angle
        self._pwm.set_servo_angle(self.channels[index]["servo"], angle)
        return True

    def open(self, index):
        return self.set(index, self.open_angle(index))

    def close(self, index):
        return self.set(index, self.close_angle(index))

    def toggle(self, index):
        if not self.valid_channel(index):
            return False
        if self.angles[index] == self.close_angle(index):
            return self.open(index)
        return self.close(index)

    def update_all(self):
        for index, angle in enumerate(self.angles):
            self._pwm.set_servo_angle(self.channels[index]["servo"], angle)

    def status_text(self):
        return ",".join("CH{}={}".format(index, angle) for index, angle in enumerate(self.angles))


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

    def reflect(self):
        if self.mode != self.NORMAL:
            return
        for index, angle in enumerate(self.servos.angles):
            self.red[index].value(1 if angle == self.servos.close_angle(index) else 0)
            self.green[index].value(1 if angle == self.servos.open_angle(index) else 0)

    def set_mode(self, mode):
        if self.mode == mode:
            if mode == self.NORMAL:
                self.reflect()
            return

        self.mode = mode
        self._phase = False
        self._last_ms = time.ticks_ms()
        if mode == self.NORMAL:
            self.reflect()

    def tick(self):
        if self.mode == self.NORMAL:
            return

        now = time.ticks_ms()
        interval = 60 if self.mode == self.FAST else 250
        if time.ticks_diff(now, self._last_ms) < interval:
            return

        self._phase = not self._phase
        self._last_ms = now

        if self.mode == self.FAST:
            for red, green in zip(self.red, self.green):
                red.value(self._phase)
                green.value(self._phase)
            return

        for index, angle in enumerate(self.servos.angles):
            if angle == self.servos.open_angle(index):
                self.green[index].value(self._phase)
                self.red[index].value(0)
            else:
                self.red[index].value(self._phase)
                self.green[index].value(0)


class ButtonDeck:
    def __init__(self, channels, callback):
        self.switches = [Pin(channel["switch"], Pin.IN, Pin.PULL_UP) for channel in channels]
        self._pressed_at = [None] * len(channels)
        self._long_pressing = [False] * len(channels)
        self.callback = callback

    def poll(self):
        now = time.ticks_ms()
        for index, pin in enumerate(self.switches):
            if not pin.value():
                if self._pressed_at[index] is None:
                    self._pressed_at[index] = now
                elif not self._long_pressing[index]:
                    if time.ticks_diff(now, self._pressed_at[index]) >= LONG_PRESS_MS:
                        self._long_pressing[index] = True
                        print("Long press CH{}".format(index))
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
    def __init__(self, servos, leds):
        self.servos = servos
        self.leds = leds
        self.sock = None
        self.running = False

    def start(self):
        if self.running:
            return True
        self.leds.set_mode(LedDeck.FAST)
        if not self._connect_ap():
            print("Wi-Fi start failed")
            self.leds.set_mode(LedDeck.NORMAL)
            return False

        self.sock = socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("0.0.0.0", SERVER_PORT))
        self.sock.listen(8)
        self.sock.settimeout(0)
        self.running = True
        self.leds.set_mode(LedDeck.BLINK)

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
        self.leds.set_mode(LedDeck.NORMAL)
        print("Server stopped")
        return True

    def poll(self):
        if not self.running:
            return

        while True:
            try:
                conn, _addr = self.sock.accept()
            except OSError:
                break

            try:
                command = self._readline(conn).upper()
                self._handle(command, conn)
            except Exception as exc:
                print("Server error:", exc)
                try:
                    conn.send(b"ERROR\n")
                except Exception:
                    pass
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

    def _readline(self, conn, max_length=256):
        conn.settimeout(5)
        buffer = bytearray()
        while len(buffer) < max_length:
            try:
                chunk = conn.recv(1)
            except OSError:
                break
            if not chunk or chunk == b"\n":
                break
            buffer += chunk
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
                self.leds.tick()
                time.sleep(0.3)

        if USE_STATIC_IP:
            wlan.ifconfig(STATIC_IFCONFIG)

        print("Wi-Fi", wlan.ifconfig())
        return True

    def _handle(self, command, conn):
        parts = command.split()
        if not parts:
            conn.send(b"UNKNOWN\n")
            return

        operation = parts[0]
        if operation == "STATUS":
            conn.send(self.servos.status_text().encode() + b"\n")
            return

        if operation not in ("OPEN", "CLOSE", "TOGGLE") or len(parts) != 2:
            conn.send(b"UNKNOWN\n")
            return

        try:
            channel = int(parts[1])
        except ValueError:
            conn.send(b"ERR\n")
            return

        if operation == "OPEN":
            ok = self.servos.open(channel)
        elif operation == "CLOSE":
            ok = self.servos.close(channel)
        else:
            ok = self.servos.toggle(channel)

        if ok:
            self.leds.reflect()
            conn.send(b"OK\n")
        else:
            conn.send(b"ERR\n")


servos = ServoBoard(CHANNELS)
leds = LedDeck(CHANNELS, servos)
server = WifiServer(servos, leds)
leds.reflect()


def on_button(channel, is_long_press):
    if is_long_press:
        if server.running:
            server.stop()
        else:
            server.start()
        return

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
    sync_led_mode()
    leds.tick()
    server.poll()
    time.sleep(0.02)
