DEFAULT_HOST = "10.32.145.232"
DEFAULT_PORT = 12345
ENCODING = "utf-8"
LINE_ENDING = b"\n"


def parse_status(raw_status):
    channels = {}
    for token in raw_status.split(","):
        token = token.strip()
        if not token or "=" not in token:
            continue
        left, right = token.split("=", 1)
        left = left.strip().upper()
        if not left.startswith("CH"):
            continue
        try:
            channels[int(left[2:])] = int(right.strip())
        except ValueError:
            continue
    return channels


def format_status(channels):
    return ", ".join("CH{}={}".format(channel, channels[channel]) for channel in sorted(channels))
