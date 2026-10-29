"""Channel leases and a small, Pico-friendly session protocol.

The controller is the authority for ownership.  Desktop applications only keep
an opaque token and renew it while their window remains connected.
"""

try:
    import ujson as json
except ImportError:  # CPython tests and newer MicroPython builds
    import json


LEASE_MS = 15_000


def valid_label(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 32:
        return False
    # MicroPython omits str.isprintable; use only its supported ord/encode APIs.
    for character in value:
        code = ord(character)
        if (
            code < 32
            or 127 <= code <= 159
            or 0xD800 <= code <= 0xDFFF
            or code in (0x2028, 0x2029)
        ):
            return False
    return len(value.encode("utf-8")) <= 96


def valid_token(value):
    return (
        isinstance(value, str)
        and len(value) == 32
        and all(character in "0123456789abcdef" for character in value)
    )


class DeviceLabel:
    """Persist only the human label; calibration remains in settings.py."""

    def __init__(self, default, path="device_config.json", os_module=None):
        self.default = default
        self.path = path
        if os_module is None:
            try:
                import uos as os_module
            except ImportError:
                import os as os_module
        self.os = os_module
        self.value = self._load()

    def _load(self):
        try:
            with open(self.path, "r") as stream:
                value = json.loads(stream.read()).get("label")
            return value if valid_label(value) else self.default
        except Exception:
            return self.default

    def save(self, value):
        if not valid_label(value):
            raise ValueError("invalid_request")
        temporary = self.path + ".tmp"
        try:
            with open(temporary, "w") as stream:
                # MicroPython's ujson consistently exposes dumps/loads, while
                # dump is not available in every firmware build.
                stream.write(json.dumps({"label": value}))
            self.os.rename(temporary, self.path)
        except Exception as error:
            try:
                self.os.remove(temporary)
            except Exception:  # noqa: S110 - cleanup must not hide storage failure
                pass
            raise OSError("storage") from error
        self.value = value


class Sessions:
    def __init__(self, channels, device_id, label, ticks_ms, ticks_diff, save_label):
        self.channels = channels
        self.device_id = device_id
        self.label = label
        self.ticks_ms = ticks_ms
        self.ticks_diff = ticks_diff
        self.save_label = save_label
        self.claims = {}
        self.owners = {}

    def _reply(self, error=None, **values):
        result = {"ok": error is None}
        if error is not None:
            result["error"] = error
        result.update(values)
        return result

    def _expire(self):
        now = self.ticks_ms()
        expired = [
            token
            for token, owner in self.owners.items()
            if self.ticks_diff(now, owner["seen"]) >= LEASE_MS
        ]
        for token in expired:
            self._release(token)

    def _release(self, token):
        owner = self.owners.pop(token, None)
        if owner is not None:
            for channel in owner["channels"]:
                if self.claims.get(channel) == token:
                    del self.claims[channel]

    def clear(self):
        self.claims.clear()
        self.owners.clear()

    def locked_channels(self):
        self._expire()
        return set(self.claims)

    def is_locked(self, channel):
        self._expire()
        return channel in self.claims

    def info(self):
        self._expire()
        return self._reply(
            protocol=2,
            device_id=self.device_id,
            label=self.label,
            lease_ms=LEASE_MS,
            channels=[
                {
                    "id": index,
                    "label": channel["label"],
                    "locked": index in self.claims,
                }
                for index, channel in enumerate(self.channels)
            ],
        )

    def _channels(self, value):
        if not isinstance(value, list) or not value:
            return None
        if any(
            not isinstance(channel, int) or isinstance(channel, bool)
            for channel in value
        ):
            return None
        if len(set(value)) != len(value) or any(
            channel < 0 or channel >= len(self.channels) for channel in value
        ):
            return None
        return tuple(sorted(value))

    def _owner(self, token):
        self._expire()
        return self.owners.get(token)

    def claim(self, token, channels):
        selected = self._channels(channels)
        if not valid_token(token) or selected is None:
            return self._reply("invalid_request")
        owner = self._owner(token)
        if owner is not None:
            if owner["channels"] != selected:
                return self._reply("invalid_request")
            owner["seen"] = self.ticks_ms()
            return self._reply(channels=list(selected), lease_ms=LEASE_MS)
        if any(channel in self.claims for channel in selected):
            return self._reply("busy")
        now = self.ticks_ms()
        self.owners[token] = {"channels": selected, "seen": now}
        for channel in selected:
            self.claims[channel] = token
        return self._reply(channels=list(selected), lease_ms=LEASE_MS)

    def renew(self, token):
        if not valid_token(token):
            return self._reply("invalid_request")
        owner = self._owner(token)
        if owner is None:
            return self._reply("lease_lost")
        owner["seen"] = self.ticks_ms()
        return self._reply(channels=list(owner["channels"]), lease_ms=LEASE_MS)

    def release(self, token):
        if not valid_token(token):
            return self._reply("invalid_request")
        self._expire()
        self._release(token)
        return self._reply()

    def operate(self, token, action, channels, callback):
        selected = self._channels(channels)
        if (
            not valid_token(token)
            or selected is None
            or action not in ("open", "close", "toggle")
        ):
            return self._reply("invalid_request")
        owner = self._owner(token)
        if owner is None or any(
            self.claims.get(channel) != token for channel in selected
        ):
            return self._reply("lease_lost")
        # Validate ownership for the entire action before moving anything.
        if not callback(action, selected):
            return self._reply("invalid_request")
        owner["seen"] = self.ticks_ms()
        return self._reply()

    def request(self, body, callback=None):
        if not isinstance(body, dict):
            return self._reply("invalid_request")
        operation = body.get("op")
        if operation == "info":
            return self.info()
        if operation == "claim":
            return self.claim(body.get("token"), body.get("channels"))
        if operation == "renew":
            return self.renew(body.get("token"))
        if operation == "release":
            return self.release(body.get("token"))
        if operation == "operate":
            if callback is None:
                return self._reply("invalid_request")
            return self.operate(
                body.get("token"), body.get("action"), body.get("channels"), callback
            )
        if operation == "set_label":
            self._expire()
            label = body.get("label")
            if self.claims or not valid_label(label):
                return self._reply("busy" if self.claims else "invalid_request")
            try:
                self.save_label(label)
            except Exception:
                return self._reply("storage")
            self.label = label
            return self._reply(label=label)
        return self._reply("invalid_request")
