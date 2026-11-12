"""Verify downloaded release candidates and write the evidence published with them.

The publish job runs this after every platform build and the tag validation
suite have succeeded. It never builds, signs, uploads or contacts hardware.
"""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

APPLICATION = "kohdalab-shutter"
PLATFORMS = ("windows-x64", "macos-universal")
SIGNING = {
    "windows-x64": "unsigned",
    "macos-universal": "ad hoc signature; not notarized",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(repository: Path, *arguments: str) -> str:
    executable = shutil.which("git")
    if executable is None:
        raise RuntimeError("git is required to record release provenance")
    return subprocess.check_output(  # noqa: S603 - fixed git arguments
        [executable, *arguments], cwd=repository, text=True
    ).strip()


def package_names(version: str) -> set[str]:
    return {
        f"{APPLICATION}-{version}-windows-x64-Setup.exe",
        f"{APPLICATION}-{version}-windows-x64.zip",
        f"{APPLICATION}-{version}-macos-universal.zip",
        f"{APPLICATION}-{version}-macos-universal.dmg",
    }


def verify_packages(assets: Path, version: str, commit: str) -> dict[str, str]:
    """Require exactly the expected packages, each vouched for by its build."""
    expected = package_names(version)
    actual = {
        path.name
        for path in assets.iterdir()
        if path.suffix in (".zip", ".dmg", ".exe")
    }
    if actual != expected:
        raise ValueError(f"Unexpected packages: {sorted(actual ^ expected)}")
    reports = {f"BUILD-{platform}.json" for platform in PLATFORMS}
    present = {path.name for path in assets.glob("BUILD-*.json")}
    if present != reports:
        raise ValueError(f"Unexpected build reports: {sorted(present ^ reports)}")
    validated: dict[str, str] = {}
    for name in sorted(reports):
        data = json.loads((assets / name).read_text(encoding="utf-8"))
        if data["commit"] != commit or data["version"] != version:
            raise ValueError(f"{name} describes another commit or version")
        for asset, digest in data["assets"].items():
            if asset not in expected or sha256(assets / asset) != digest:
                raise ValueError(f"{name} does not match {asset}")
            validated[asset] = digest
    if set(validated) != expected:
        raise ValueError("A package is missing from the build reports")
    return validated


def prepare(
    assets: Path,
    repository: Path,
    tag: str,
    commit: str,
    test_run: int,
    release_run: int,
    validation: Path,
) -> Path:
    if not tag.startswith("v"):
        raise ValueError("Release tags start with v")
    version = tag[1:]
    if git(repository, "rev-parse", "HEAD") != commit:
        raise ValueError("The checkout is not the release commit")
    verify_packages(assets, version, commit)

    report = json.loads(validation.read_text(encoding="utf-8"))
    if (
        report.get("result") != "passed"
        or report.get("mode") != "simulation"
        or report.get("hardware_connected") is not False
    ):
        raise ValueError("GUI API validation is not a passing simulation report")
    validation_name = "validation-linux-gui-api.json"
    shutil.copyfile(validation, assets / validation_name)

    source_name = f"{APPLICATION}-{version}-source.zip"
    git(
        repository,
        "archive",
        "--format=zip",
        f"--prefix={APPLICATION}-{version}/",
        f"--output={(assets / source_name).resolve()}",
        commit,
    )

    verification = assets / "RELEASE-VERIFICATION.json"
    covered = sorted(
        path.name for path in assets.iterdir() if path.name != "SHA256SUMS.txt"
    )
    verification.write_text(
        json.dumps(
            {
                "application": "shutter",
                "version": version,
                "tag": tag,
                "release_commit": commit,
                "source_tree": git(repository, "rev-parse", f"{commit}^{{tree}}"),
                "test_run": test_run,
                "release_run": release_run,
                "hardware_tested": False,
                "signing": SIGNING,
                "source_archive": {
                    "asset": source_name,
                    "method": "git archive of release_commit",
                },
                "gui_api_validation": {
                    "asset": validation_name,
                    "scope": (
                        "Isolated simulation against the Linux build of "
                        "release_commit in test_run. Packaged Windows and Mac "
                        "binaries are checked by the build jobs of release_run."
                    ),
                },
                "assets": {
                    name: sha256(assets / name)
                    for name in covered
                    if name != verification.name
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    sums = assets / "SHA256SUMS.txt"
    sums.write_text(
        "".join(
            f"{sha256(assets / name)}  {name}\n"
            for name in sorted([*covered, verification.name])
        ),
        encoding="utf-8",
    )
    return sums


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--repository", type=Path, default=Path("."))
    parser.add_argument("--tag", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--test-run", type=int, required=True)
    parser.add_argument("--release-run", type=int, required=True)
    parser.add_argument("--validation", type=Path, required=True)
    args = parser.parse_args()
    print(
        prepare(
            args.assets,
            args.repository,
            args.tag,
            args.commit,
            args.test_run,
            args.release_run,
            args.validation,
        )
    )


if __name__ == "__main__":
    main()
