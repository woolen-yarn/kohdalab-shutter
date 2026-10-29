"""Validate the files users receive, independently of native build tooling."""

import importlib.util
import json
from pathlib import Path
import struct
import zipfile
from unittest.mock import patch

import pytest

SPEC = importlib.util.spec_from_file_location(
    "release_package",
    Path(__file__).resolve().parents[1] / "scripts/package_release.py",
)
assert SPEC is not None and SPEC.loader is not None
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


def test_icon_is_a_valid_rgba_png():
    image = release.icon_png(32)
    assert image[:8] == b"\x89PNG\r\n\x1a\n"
    assert struct.unpack(">IIBBBBB", image[16:29]) == (32, 32, 8, 6, 0, 0, 0)


def test_windows_archive_contains_launchers_and_licenses(tmp_path):
    binaries = tmp_path / "binaries"
    binaries.mkdir()
    for name in release.BINARIES:
        (binaries / (name + ".exe")).write_bytes(b"fake-native-binary")
    crate = tmp_path / "crate"
    (crate / "fonts").mkdir(parents=True)
    (crate / "LICENSE-MIT").write_text("Test license")
    (crate / "fonts/OFL.txt").write_text("Test font license")
    metadata = tmp_path / "metadata.json"
    metadata.write_text(
        json.dumps(
            {
                "packages": [
                    {
                        "name": "test-dependency",
                        "version": "1.0.0",
                        "license": "MIT",
                        "source": "registry+test",
                        "manifest_path": str(crate / "Cargo.toml"),
                    },
                    {
                        "name": "project",
                        "version": "1.0.0",
                        "source": None,
                        "manifest_path": str(tmp_path / "Cargo.toml"),
                    },
                ]
            }
        )
    )
    result = type("Result", (), {"stdout": release.version()})()
    with patch.object(release, "run", return_value=result):
        archive = release.package("windows-x64", binaries, tmp_path / "dist", metadata)
    base = archive.stem
    with zipfile.ZipFile(archive) as handle:
        paths = set(handle.namelist())
        assert f"{base}/kohdalab-shutter-gui.exe" in paths
        assert f"{base}/kohdalab-shutter.exe" in paths
        assert f"{base}/LICENSE" in paths
        assert f"{base}/licenses/test-dependency-1.0.0/LICENSE-MIT" in paths
        assert f"{base}/licenses/test-dependency-1.0.0/fonts/OFL.txt" in paths
        assert b"%~dp0kohdalab-shutter-gui.exe" in handle.read(f"{base}/Demo.cmd")
        assert not any("wifi_config.py" in p for p in paths)
    report = json.loads((archive.parent / "BUILD-windows-x64.json").read_text())
    assert (
        report["assets"][archive.name]
        == release.hashlib.sha256(archive.read_bytes()).hexdigest()
    )


def test_packaging_rejects_missing_binaries_and_existing_output(tmp_path):
    with pytest.raises(FileNotFoundError, match="Missing native binary"):
        release.package(
            "windows-x64", tmp_path, tmp_path / "dist", tmp_path / "missing.json"
        )
    with pytest.raises(FileExistsError, match="Refusing to replace"):
        release.package(
            "windows-x64", tmp_path, tmp_path / "dist", tmp_path / "missing.json"
        )
