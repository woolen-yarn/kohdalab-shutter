#!/usr/bin/env python3
"""Verify Shutter's common control API against the isolated demo GUI."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import tempfile
import time
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bindings" / "control"))
from kohdalab_control import ControlClient  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "binary",
        type=Path,
        nargs="?",
        default=Path("target/debug/kohdalab-shutter-gui"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(tempfile.gettempdir()) / "kohdalab-shutter-common-control.json",
    )
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    log_path = args.output.with_suffix(".log")
    with tempfile.TemporaryDirectory(prefix="kohdalab-shutter-common-") as directory:
        with log_path.open("w", encoding="utf-8") as log:
            process = subprocess.Popen(  # noqa: S603 - explicit test binary, no shell
                [
                    str(args.binary.resolve()),
                    "--demo",
                    "--gui-api",
                    "--api-directory",
                    directory,
                ],
                stdout=log,
                stderr=subprocess.STDOUT,
            )
        try:
            endpoint = None
            for _ in range(300):
                candidates = list(Path(directory).glob("*.json"))
                if candidates:
                    endpoint = candidates[0]
                    break
                if process.poll() is not None:
                    raise RuntimeError(
                        f"Shutter exited before API startup: {process.returncode}"
                    )
                time.sleep(0.1)
            if endpoint is None:
                raise RuntimeError("Shutter common API descriptor did not appear")
            client = ControlClient(endpoint=endpoint)
            description = client.describe()
            if description["application"] != "kohdalab-shutter":
                raise RuntimeError("Unexpected application identity")
            if (
                client.status().get("demo") is not True
                or client.config().get("demo") is not True
            ):
                raise RuntimeError("Shutter was not running in explicit demo mode")
            lease = client.acquire()
            if not lease.get("lease"):
                raise RuntimeError("Common acquire did not return a lease")
            first = client.invoke("open", channel=0)
            if first.get("cleanup") != "not_required":
                raise RuntimeError(
                    "Hold-last-state receipt must report cleanup=not_required"
                )
            completed = client.wait(first["job_id"], timeout=5)
            if (
                completed.get("status") != "completed"
                or completed.get("cleanup") != "not_required"
            ):
                raise RuntimeError(
                    "Open receipt did not complete with truthful cleanup"
                )
            duplicate = client.invoke("open", channel=0, request_id=first["job_id"])
            if (
                duplicate.get("job_id") != first["job_id"]
                or duplicate.get("cleanup") != "not_required"
            ):
                raise RuntimeError("Duplicate request did not return a stable receipt")
            released = client.release()
            if (
                released.get("released") is not True
                or released.get("cleanup") != "not_required"
            ):
                raise RuntimeError("Release did not preserve hold-last-state semantics")
            report = {
                "result": "passed",
                "application": description["application"],
                "methods": description["methods"],
                "duplicate_receipt": "stable",
                "cleanup": "not_required",
                "hardware_connected": False,
                "simulation": True,
                "descriptor": str(endpoint),
                "log": str(log_path),
            }
            args.output.write_text(
                json.dumps(report, indent=2) + "\n", encoding="utf-8"
            )
            print(json.dumps(report, sort_keys=True))
            return 0
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
