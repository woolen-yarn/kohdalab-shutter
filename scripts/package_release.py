"""Package native desktop binaries; no Python runtime is shipped or required."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import plistlib
import shutil
import struct
import subprocess
import sys
import tomllib
import zipfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
APP = "KohdaLab Shutter"
BINARIES = ("kohdalab-shutter-gui", "kohdalab-shutter")


def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True)  # noqa: S603 - fixed local build tools/paths


def version():
    return tomllib.loads((ROOT / "Cargo.toml").read_text(encoding="utf-8"))["package"][
        "version"
    ]


def icon_png(size):
    """Draw the same front-facing light window as the GUI, using only stdlib."""
    rows = bytearray()
    for y in range(size):
        rows.append(0)
        for x in range(size):
            dx, dy = (x + 0.5) / size - 0.5, (y + 0.5) / size - 0.5
            r = math.hypot(dx, dy)
            color = (18, 19, 23, 255)
            if r < 0.36:
                color = (56, 58, 67, 255)
            if r < 0.32:
                color = (26, 27, 32, 255)
            if r < 0.25:
                color = (27, 46, 45, 255)
            if r < 0.18:
                color = (31, 69, 65, 255)
            if r < 0.12:
                color = (63, 215, 194, 255)
            if r < 0.32 and abs(dx) > 0.28:
                color = (74, 77, 88, 255)
            rows.extend(color)

    def chunk(name, data):
        return (
            struct.pack(">I", len(data))
            + name
            + data
            + struct.pack(">I", zlib.crc32(name + data))
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


def add_notices(destination, metadata):
    packages = json.loads(metadata.read_text(encoding="utf-8"))["packages"]
    notice_root = destination / "licenses"
    notice_root.mkdir()
    entries = []
    for package in sorted(packages, key=lambda item: (item["name"], item["version"])):
        name = f"{package['name']}-{package['version']}"
        entries.append(
            f"{name}\nLicense: {package.get('license') or 'See included license files'}\n{package.get('repository') or ''}\n"
        )
        if package.get("source") is None:
            continue  # The project's own MIT license is already included.
        source = Path(package["manifest_path"]).parent
        # Font licenses are nested in epaint_default_fonts/fonts.
        candidates = [
            p
            for p in source.rglob("*")
            if p.is_file()
            and (
                p.name.upper().startswith(("LICENSE", "COPYING", "NOTICE"))
                or p.name
                in (
                    "OFL.txt",
                    "UFL.txt",
                    "Hack-Regular.txt",
                    "emoji-icon-font-mit-license.txt",
                )
            )
        ]
        license_file = package.get("license_file")
        if license_file:
            candidates.append(source / license_file)
        for path in sorted(set(candidates)):
            relative = path.relative_to(source)
            target = notice_root / name / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    (destination / "THIRD-PARTY-NOTICES.txt").write_text(
        "\n".join(entries), encoding="utf-8"
    )


def write_readme(destination, platform):
    instructions = (
        "Extract this entire ZIP, then double-click kohdalab-shutter-gui.exe.\n"
        "Demo.cmd opens the simulated interface without connecting hardware.\n"
        if platform == "windows-x64"
        else "Drag KohdaLab Shutter.app to Applications, then open it.\n"
        "Apple Silicon and Intel are supported on macOS 13 or later.\n"
    )
    (destination / "README.txt").write_text(
        f"{APP} {version()}\n\n{instructions}\n"
        "Rust and Python are not needed to run this desktop app.\n"
        "Start the Pico W server, select Find Pico W, choose your controller and Connect.\n"
        "Pico W firmware still uses MicroPython; its initial upload is a separate step.\n"
        "States are commanded positions, not measured optical transmission.\n\n"
        "This distribution is not publisher-signed or Apple-notarized.\n"
        "Windows or macOS may show an unknown-publisher warning. See the installation guide.\n\n"
        "Documentation: https://github.com/woolen-yarn/kohdalab-shutter/blob/main/docs/install.md\n"
        "Source and license: https://github.com/woolen-yarn/kohdalab-shutter\n",
        encoding="utf-8",
    )
    shutil.copy2(ROOT / "LICENSE", destination / "LICENSE")


def package(platform, binaries, output, metadata):
    output.mkdir(parents=True, exist_ok=True)
    name = f"kohdalab-shutter-{version()}-{platform}"
    stage = output / name
    if stage.exists():
        raise FileExistsError(
            f"Refusing to replace existing staging directory: {stage}"
        )
    stage.mkdir()
    suffix = ".exe" if platform == "windows-x64" else ""
    for binary in BINARIES:
        source = binaries / (binary + suffix)
        if not source.is_file() or not source.stat().st_size:
            raise FileNotFoundError(f"Missing native binary: {source}")
    write_readme(stage, platform)
    if platform == "windows-x64":
        for binary in BINARIES:
            shutil.copy2(binaries / (binary + suffix), stage)
        (stage / "Demo.cmd").write_bytes(
            b'@echo off\r\nstart "" "%~dp0kohdalab-shutter-gui.exe" --demo\r\n'
        )
        add_notices(stage, metadata)
        smoke = stage / "kohdalab-shutter.exe"
    else:
        app = stage / f"{APP}.app"
        contents = app / "Contents"
        executable = contents / "MacOS"
        resources = contents / "Resources"
        executable.mkdir(parents=True)
        resources.mkdir()
        for binary in BINARIES:
            target = executable / binary
            shutil.copy2(binaries / binary, target)
            target.chmod(0o755)
            run("lipo", "-verify_arch", "arm64", "x86_64", str(target))
        info = {
            "CFBundleName": APP,
            "CFBundleDisplayName": APP,
            "CFBundleIdentifier": "jp.kohdalab.shutter",
            "CFBundleExecutable": "kohdalab-shutter-gui",
            "CFBundlePackageType": "APPL",
            "CFBundleShortVersionString": version(),
            "CFBundleVersion": version(),
            "CFBundleIconFile": "Shutter.icns",
            "LSMinimumSystemVersion": "13.0",
            "NSHighResolutionCapable": True,
            "NSLocalNetworkUsageDescription": "Find and control Pico W optical shutters on your local network.",
        }
        with (contents / "Info.plist").open("wb") as handle:
            plistlib.dump(info, handle)
        iconset = output / "Shutter.iconset"
        iconset.mkdir()
        for points in (16, 32, 128, 256, 512):
            for scale in (1, 2):
                tail = "@2x" if scale == 2 else ""
                (iconset / f"icon_{points}x{points}{tail}.png").write_bytes(
                    icon_png(points * scale)
                )
        run(
            "iconutil",
            "-c",
            "icns",
            str(iconset),
            "-o",
            str(resources / "Shutter.icns"),
        )
        shutil.rmtree(iconset)
        add_notices(resources, metadata)
        shutil.copy2(stage / "LICENSE", resources)
        for binary in BINARIES:
            run("codesign", "--force", "--sign", "-", str(executable / binary))
        run("codesign", "--force", "--sign", "-", str(app))
        run("codesign", "--verify", "--deep", "--strict", str(app))
        smoke = executable / "kohdalab-shutter"
        (stage / "Applications").symlink_to("/Applications", target_is_directory=True)
        run(
            "hdiutil",
            "create",
            "-volname",
            APP,
            "-srcfolder",
            str(stage),
            "-ov",
            "-format",
            "UDZO",
            str(output / f"{name}.dmg"),
        )
        run("hdiutil", "verify", str(output / f"{name}.dmg"))
    if not run(str(smoke.resolve()), "--version").stdout.strip().endswith(version()):
        raise RuntimeError("Packaged CLI version did not match Cargo.toml")
    run(str(smoke.resolve()), "--help")
    gui = (
        stage / "kohdalab-shutter-gui.exe"
        if platform == "windows-x64"
        else executable / "kohdalab-shutter-gui"
    )
    run(str(gui.resolve()), "--help")
    archive = output / f"{name}.zip"
    if platform == "macos-universal":
        # ditto preserves app executable permissions, symlinks and bundle metadata.
        run(
            "ditto",
            "-c",
            "-k",
            "--sequesterRsrc",
            "--keepParent",
            str(stage),
            str(archive),
        )
    else:
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as handle:
            for file in sorted(stage.rglob("*")):
                if file.is_file():
                    handle.write(file, file.relative_to(output))
    (output / f"BUILD-{platform}.json").write_text(
        json.dumps(
            {
                "version": version(),
                "platform": platform,
                "commit": run("git", "rev-parse", "HEAD").stdout.strip(),
                "assets": {
                    p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in sorted(output.glob(f"{name}.*"))
                    if p.suffix in (".zip", ".dmg")
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return archive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--platform", choices=("windows-x64", "macos-universal"), required=True
    )
    parser.add_argument("--binaries", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("dist"))
    args = parser.parse_args()
    if sys.platform != ("win32" if args.platform == "windows-x64" else "darwin"):
        parser.error("Run the packager on the matching native operating system")
    print(package(args.platform, args.binaries, args.output, args.metadata))


if __name__ == "__main__":
    main()
