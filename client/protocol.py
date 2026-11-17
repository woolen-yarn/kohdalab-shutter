from collections.abc import Mapping
from dataclasses import dataclass


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


@dataclass(frozen=True)
class ChannelState:
    """One firmware ``STATE`` field: commanded position and calibration."""

    position: int
    target: int
    close_angle: int
    open_angle: int
    busy: bool


def parse_state(raw_state: str) -> dict[int, ChannelState]:
    """Parse ``CHn=position/target/close/open/busy`` fields from ``STATE``."""
    if not isinstance(raw_state, str) or not raw_state.strip():
        raise ProtocolError("Empty STATE response")

    channels = {}
    for token in raw_state.split(","):
        token = token.strip()
        left, separator, right = token.partition("=")
        left = left.strip().upper()
        fields = right.split("/")
        if not separator or not left.startswith("CH") or len(fields) != 5:
            raise ProtocolError("Malformed STATE field: {!r}".format(token))
        try:
            channel = int(left[2:])
            position, target, close_angle, open_angle, busy = map(int, fields)
        except ValueError:
            raise ProtocolError("Invalid STATE field: {!r}".format(token)) from None
        angles = (position, target, close_angle, open_angle)
        if channel < 0 or busy not in (0, 1) or not all(0 <= a <= 180 for a in angles):
            raise ProtocolError("STATE value out of range: {!r}".format(token))
        if channel in channels:
            raise ProtocolError("Duplicate channel in STATE: CH{}".format(channel))
        channels[channel] = ChannelState(*angles, busy=bool(busy))
    return channels


def state_name(state: ChannelState | None) -> str:
    """Name a channel by its own calibration; old firmware is Unknown."""
    if state is None:
        return "UNKNOWN"
    if state.busy or state.target != state.position:
        return "MOVING"
    if state.position == state.close_angle:
        return "CLOSE"
    if state.position == state.open_angle:
        return "OPEN"
    return "UNKNOWN"


def format_status(channels: Mapping[int, int]) -> str:
    return ", ".join(
        "CH{}={}".format(channel, channels[channel]) for channel in sorted(channels)
    )
