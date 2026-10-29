"""Local validation for notarization fail-closed checks; never contacts Apple."""

import importlib.util
import json
from pathlib import Path
import plistlib
import stat
from unittest.mock import patch
import zipfile

import pytest

SPEC = importlib.util.spec_from_file_location(
    "notarize_macos", Path(__file__).resolve().parents[1] / "scripts/notarize_macos.py"
)
assert SPEC and SPEC.loader
notary = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(notary)


def test_only_timestamped_developer_id_with_hardened_runtime_is_accepted():
    valid = (
        "flags=0x10000(runtime)\nAuthority=Developer ID Application: Test\n"
        "TeamIdentifier=ABCDE12345\nTimestamp=Oct 29, 2026\n"
    )
    notary.require_identity(valid, "ABCDE12345")
    for bad in (
        valid.replace("ABCDE12345", "WRONG12345"),
        valid.replace("Authority=Developer ID Application: Test", "Signature=adhoc"),
        valid.replace("flags=0x10000(runtime)", "flags=0x0(none)"),
        valid.replace("Timestamp=Oct 29, 2026", ""),
    ):
        with pytest.raises(RuntimeError, match="Developer ID"):
            notary.require_identity(bad, "ABCDE12345")


def test_rejected_notarization_is_never_treated_as_accepted():
    for status in ("Invalid", "Rejected", "In Progress"):
        result = type(
            "Result", (), {"stdout": json.dumps({"status": status, "id": "test-id"})}
        )()
        with patch.object(notary, "run", return_value=result):
            with pytest.raises(RuntimeError, match="not accepted"):
                notary.notarize(Path("test.zip"), "profile", Path("keychain"))


def test_app_extraction_preserves_executable_permissions_and_ignores_outer_link(
    tmp_path,
):
    archive = tmp_path / "app.zip"
    prefix = "kohdalab-shutter-0.4.1-macos-universal/KohdaLab Shutter.app/"
    with zipfile.ZipFile(archive, "w") as package:
        package.writestr(
            prefix + "Contents/Info.plist",
            plistlib.dumps(
                {
                    "CFBundleIdentifier": "jp.kohdalab.shutter",
                    "CFBundleShortVersionString": "0.4.1",
                    "CFBundleExecutable": "kohdalab-shutter-gui",
                }
            ),
        )
        for name in notary.BINARIES:
            info = zipfile.ZipInfo(prefix + "Contents/MacOS/" + name)
            info.external_attr = (stat.S_IFREG | 0o755) << 16
            package.writestr(info, b"test")
        package.writestr("kohdalab-shutter-0.4.1-macos-universal/README.txt", "ignored")
    result = notary.unpack_app(archive, tmp_path / "unpacked", "0.4.1")
    assert (result / "Contents/MacOS/kohdalab-shutter").stat().st_mode & 0o111
    assert not (tmp_path / "unpacked/README.txt").exists()


def test_archive_traversal_and_app_symlinks_are_rejected(tmp_path):
    for i, name in enumerate(
        (
            "../escape",
            "/absolute",
            "kohdalab-shutter-0.4.1-macos-universal/KohdaLab Shutter.app/evil",
        )
    ):
        archive = tmp_path / f"bad-{i}.zip"
        with zipfile.ZipFile(archive, "w") as package:
            info = zipfile.ZipInfo(name)
            if i == 2:
                info.external_attr = (stat.S_IFLNK | 0o777) << 16
            package.writestr(info, "/outside")
        with pytest.raises(ValueError):
            notary.unpack_app(archive, tmp_path / f"unpack-{i}", "0.4.1")
