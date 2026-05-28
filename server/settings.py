SERVER_PORT = 12345
LONG_PRESS_MS = 3000
AUTO_START_SERVER = False

USE_STATIC_IP = True
STATIC_IFCONFIG = (
    "10.32.145.232",  # ip
    "255.255.255.0",  # netmask
    "10.32.145.1",    # gateway
    "130.34.40.53",   # dns
)

I2C_BUS = 0
I2C_SDA_PIN = 16
I2C_SCL_PIN = 17
I2C_FREQ = 400_000
PCA9685_ADDRESS = 0x40
PCA9685_ANGLE_OFFSET = 0

# Add or remove entries here to build a different number of channels.
# servo is the PCA9685 channel number. switch/red/green are Pico GPIO numbers.
CHANNELS = (
    {"label": "CH00", "servo": 0, "switch": 2, "green": 3, "red": 4, "close": 0, "open": 90},
    {"label": "CH01", "servo": 1, "switch": 5, "green": 6, "red": 7, "close": 0, "open": 90},
    {"label": "CH02", "servo": 2, "switch": 8, "green": 9, "red": 10, "close": 0, "open": 90},
    {"label": "CH03", "servo": 3, "switch": 11, "green": 12, "red": 13, "close": 0, "open": 90},
)
