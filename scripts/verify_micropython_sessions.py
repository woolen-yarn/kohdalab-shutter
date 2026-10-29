"""Run production Pico session code under MicroPython Unix.

Run from the repository root with a MicroPython interpreter.  This intentionally
uses only APIs available on the Pico W firmware.
"""

import os
import sys

sys.path.insert(0, "server")

from sessions import DeviceLabel, LEASE_MS, Sessions, valid_label  # noqa: E402


class Clock:
    def __init__(self):
        self.now = 0

    def ticks_ms(self):
        return self.now

    @staticmethod
    def ticks_diff(now, then):
        # Same signed-wrap shape as MicroPython time.ticks_diff.
        return ((now - then + (1 << 29)) % (1 << 30)) - (1 << 29)


def remove_if_present(path):
    try:
        os.remove(path)
    except OSError:
        pass


def require(value, message):
    if not value:
        raise RuntimeError(message)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "micropython-session-label-test.json"
    remove_if_present(path)
    remove_if_present(path + ".tmp")
    try:
        require(valid_label("偏光シャッター A"), "Japanese label was rejected")
        require(not valid_label("bad\nlabel"), "control label was accepted")
        label = DeviceLabel("Default", path)
        require(label.value == "Default", "default label was not used")
        label.save("レーザー入口")
        require(
            DeviceLabel("Default", path).value == "レーザー入口",
            "label did not persist",
        )

        clock = Clock()
        writes = []
        channels = [{"label": "Input"}, {"label": "Output"}, {"label": "Probe"}]
        first = "1" * 32
        second = "2" * 32
        manager = Sessions(
            channels,
            "abc123",
            label.value,
            clock.ticks_ms,
            clock.ticks_diff,
            label.save,
        )
        require(
            manager.request({"op": "info"})["label"] == "レーザー入口", "info label"
        )
        require(manager.claim(first, [0])["ok"], "first claim")
        require(manager.claim(second, [0])["error"] == "busy", "overlap claim")
        require(manager.claim(second, [1])["ok"], "independent claim")
        require(
            manager.operate(
                first,
                "open",
                [0],
                lambda action, selected: writes.append((action, selected)) or True,
            )["ok"],
            "owned operation",
        )
        require(writes == [("open", (0,))], "operation callback")
        require(manager.release(first)["ok"], "release")
        require(manager.claim(second, [1])["ok"], "same lease retry")

        # Lease expiry across the signed ticks counter wrap releases only its CH.
        manager.clear()
        clock.now = (1 << 30) - 10
        require(manager.claim(first, [2])["ok"], "wrap claim")
        clock.now = LEASE_MS - 1000
        require(manager.claim(second, [1])["ok"], "later wrap claim")
        clock.now = LEASE_MS
        require(not manager.is_locked(2), "wrapped lease did not expire")
        require(manager.is_locked(1), "other lease was released")
    finally:
        remove_if_present(path)
        remove_if_present(path + ".tmp")
    print("Pico session runtime verification passed under", sys.implementation.name)


main()
