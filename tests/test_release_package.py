"""Validate the files users receive, independently of native build tooling."""

import importlib.util
import json
import os
from pathlib import Path
import struct
import subprocess
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


def test_run_includes_captured_diagnostics_on_failure(monkeypatch):
    error = subprocess.CalledProcessError(
        9, ("tool", "argument"), output="tool output", stderr="tool error"
    )
    monkeypatch.setattr(
        release.subprocess, "run", lambda *args, **kwargs: (_ for _ in ()).throw(error)
    )
    with pytest.raises(RuntimeError, match="tool output") as caught:
        release.run("tool", "argument")
    assert "tool error" in str(caught.value)


def test_windows_archive_contains_launchers_and_licenses(tmp_path):
    binaries = tmp_path / "binaries"
    binaries.mkdir()
    for name in release.BINARIES:
        (binaries / (name + ".exe")).write_bytes(b"fake-native-binary")
    crate = tmp_path / "crate"
    (crate / "fonts").mkdir(parents=True)
    (crate / "LICENSE-MIT").write_text("Test license")
    (crate / "fonts/OFL.txt").write_text("Test font license")
    # Registry archives can preserve timestamps predating the ZIP epoch.
    os.utime(crate / "LICENSE-MIT", (0, 0))
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

    def fake_setup(stage, output):
        path = output / f"{stage.name}-Setup.exe"
        path.write_bytes(b"test-installer")
        return path

    with (
        patch.object(release, "run", return_value=result),
        patch.object(release, "build_windows_setup", side_effect=fake_setup),
    ):
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
    setup = archive.with_name(f"{archive.stem}-Setup.exe")
    assert set(report["assets"]) == {archive.name, setup.name}
    assert (
        report["assets"][setup.name]
        == release.hashlib.sha256(setup.read_bytes()).hexdigest()
    )
    assert (
        report["assets"][archive.name]
        == release.hashlib.sha256(archive.read_bytes()).hexdigest()
    )


def test_vendored_spdx_text_is_used_when_crate_has_no_license_file(
    tmp_path, monkeypatch
):
    source = tmp_path / "crate"
    source.mkdir()
    (source / ".cargo_vcs_info.json").write_text(
        json.dumps({"git": {"sha1": "exact-commit"}})
    )
    spdx = tmp_path / "spdx"
    spdx.mkdir()
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    text = "Canonical test MIT text\n"
    upstream_text = "Copyright Test Author\n"
    (spdx / "MIT.json").write_text(
        json.dumps({"licenseId": "MIT", "licenseText": text})
    )
    (upstream / "LICENSE.txt").write_bytes(upstream_text.encode("utf-8"))
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "spdx": {
                    "MIT": {
                        "path": "spdx/MIT.json",
                        "text_sha256": release.hashlib.sha256(
                            text.encode()
                        ).hexdigest(),
                    }
                },
                "upstream": {
                    "test-LICENSE.txt": {
                        "path": "upstream/LICENSE.txt",
                        "sha256": release.hashlib.sha256(
                            upstream_text.encode()
                        ).hexdigest(),
                    }
                },
                "packages": {
                    "missing-license@1.0.0": {
                        "revision": "exact-commit",
                        "licenses": ["MIT"],
                        "notices": ["test-LICENSE.txt"],
                    }
                },
            }
        )
    )
    monkeypatch.setattr(release, "VENDORED_LICENSES", manifest)
    metadata = tmp_path / "metadata.json"
    metadata.write_text(
        json.dumps(
            {
                "packages": [
                    {
                        "name": "missing-license",
                        "version": "1.0.0",
                        "license": "MIT",
                        "source": "registry+test",
                        "manifest_path": str(source / "Cargo.toml"),
                    }
                ]
            }
        )
    )
    destination = tmp_path / "distribution"
    destination.mkdir()
    release.add_notices(destination, metadata)
    assert (
        destination / "licenses/missing-license-1.0.0/SPDX-MIT.txt"
    ).read_text() == text
    assert (
        destination / "licenses/missing-license-1.0.0/UPSTREAM-test-LICENSE.txt"
    ).read_text() == upstream_text


def test_missing_crate_license_and_vendored_record_fails_closed(tmp_path):
    source = tmp_path / "crate"
    source.mkdir()
    (source / ".cargo_vcs_info.json").write_text(
        json.dumps({"git": {"sha1": "unknown-commit"}})
    )
    metadata = tmp_path / "metadata.json"
    metadata.write_text(
        json.dumps(
            {
                "packages": [
                    {
                        "name": "unreviewed-dependency",
                        "version": "1.0.0",
                        "license": "MIT",
                        "source": "registry+test",
                        "manifest_path": str(source / "Cargo.toml"),
                    }
                ]
            }
        )
    )
    destination = tmp_path / "distribution"
    destination.mkdir()
    with pytest.raises(RuntimeError, match="No vendored license record"):
        release.add_notices(destination, metadata)


def test_packaging_rejects_missing_binaries_and_existing_output(tmp_path):
    with pytest.raises(FileNotFoundError, match="Missing native binary"):
        release.package(
            "windows-x64", tmp_path, tmp_path / "dist", tmp_path / "missing.json"
        )
    with pytest.raises(FileExistsError, match="Refusing to replace"):
        release.package(
            "windows-x64", tmp_path, tmp_path / "dist", tmp_path / "missing.json"
        )


def test_windows_setup_must_exist_before_reporting(tmp_path):
    with patch.object(release, "run"):
        with pytest.raises(RuntimeError, match="Installer was not created"):
            release.build_windows_setup(tmp_path / "stage", tmp_path)
