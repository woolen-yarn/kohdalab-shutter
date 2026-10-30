"""Build the native standalone GUI. No network or USB access during app smoke."""

import argparse
import hashlib
from importlib.metadata import distribution, version
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
NAME = "KohdaLab Pico Setup"


def call(*args):
    subprocess.run(list(args), check=True, cwd=ROOT)  # noqa: S603 - fixed build commands


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--platform", required=True, choices=("windows-x64", "macos-arm64", "macos-x64")
    )
    args = parser.parse_args()
    stage = ROOT / "build/pico-setup/licenses"
    stage.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROOT / "packaging/pico-setup/licenses", stage, dirs_exist_ok=True)
    shutil.copy(ROOT / "LICENSE", stage / "KohdaLab-MIT.txt")
    python_license = (
        Path(sys.base_prefix)
        / f"lib/python{sys.version_info.major}.{sys.version_info.minor}/LICENSE.txt"
    )
    if not python_license.exists():
        python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if not python_license.exists():
        raise RuntimeError("Python runtime license missing")
    shutil.copy(python_license, stage / "Python-LICENSE.txt")
    dependencies = (
        "mpremote",
        "pyserial",
        "PySide6_Essentials",
        "shiboken6",
        "pyinstaller",
    )
    for name in dependencies:
        dist = distribution(name)
        for item in dist.files or []:
            if item.name.lower().startswith(("license", "copying", "notice")):
                source = Path(dist.locate_file(item))
                if source.is_file():
                    shutil.copy(source, stage / (name + "-" + item.name))
    data = []
    for name in (
        "pca9685.py",
        "servo.py",
        "discovery.py",
        "sessions.py",
        "settings.py",
        "main.py",
    ):
        data += ["--add-data", str(ROOT / "server" / name) + os.pathsep + "server"]
    data += ["--add-data", str(stage) + os.pathsep + "licenses"]
    call(
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--onedir",
        "--name",
        NAME,
        "--distpath",
        "dist/pico-setup",
        "--workpath",
        "build/pico-setup/pyinstaller",
        "--specpath",
        "build/pico-setup",
        "--paths",
        str(ROOT),
        "--hidden-import",
        "mpremote.main",
        "--collect-submodules",
        "mpremote",
        "--hidden-import",
        "serial.tools.list_ports",
        *data,
        "scripts/pico_setup_entry.py",
    )
    output = ROOT / "dist/pico-setup"
    if sys.platform == "darwin":
        app = output / (NAME + ".app")
        binary = app / "Contents/MacOS" / NAME
        call("codesign", "--verify", "--deep", "--strict", str(app))
        call(str(binary), "--smoke-test")
    else:
        app = output / NAME
        binary = app / (NAME + ".exe")
        call(str(binary), "--smoke-test")
    archive_base = output / f"kohdalab-pico-setup-1.0.0-{args.platform}"
    if sys.platform == "darwin":
        archive = Path(str(archive_base) + ".zip")
        call(
            "ditto",
            "-c",
            "-k",
            "--sequesterRsrc",
            "--keepParent",
            str(app),
            str(archive),
        )
    else:
        archive = Path(
            shutil.make_archive(str(archive_base), "zip", app.parent, app.name)
        )
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("git is required to record build provenance")
    commit = subprocess.check_output(  # noqa: S603 - fixed git arguments
        [git, "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    report = {
        "version": "1.0.0",
        "platform": args.platform,
        "commit": commit,
        "python": platform.python_version(),
        "dependencies": {name: version(name) for name in dependencies},
        "asset": archive.name,
        "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "smoke": "passed; demo/backend version only; no USB opened",
        "signing": "ad-hoc; not notarized" if sys.platform == "darwin" else "unsigned",
    }
    (output / f"BUILD-{args.platform}.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report))


if __name__ == "__main__":
    main()
