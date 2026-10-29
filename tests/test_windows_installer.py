"""Unit tests for the Windows Setup.exe source generator."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "windows_installer", ROOT / "scripts/build_windows_installer.py"
)
assert SPEC is not None and SPEC.loader is not None
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


def payload(tmp_path: Path) -> Path:
    directory = tmp_path / "portable"
    (directory / "licenses/example").mkdir(parents=True)
    for filename in (installer.APP_EXE, installer.CLI_EXE, "README.txt", "LICENSE"):
        (directory / filename).write_bytes(b"payload")
    (directory / "licenses/example/LICENSE.txt").write_text("license", encoding="utf-8")
    return directory


def test_generated_include_installs_and_removes_only_payload_files(
    tmp_path: Path,
) -> None:
    source = installer.generated_payload_include(payload(tmp_path))
    assert "!macro InstallPayload" in source
    assert 'SetOutPath "$INSTDIR\\licenses\\example"' in source
    assert 'File /oname="LICENSE.txt"' in source
    assert 'Delete "$INSTDIR\\licenses\\example\\LICENSE.txt"' in source
    assert 'RMDir "$INSTDIR\\licenses\\example"' in source
    assert 'RMDir "$INSTDIR\\licenses"' in source
    assert "RMDir /r" not in source


def test_payload_validation_requires_launchers_and_rejects_links(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidate = payload(tmp_path)
    (candidate / installer.CLI_EXE).unlink()
    with pytest.raises(ValueError, match="kohdalab-shutter.exe"):
        installer.payload_files(candidate)
    (candidate / installer.CLI_EXE).write_bytes(b"cli")
    linked = candidate / "linked.txt"
    linked.write_text("link fixture", encoding="utf-8")
    original = Path.is_symlink
    monkeypatch.setattr(
        Path, "is_symlink", lambda path: path == linked or original(path)
    )
    with pytest.raises(ValueError, match="symlink"):
        installer.payload_files(candidate)


@pytest.mark.parametrize(
    ("value", "expected"),
    [("0.4.3", "0.4.3.0"), ("1.2.3-beta.1", "1.2.3.0"), ("1.2.3.4", "1.2.3.4")],
)
def test_windows_file_version(value: str, expected: str) -> None:
    assert installer.windows_file_version(value) == expected


def test_static_template_is_per_user_and_preserves_unknown_files() -> None:
    source = (ROOT / "packaging/windows/KohdaLab-Shutter.nsi").read_text(
        encoding="utf-8"
    )
    assert 'InstallDir "$LOCALAPPDATA\\Programs\\Kohdalab\\KohdaLab Shutter"' in source
    assert "RequestExecutionLevel user" in source
    assert "InstallDirRegKey" not in source
    assert (
        'StrCpy $INSTDIR "$LOCALAPPDATA\\Programs\\Kohdalab\\KohdaLab Shutter"'
        in source
    )
    assert "HKLM" not in source
    assert "RMDir /r" not in source
    assert "Close KohdaLab Shutter before" in source
    assert "KohdaLabShutter" in source
    assert "KohdaLab Shutter Demo.lnk" in source
    assert "CreateFileW" in source
    assert "IfSilent" in source


def test_nsis_license_is_added_to_portable_payload(tmp_path: Path) -> None:
    candidate = payload(tmp_path)
    (candidate / "THIRD-PARTY-NOTICES.txt").write_text("existing\n", encoding="utf-8")
    installer.add_nsis_notice(candidate)
    assert (candidate / "licenses/nsis-3.12-zlib.txt").read_text(
        encoding="utf-8"
    ) == installer.NSIS_LICENSE
    assert "NSIS 3.12 bootstrap" in (candidate / "THIRD-PARTY-NOTICES.txt").read_text(
        encoding="utf-8"
    )
