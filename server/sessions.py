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


def _canonical_channel_id(value):
    """Return a non-negative, canonical decimal channel id or None."""
    if not isinstance(value, str) or not value:
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    if number < 0 or str(number) != value:
        return None
    return number


class DeviceLabel:
    """Persist human-readable device and channel labels outside settings.py."""

    def __init__(self, default, path="device_config.json", os_module=None):
        self.default = default
        self.path = path
        if os_module is None:
            try:
                import uos as os_module
            except ImportError:
                import os as os_module
        self.os = os_module
        self._config = self._load()
        value = self._config.get("label")
        self.value = value if valid_label(value) else self.default

    def _load(self):
        try:
            with open(self.path, "r") as stream:
                config = json.loads(stream.read())
            return config if isinstance(config, dict) else {}
        except Exception:
            return {}

    @property
    def channel_labels(self):
        """Return valid saved labels; leave unrelated stored config untouched."""
        labels = self._config.get("channel_labels")
        if not isinstance(labels, dict):
            return {}
        result = {}
        for channel, label in labels.items():
            if _canonical_channel_id(channel) is not None and valid_label(label):
                result[channel] = label
        return result

    def _write(self, config):
        temporary = self.path + ".tmp"
        try:
            with open(temporary, "w") as stream:
                # MicroPython's ujson consistently exposes dumps/loads, while
                # dump is not available in every firmware build.
                stream.write(json.dumps(config))
            # Pico/MicroPython exposes rename; Windows CPython needs replace
            # for an atomic overwrite of an existing file.
            getattr(self.os, "replace", self.os.rename)(temporary, self.path)
        except Exception as error:
            try:
                self.os.remove(temporary)
            except Exception:  # noqa: S110 - cleanup must not hide storage failure
                pass
            raise OSError("storage") from error

    def save_config(self, patch):
        """Atomically merge a label patch while preserving unrelated settings."""
        if not isinstance(patch, dict) or not patch:
            raise ValueError("invalid_request")
        if any(key not in ("label", "channel_labels") for key in patch):
            raise ValueError("invalid_request")
        if "label" in patch and not valid_label(patch["label"]):
            raise ValueError("invalid_request")
        channel_patch = patch.get("channel_labels")
        if channel_patch is not None:
            if not isinstance(channel_patch, dict):
                raise ValueError("invalid_request")
            for channel, label in channel_patch.items():
                if _canonical_channel_id(channel) is None or not valid_label(label):
                    raise ValueError("invalid_request")

        config = {}
        for key, value in self._config.items():
            config[key] = value
        if "label" in patch:
            config["label"] = patch["label"]
        if channel_patch is not None:
            previous = config.get("channel_labels")
            labels = {}
            if isinstance(previous, dict):
                for channel, label in previous.items():
                    labels[channel] = label
            for channel, label in channel_patch.items():
                labels[channel] = label
            config["channel_labels"] = labels

        self._write(config)
        self._config = config
        if "label" in patch:
            self.value = patch["label"]

    def save(self, value):
        self.save_config({"label": value})


class Sessions:
    def __init__(
        self,
        channels,
        device_id,
        label,
        ticks_ms,
        ticks_diff,
        save_label,
        config_store=None,
    ):
        self.channels = channels
        self.device_id = device_id
        self.label = label
        self.ticks_ms = ticks_ms
        self.ticks_diff = ticks_diff
        self.save_label = save_label
        self.config_store = config_store
        self.channel_labels = (
            config_store.channel_labels if config_store is not None else {}
        )
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
                    "label": self.channel_labels.get(str(index), channel["label"]),
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

    def set_config(self, token, label, channel_labels):
        if not valid_token(token):
            return self._reply("invalid_request")
        owner = self._owner(token)
        if owner is None:
            return self._reply("lease_lost")
        if label is None and channel_labels is None:
            return self._reply("invalid_request")

        patch = {}
        if label is not None:
            if not valid_label(label):
                return self._reply("invalid_request")
            patch["label"] = label
        if channel_labels is not None:
            if not isinstance(channel_labels, dict):
                return self._reply("invalid_request")
            for channel, value in channel_labels.items():
                channel_id = _canonical_channel_id(channel)
                if (
                    channel_id is None
                    or channel_id >= len(self.channels)
                    or channel_id not in owner["channels"]
                    or not valid_label(value)
                ):
                    return self._reply("invalid_request")
            if channel_labels:
                patch["channel_labels"] = channel_labels
            elif not patch:
                return self._reply("invalid_request")

        try:
            if self.config_store is not None:
                self.config_store.save_config(patch)
            elif "channel_labels" in patch:
                return self._reply("storage")
            else:
                self.save_label(label)
        except Exception:
            return self._reply("storage")

        if "label" in patch:
            self.label = label
        if "channel_labels" in patch:
            labels = {}
            for channel, value in self.channel_labels.items():
                labels[channel] = value
            for channel, value in channel_labels.items():
                labels[channel] = value
            self.channel_labels = labels
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
                if self.config_store is None:
                    self.save_label(label)
                else:
                    self.config_store.save_config({"label": label})
            except Exception:
                return self._reply("storage")
            self.label = label
            return self._reply(label=label)
        if operation == "set_config":
            return self.set_config(
                body.get("token"), body.get("label"), body.get("channel_labels")
            )
        return self._reply("invalid_request")
