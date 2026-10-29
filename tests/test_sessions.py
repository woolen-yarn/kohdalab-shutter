from server.sessions import DeviceLabel, LEASE_MS, Sessions, valid_label, valid_token


class Clock:
    def __init__(self):
        self.now = 0

    def ticks_ms(self):
        return self.now

    @staticmethod
    def ticks_diff(now, then):
        return now - then


CHANNELS = [{"label": "Input"}, {"label": "Output"}, {"label": "Probe"}]
ONE = "1" * 32
TWO = "2" * 32


def sessions():
    clock = Clock()
    saved = []
    value = {"label": "Bench A"}

    def save(label):
        saved.append(label)
        value["label"] = label

    manager = Sessions(
        CHANNELS, "abc123", value["label"], clock.ticks_ms, clock.ticks_diff, save
    )
    return manager, clock, saved


def test_info_claim_is_atomic_and_idempotent():
    manager, _clock, _saved = sessions()
    info = manager.request({"op": "info"})
    assert info["protocol"] == 2
    assert info["label"] == "Bench A"
    assert not any(channel["locked"] for channel in info["channels"])
    assert manager.request({"op": "claim", "token": ONE, "channels": [0, 1]})["ok"]
    assert manager.request({"op": "claim", "token": ONE, "channels": [1, 0]})["ok"]
    assert (
        manager.request({"op": "claim", "token": ONE, "channels": [2]})["error"]
        == "invalid_request"
    )
    assert (
        manager.request({"op": "claim", "token": TWO, "channels": [1, 2]})["error"]
        == "busy"
    )
    assert manager.request({"op": "claim", "token": TWO, "channels": [2]})["ok"]
    assert manager.locked_channels() == {0, 1, 2}


def test_expiry_renew_and_release():
    manager, clock, _saved = sessions()
    assert manager.claim(ONE, [0])["ok"]
    clock.now = LEASE_MS - 1
    assert manager.renew(ONE)["ok"]
    clock.now += LEASE_MS - 1
    assert manager.is_locked(0)
    clock.now += 1
    assert not manager.is_locked(0)
    assert manager.renew(ONE)["error"] == "lease_lost"
    assert manager.release(ONE)["ok"]
    assert manager.claim(TWO, [0])["ok"]


def test_operate_requires_every_selected_channel_and_only_then_calls_callback():
    manager, _clock, _saved = sessions()
    calls = []
    assert manager.claim(ONE, [0])["ok"]
    result = manager.request(
        {"op": "operate", "token": ONE, "action": "open", "channels": [0, 1]},
        lambda action, channels: calls.append((action, channels)) or True,
    )
    assert result["error"] == "lease_lost"
    assert calls == []
    assert manager.request(
        {"op": "operate", "token": ONE, "action": "open", "channels": [0]},
        lambda action, channels: calls.append((action, channels)) or True,
    )["ok"]
    assert calls == [("open", (0,))]


def test_label_only_changes_when_free_and_is_persisted():
    manager, _clock, saved = sessions()
    assert manager.request({"op": "set_label", "label": "Line 2"}) == {
        "ok": True,
        "label": "Line 2",
    }
    assert saved == ["Line 2"]
    assert manager.claim(ONE, [0])["ok"]
    assert manager.request({"op": "set_label", "label": "Busy"})["error"] == "busy"
    assert manager.release(ONE)["ok"]
    assert (
        manager.request({"op": "set_label", "label": "bad\nlabel"})["error"]
        == "invalid_request"
    )


def test_inputs_are_tightly_validated():
    manager, _clock, _saved = sessions()
    assert valid_token(ONE) and not valid_token("A" * 32)
    assert valid_label("A label")
    assert valid_label("偏光シャッター A")
    assert not valid_label("\t")
    assert not valid_label("line\nbreak")
    assert not valid_label("bad\ud800surrogate")
    assert not valid_label("あ" * 33)
    assert not valid_label("😀" * 32)  # 32 printable characters but 128 UTF-8 bytes.
    for request in (
        {"op": "claim", "token": ONE, "channels": []},
        {"op": "claim", "token": ONE, "channels": [0, 0]},
        {"op": "claim", "token": ONE, "channels": [9]},
        {"op": "operate", "token": ONE, "action": "move", "channels": [0]},
        {"op": "other"},
        None,
    ):
        assert manager.request(request)["error"] == "invalid_request"


def test_device_label_is_persisted_and_invalid_file_falls_back(tmp_path):
    path = tmp_path / "device_config.json"
    label = DeviceLabel("Default", str(path))
    assert label.value == "Default"
    label.save("Optics line")
    assert DeviceLabel("Default", str(path)).value == "Optics line"
    path.write_text('{"label":"bad\\nlabel"}', encoding="utf-8")
    assert DeviceLabel("Default", str(path)).value == "Default"


def test_storage_failures_and_remaining_session_rejections(tmp_path):
    class BrokenOs:
        def rename(self, _temporary, _path):
            raise OSError("full")

        def remove(self, _temporary):
            raise OSError("already gone")

    path = tmp_path / "device_config.json"
    broken = DeviceLabel("Default", str(path), BrokenOs())
    try:
        broken.save("Saved")
    except OSError as error:
        assert str(error) == "storage"
    else:
        raise AssertionError("storage error was accepted")
    try:
        broken.save("\n")
    except ValueError as error:
        assert str(error) == "invalid_request"
    else:
        raise AssertionError("invalid label was accepted")

    manager, _clock, _saved = sessions()
    assert manager.renew("bad")["error"] == "invalid_request"
    assert manager.release("bad")["error"] == "invalid_request"
    assert manager.request({"op": "renew", "token": ONE})["error"] == "lease_lost"
    assert manager.request({"op": "release", "token": ONE})["ok"]
    assert manager.request({"op": "operate"})["error"] == "invalid_request"
    assert (
        manager.operate(ONE, "move", [0], lambda _action, _channels: True)["error"]
        == "invalid_request"
    )
    assert manager.claim(ONE, [0])["ok"]
    assert (
        manager.operate(ONE, "open", [0], lambda _action, _channels: False)["error"]
        == "invalid_request"
    )
    manager.claims[0] = TWO
    manager._release(ONE)
    assert manager.claims[0] == TWO
    manager.clear()
    assert manager.locked_channels() == set()

    def storage_failure(_label):
        raise OSError("full")

    failing = Sessions(
        CHANNELS,
        "id",
        "Bench",
        lambda: 0,
        lambda now, then: now - then,
        storage_failure,
    )
    assert failing.request({"op": "set_label", "label": "New"})["error"] == "storage"
    assert (
        manager.request({"op": "claim", "token": ONE, "channels": [True]})["error"]
        == "invalid_request"
    )


def test_label_validation_uses_micropython_supported_string_operations():
    for value in ("Bench A", "測定台A", "échantillon"):
        assert valid_label(value)
    for value in ("bad\x7f", "bad\x9f", "bad\u2028line", "bad\u2029line"):
        assert not valid_label(value)
