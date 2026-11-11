"""Release evidence is generated from verified bytes of one commit."""

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "release_evidence", ROOT / "scripts/prepare_release_evidence.py"
)
assert SPEC is not None and SPEC.loader is not None
evidence = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evidence)

VERSION = "9.8.7"
TAG = "v" + VERSION


def run_git(repository, *arguments):
    return subprocess.check_output(  # noqa: S603 - fixed git arguments in a temp repo
        [evidence.shutil.which("git"), *arguments], cwd=repository, text=True
    ).strip()


@pytest.fixture
def repository(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    run_git(repo, "init", "--quiet")
    (repo / "README.md").write_text("release source\n", encoding="utf-8")
    run_git(repo, "add", "README.md")
    run_git(
        repo,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "--quiet",
        "-m",
        "source",
    )
    return repo


@pytest.fixture
def candidates(tmp_path, repository):
    commit = run_git(repository, "rev-parse", "HEAD")
    assets = tmp_path / "assets"
    assets.mkdir()
    groups = {
        "windows-x64": ("windows-x64-Setup.exe", "windows-x64.zip"),
        "macos-universal": ("macos-universal.zip", "macos-universal.dmg"),
    }
    for platform, suffixes in groups.items():
        digests = {}
        for suffix in suffixes:
            name = f"kohdalab-shutter-{VERSION}-{suffix}"
            (assets / name).write_bytes(name.encode())
            digests[name] = hashlib.sha256(name.encode()).hexdigest()
        (assets / f"BUILD-{platform}.json").write_text(
            json.dumps({"version": VERSION, "commit": commit, "assets": digests}),
            encoding="utf-8",
        )
    validation = tmp_path / "gui-api-validation.json"
    validation.write_text(
        json.dumps(
            {"result": "passed", "mode": "simulation", "hardware_connected": False}
        ),
        encoding="utf-8",
    )
    return assets, commit, validation


def prepare(repository, candidates, tag=TAG):
    assets, commit, validation = candidates
    return evidence.prepare(assets, repository, tag, commit, 11, 22, validation)


def test_evidence_covers_every_published_file(repository, candidates):
    assets, commit, _ = candidates
    sums = prepare(repository, candidates)

    listed = dict(reversed(line.split("  ")) for line in sums.read_text().splitlines())
    published = {path.name for path in assets.iterdir()}
    assert set(listed) == published - {"SHA256SUMS.txt"}
    assert {
        "BUILD-windows-x64.json",
        "BUILD-macos-universal.json",
        "RELEASE-VERIFICATION.json",
        "validation-linux-gui-api.json",
        f"kohdalab-shutter-{VERSION}-source.zip",
    } <= set(listed)
    for name, digest in listed.items():
        assert hashlib.sha256((assets / name).read_bytes()).hexdigest() == digest

    record = json.loads((assets / "RELEASE-VERIFICATION.json").read_text())
    assert record["tag"] == TAG and record["version"] == VERSION
    assert record["release_commit"] == commit
    assert record["source_tree"] == run_git(repository, "rev-parse", "HEAD^{tree}")
    assert (record["test_run"], record["release_run"]) == (11, 22)
    assert record["hardware_tested"] is False
    assert record["signing"]["windows-x64"] == "unsigned"
    assert set(record["assets"]) == set(listed) - {"RELEASE-VERIFICATION.json"}
    assert all(listed[name] == digest for name, digest in record["assets"].items())

    with zipfile.ZipFile(assets / f"kohdalab-shutter-{VERSION}-source.zip") as source:
        assert source.read(f"kohdalab-shutter-{VERSION}/README.md") == (
            b"release source\n"
        )


@pytest.mark.parametrize(
    "damage, message",
    [
        (lambda a: (a / "extra.zip").write_bytes(b"x"), "Unexpected packages"),
        (
            lambda a: (a / f"kohdalab-shutter-{VERSION}-windows-x64.zip").unlink(),
            "Unexpected packages",
        ),
        (
            lambda a: (a / f"kohdalab-shutter-{VERSION}-windows-x64.zip").write_bytes(
                b"changed"
            ),
            "does not match",
        ),
        (lambda a: (a / "BUILD-macos-universal.json").unlink(), "build reports"),
        (
            lambda a: (a / "BUILD-windows-x64.json").write_text(
                json.dumps({"version": VERSION, "commit": "0" * 40, "assets": {}})
            ),
            "another commit",
        ),
        (
            lambda a: (a / "BUILD-windows-x64.json").write_text(
                json.dumps(
                    {
                        "version": VERSION,
                        "commit": json.loads(
                            (a / "BUILD-macos-universal.json").read_text()
                        )["commit"],
                        "assets": {},
                    }
                )
            ),
            "missing from the build reports",
        ),
    ],
)
def test_unverified_candidates_are_rejected(repository, candidates, damage, message):
    damage(candidates[0])
    with pytest.raises(ValueError, match=message):
        prepare(repository, candidates)
    assert not (candidates[0] / "SHA256SUMS.txt").exists()


def test_other_checkout_tag_or_failed_validation_is_rejected(repository, candidates):
    assets, commit, validation = candidates
    with pytest.raises(ValueError, match="start with v"):
        prepare(repository, candidates, tag=VERSION)
    with pytest.raises(ValueError, match="not the release commit"):
        evidence.prepare(assets, repository, TAG, "0" * 40, 1, 2, validation)
    for report in (
        {"result": "failed", "mode": "simulation", "hardware_connected": False},
        {"result": "passed", "mode": "hardware", "hardware_connected": False},
        {"result": "passed", "mode": "simulation", "hardware_connected": True},
    ):
        validation.write_text(json.dumps(report), encoding="utf-8")
        with pytest.raises(ValueError, match="passing simulation"):
            prepare(repository, candidates)
    assert not (assets / "RELEASE-VERIFICATION.json").exists()
