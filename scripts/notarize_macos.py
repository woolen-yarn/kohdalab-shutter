"""Create Developer ID signed/notarized Mac candidates using a prepared keychain.

No certificate, private key or account password is accepted by this script. The
protected workflow prepares an ephemeral keychain and named notary profile.
"""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import plistlib
import re
import stat
import subprocess
import tempfile
import zipfile

APP = "KohdaLab Shutter.app"
BINARIES = ("kohdalab-shutter", "kohdalab-shutter-gui")


def run(*args):
    result = subprocess.run(args, capture_output=True, text=True, check=False)  # noqa: S603 - fixed system tools and validated paths; no secret values
    if result.returncode:
        raise RuntimeError(
            f"{args[0]} failed ({result.returncode}): {result.stderr.strip()}"
        )
    return result


def unpack_app(archive, destination, version):
    """Extract only the known app, rejecting traversal and app-internal symlinks."""
    prefix = PurePosixPath(f"kohdalab-shutter-{version}-macos-universal") / APP
    app = destination / APP
    if app.exists():
        raise FileExistsError(f"Refusing to replace {app}")
    with zipfile.ZipFile(archive) as package:
        for entry in package.infolist():
            path = PurePosixPath(entry.filename)
            if path.is_absolute() or ".." in path.parts or "\\" in entry.filename:
                raise ValueError("Unsafe path in Mac archive")
            if not path.is_relative_to(prefix):
                continue  # Ignore the outer Applications link and resource-fork copies.
            relative = path.relative_to(prefix)
            mode = entry.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise ValueError("App-internal symlinks are not expected")
            target = app / Path(*relative.parts)
            if entry.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(package.read(entry))
                target.chmod(0o755 if mode & 0o111 else 0o644)
    info = plistlib.loads((app / "Contents/Info.plist").read_bytes())
    if (
        info.get("CFBundleIdentifier") != "jp.kohdalab.shutter"
        or info.get("CFBundleShortVersionString") != version
        or info.get("CFBundleExecutable") != "kohdalab-shutter-gui"
    ):
        raise ValueError("Unexpected Mac bundle identity or version")
    for name in BINARIES:
        if not (app / "Contents/MacOS" / name).is_file():
            raise ValueError(f"Missing first-party executable: {name}")
    return app


def require_identity(display, team):
    flags = re.search(r"flags=0x([0-9a-fA-F]+)", display)
    if (
        f"TeamIdentifier={team}" not in display.splitlines()
        or "Authority=Developer ID Application:" not in display
        or "Timestamp=" not in display
        or flags is None
        or not int(flags.group(1), 16) & 0x10000
    ):
        raise RuntimeError(
            "Expected timestamped Developer ID hardened-runtime signature"
        )


def notarize(path, profile, keychain):
    result = run(
        "xcrun",
        "notarytool",
        "submit",
        str(path),
        "--keychain-profile",
        profile,
        "--keychain",
        str(keychain),
        "--wait",
        "--timeout",
        "30m",
        "--output-format",
        "json",
    )
    receipt = json.loads(result.stdout)
    if receipt.get("status") != "Accepted" or not receipt.get("id"):
        raise RuntimeError(
            f"Apple notarization was not accepted: {receipt.get('status')}; submission {receipt.get('id')}"
        )
    return {"id": receipt["id"], "status": receipt["status"]}


def sign_and_notarize(archive, version, identity, team, profile, keychain, output):
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("A stable three-component release version is required")
    if not re.fullmatch(r"[A-Fa-f0-9]{40}", identity):
        raise ValueError(
            "Use the SHA-1 identity fingerprint, not an ambiguous certificate name"
        )
    if not re.fullmatch(r"[A-Z0-9]{10}", team):
        raise ValueError("Invalid Apple Team ID")
    output.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="shutter-notary-") as directory:
        work = Path(directory)
        stage = work / f"kohdalab-shutter-{version}-macos-universal-signed"
        stage.mkdir()
        app = unpack_app(archive, stage, version)
        for name in BINARIES:
            run(
                "lipo",
                str(app / "Contents/MacOS" / name),
                "-verify_arch",
                "arm64",
                "x86_64",
            )
        for path in (app / "Contents/MacOS/kohdalab-shutter", app):
            run(
                "codesign",
                "--force",
                "--timestamp",
                "--options",
                "runtime",
                "--keychain",
                str(keychain),
                "--sign",
                identity,
                str(path),
            )
        run("codesign", "--verify", "--deep", "--strict", str(app))
        for path in (app / "Contents/MacOS/kohdalab-shutter", app):
            result = run("codesign", "--display", "--verbose=4", str(path))
            require_identity(result.stderr + result.stdout, team)
        submission = work / "notary-input.zip"
        run("ditto", "-c", "-k", "--keepParent", str(app), str(submission))
        app_receipt = notarize(submission, profile, keychain)
        run("xcrun", "stapler", "staple", str(app))
        run("xcrun", "stapler", "validate", str(app))
        run("spctl", "--assess", "--type", "execute", "--verbose=4", str(app))
        (stage / "Applications").symlink_to("/Applications", target_is_directory=True)
        (stage / "README.txt").write_text(
            "KohdaLab Shutter " + version + "\n\n"
            "Drag KohdaLab Shutter.app to Applications.\n"
            "Developer ID signed, timestamped, hardened runtime enabled, and notarized by Apple.\n"
            "No Rust or Python installation is required.\n"
            "Licenses and dependency notices are inside the app's Contents/Resources.\n",
            encoding="utf-8",
        )
        name = f"kohdalab-shutter-{version}-macos-universal-signed"
        dmg = output / f"{name}.dmg"
        run(
            "hdiutil",
            "create",
            "-volname",
            "KohdaLab Shutter",
            "-srcfolder",
            str(stage),
            "-format",
            "UDZO",
            str(dmg),
        )
        run(
            "codesign",
            "--timestamp",
            "--keychain",
            str(keychain),
            "--sign",
            identity,
            str(dmg),
        )
        run("codesign", "--verify", "--strict", str(dmg))
        dmg_receipt = notarize(dmg, profile, keychain)
        run("xcrun", "stapler", "staple", str(dmg))
        run("xcrun", "stapler", "validate", str(dmg))
        run(
            "spctl",
            "--assess",
            "--type",
            "open",
            "--context",
            "context:primary-signature",
            "--verbose=4",
            str(dmg),
        )
        run("hdiutil", "verify", str(dmg))
        run(
            "ditto",
            "-c",
            "-k",
            "--sequesterRsrc",
            "--keepParent",
            str(stage),
            str(output / f"{name}.zip"),
        )
        report = {
            "version": version,
            "signing": "Developer ID Application",
            "identity_sha1": identity.upper(),
            "team_id": team,
            "app_notarization": app_receipt,
            "dmg_notarization": dmg_receipt,
            "stapled": True,
            "assets": {
                p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(output.iterdir())
                if p.suffix in (".zip", ".dmg")
            },
        }
        (output / "SIGNING-macos.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
        (output / "SHA256SUMS-macos-signed.txt").write_text(
            "".join(f"{digest}  {name}\n" for name, digest in report["assets"].items()),
            encoding="utf-8",
        )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--identity", required=True)
    parser.add_argument("--team-id", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--keychain", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = sign_and_notarize(
        args.archive,
        args.version,
        args.identity,
        args.team_id,
        args.profile,
        args.keychain,
        args.output,
    )
    print(json.dumps(report))


if __name__ == "__main__":
    main()
