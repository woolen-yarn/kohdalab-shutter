from collections.abc import Mapping


DEFAULT_HOST = "10.32.145.232"
DEFAULT_PORT = 12345
ENCODING = "utf-8"
LINE_ENDING = b"\n"


class ProtocolError(ValueError):
    """Raised when the Pico returns a malformed or rejected response."""


def parse_status(raw_status: str) -> dict[int, int]:
    if not isinstance(raw_status, str) or not raw_status.strip():
        raise ProtocolError("Empty STATUS response")

    channels = {}
    for token in raw_status.split(","):
        token = token.strip()
        if not token or "=" not in token:
            raise ProtocolError("Malformed STATUS field: {!r}".format(token))
        left, right = token.split("=", 1)
        left = left.strip().upper()
        if not left.startswith("CH"):
            raise ProtocolError("Invalid channel name: {!r}".format(left))
        try:
            channel = int(left[2:])
            angle = int(right.strip())
        except ValueError:
            raise ProtocolError("Invalid STATUS field: {!r}".format(token)) from None
        if channel < 0 or not 0 <= angle <= 180:
            raise ProtocolError("STATUS value out of range: {!r}".format(token))
        if channel in channels:
            raise ProtocolError("Duplicate channel in STATUS: CH{}".format(channel))
        channels[channel] = angle
    return channels


def format_status(channels: Mapping[int, int]) -> str:
    return ", ".join(
        "CH{}={}".format(channel, channels[channel]) for channel in sorted(channels)
    )
