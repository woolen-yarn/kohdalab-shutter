"""Interactive USB installer/updater. Run via the root .bat/.command launchers."""

from __future__ import annotations

import argparse
import ast
from datetime import datetime
import getpass
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ("pca9685.py", "servo.py", "discovery.py", "sessions.py", "main.py")
PRESERVED = ("settings.py", "wifi_config.py", "device_config.json")
DHCP_MARKER = (
    "\n# USB uploader: use automatic IP addressing (DHCP).\nUSE_STATIC_IP = False\n"
)


def patch_settings(existing: bytes, defaults: str) -> bytes:
    """Keep calibration/pins/custom code; add missing compatibility constants only."""
    text = existing.decode("utf-8").replace(DHCP_MARKER, "")
    tree = ast.parse(text)
    names: set[str] = set()

    class SettingsNames(ast.NodeVisitor):
        def visit_Name(self, node: ast.Name) -> None:
            if isinstance(node.ctx, ast.Store):
                names.add(node.id)

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            names.add(node.name)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            names.add(node.name)

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            names.add(node.name)

        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
            names.update(alias.asname or alias.name for alias in node.names)

    SettingsNames().visit(tree)
    if "CHANNELS" not in names:
        raise RuntimeError(
            "Existing settings has no CHANNELS mapping. Keep its backup and adapt calibration/wiring before updating."
        )
    additions = []
    for statement in ast.parse(defaults).body:
        if isinstance(statement, ast.Assign) and all(
            isinstance(t, ast.Name) for t in statement.targets
        ):
            targets = {t.id for t in statement.targets}
            if targets.isdisjoint(names):
                additions.append(ast.get_source_segment(defaults, statement))
    if additions:
        text = (
            text.rstrip()
            + "\n\n# Compatibility defaults added by the USB updater.\n"
            + "\n".join(additions)
            + "\n"
        )
    return (text.rstrip() + DHCP_MARKER).encode("utf-8")


def run_mpremote(arguments: list[str]) -> str:
    """Keep USB calls isolated; a bundled windowed app uses a private result file."""
    with tempfile.TemporaryDirectory(prefix="shutter-remote-") as directory:
        output = Path(directory) / "output.txt"
        frozen = getattr(sys, "frozen", False)
        command = (
            [sys.executable, "--mpremote", str(output)]
            if frozen
            else [sys.executable, "-m", "mpremote"]
        )
        try:
            result = subprocess.run(  # noqa: S603 - argument list; no shell
                [*command, *arguments],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=90,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW
                if sys.platform == "win32"
                else 0,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise RuntimeError(
                "USB operation failed/timed out. Close Thonny and check the cable; backups are retained."
            ) from error
        if result.returncode:
            raise RuntimeError(
                "Pico USB operation failed. Check MicroPython, free space and the USB connection. Backups are retained."
            )
        return (output.read_text(encoding="utf-8") if frozen else result.stdout).strip()


class Pico:
    def __init__(self, port: str) -> None:
        self.port = port

    def command(self, *arguments: str) -> str:
        return run_mpremote(["connect", self.port, *arguments])

    def run(self, source: str) -> str:
        with tempfile.TemporaryDirectory(prefix="shutter-usb-") as directory:
            path = Path(directory) / "operation.py"
            path.write_text(source, encoding="utf-8")
            return self.command("run", str(path))

    def read(self, names: tuple[str, ...]) -> dict[str, bytes]:
        output = self.run(
            """import os, json, ubinascii
print(json.dumps({'machine': os.uname().machine}))
for name in """
            + repr(names)
            + """:
    try:
        with open(name, 'rb') as f:
            value = ubinascii.hexlify(f.read()).decode()
        print(json.dumps({'name': name, 'data': value}))
        del value
    except OSError as e:
        if e.args[0] != 2:
            raise
"""
        )
        try:
            lines = output.splitlines()
            if "Pico W" not in json.loads(lines[0])["machine"]:
                raise RuntimeError(
                    "This installer requires Raspberry Pi Pico W MicroPython."
                )
            files = {}
            for line in lines[1:]:
                record = json.loads(line)
                name = record["name"]
                if name not in names or name in files:
                    raise ValueError("Unexpected file")
                files[name] = bytes.fromhex(record["data"])
            return files
        except (IndexError, KeyError, ValueError, TypeError) as error:
            raise RuntimeError(
                "Could not read valid Pico W files; no originals are committed by this read."
            ) from error

    def install(self, files: dict[str, bytes]) -> None:
        # Stage all files, verify exact bytes, then compile on MicroPython without
        # executing imports or touching GPIO. main.py is committed last.
        with tempfile.TemporaryDirectory(prefix="shutter-usb-") as directory:
            for name, contents in files.items():
                local = Path(directory) / name
                local.write_bytes(contents)
                self.command("fs", "cp", str(local), ":" + name + ".shutter-upload")
        staged = tuple(name + ".shutter-upload" for name in files)
        actual = self.read(staged)
        if any(
            actual.get(name + ".shutter-upload") != contents
            for name, contents in files.items()
        ):
            raise RuntimeError(
                "Upload verification failed. Original files are unchanged; run the updater again."
            )
        order = [name for name in files if name != "main.py"] + ["main.py"]
        self.run(
            """import os
names = """
            + repr(order)
            + """
for name in names:
    with open(name + '.shutter-upload') as f:
        compile(f.read(), name, 'exec')
original = {}
for name in names:
    try:
        with open(name, 'rb') as f:
            original[name] = f.read()
    except OSError as e:
        if e.args[0] != 2:
            raise
        original[name] = None
changed = []
try:
    for name in names:
        os.rename(name + '.shutter-upload', name)
        changed.append(name)
except Exception:
    for name in reversed(changed):
        if original[name] is None:
            os.remove(name)
        else:
            with open(name + '.shutter-rollback', 'wb') as f:
                f.write(original[name])
            os.rename(name + '.shutter-rollback', name)
    raise
print('Installed')
"""
        )
        self.command("reset")


def backup(files: dict[str, bytes], root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    directory = Path(
        tempfile.mkdtemp(prefix=datetime.now().strftime("%Y%m%d-%H%M%S-"), dir=root)
    )
    for name, contents in files.items():
        path = directory / name
        with path.open("xb") as stream:
            os.chmod(path, 0o600)
            stream.write(contents)
    return directory


def plan(
    mode: str,
    current: dict[str, bytes],
    server: Path,
    ssid: str | None = None,
    password: str | None = None,
) -> dict[str, bytes]:
    if mode == "initial" and any(name in current for name in PRESERVED + ("main.py",)):
        raise RuntimeError(
            "This Pico already has files. Choose Update to preserve its settings."
        )
    if mode == "update" and (
        "settings.py" not in current or "wifi_config.py" not in current
    ):
        raise RuntimeError(
            "Update requires existing settings.py and wifi_config.py. Restore them from a backup before updating."
        )
    defaults = (server / "settings.py").read_text(encoding="utf-8")
    settings = patch_settings(current.get("settings.py", defaults.encode()), defaults)
    files = {
        name: (server / name).read_bytes() for name in PROGRAMS if name != "main.py"
    }
    files["settings.py"] = settings
    if mode == "initial":
        if not ssid or not password:
            raise RuntimeError(
                "Wi-Fi name and password are required for initial setup."
            )
        files["wifi_config.py"] = (
            "SSID = " + ascii(ssid) + "\nPASSWORD = " + ascii(password) + "\n"
        ).encode()
    files["main.py"] = (server / "main.py").read_bytes()
    return files


def choose_port(explicit: str | None) -> str:
    if explicit:
        return explicit
    from serial.tools import list_ports

    ports = sorted(
        (port for port in list_ports.comports() if port.vid == 0x2E8A),
        key=lambda port: port.device,
    )
    if not ports:
        raise RuntimeError(
            "No USB Pico found. Use a data cable and install Pico W MicroPython first (see docs/pico-upload.md)."
        )
    for number, port in enumerate(ports, 1):
        print(
            f"{number}. {port.device} — {port.description} — {port.serial_number or 'no USB ID'}"
        )
    if len(ports) == 1:
        return ports[0].device
    answer = input("Select Pico number (blank cancels): ").strip()
    if not answer.isdigit() or not 1 <= int(answer) <= len(ports):
        raise RuntimeError("Cancelled; no Pico files changed.")
    return ports[int(answer) - 1].device


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pico W initial setup / update with automatic IP (DHCP)"
    )
    parser.add_argument("--mode", choices=("initial", "update"))
    parser.add_argument(
        "--port", help="Explicit USB serial port, e.g. COM4 or /dev/cu.usbmodem..."
    )
    parser.add_argument(
        "--backup-dir",
        type=Path,
        default=Path.home() / ".kohdalab" / "shutter" / "pico-backups",
    )
    args = parser.parse_args()
    try:
        print(
            "KohdaLab Shutter — Pico W USB setup\nClose all shutter GUIs and Thonny. Connect only the Pico you intend to update.\nMicroPython must already be installed. Calibration/wiring must match this device."
        )
        mode = args.mode
        if mode is None:
            answer = input(
                "1. Initial setup (new Pico)\n2. Update (keep existing settings)\nChoose 1 or 2 (blank cancels): "
            ).strip()
            if answer not in ("1", "2"):
                return 0
            mode = "initial" if answer == "1" else "update"
        pico = Pico(choose_port(args.port))
        current = pico.read(PROGRAMS + PRESERVED)
        destination = backup(current, args.backup_dir)
        print(
            f"Backup saved: {destination}\nContains private Wi-Fi settings; do not share this folder."
        )
        ssid = password = None
        if mode == "initial":
            if any(name in current for name in PRESERVED + ("main.py",)):
                raise RuntimeError(
                    "This Pico already has files. Choose Update instead."
                )
            ssid = input("Wi-Fi name (SSID): ").strip()
            password = getpass.getpass("Wi-Fi password (hidden): ")
        files = plan(mode, current, ROOT / "server", ssid, password)
        print(f"USB device: {pico.port}\nMode: {mode} — IP: automatic (DHCP)")
        if input("Upload and restart this Pico? [y/N]: ").strip().lower() != "y":
            print(
                "Cancelled. Original Pico files are unchanged; restart it to resume its program."
            )
            return 0
        pico.install(files)
        print(
            "Complete. Hold a CH switch for 3 seconds to start Wi-Fi, then use Find Pico W in the GUI.\nIf AUTO_START_SERVER is enabled, Wi-Fi starts automatically. No IP entry is needed."
        )
        return 0
    except (RuntimeError, OSError, SyntaxError, UnicodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    except (KeyboardInterrupt, EOFError):
        print(
            "\nCancelled. If interrupted during upload, run Update again before using the device.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
