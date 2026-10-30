"""Frozen entry point; private USB subprocess never starts Qt or scans USB."""

import contextlib
import os
from pathlib import Path
import sys


def remote_child(arguments: list[str]) -> int:
    from mpremote.main import main

    output, *command = arguments
    sys.argv = ["mpremote", *command]
    with Path(output).open("w", encoding="utf-8") as stream, open(os.devnull) as null:
        sys.stdin = null
        with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
            try:
                main()
            except SystemExit as error:
                return int(error.code or 0)
    return 0


def main() -> int:
    if sys.argv[1:2] == ["--mpremote"]:
        return remote_child(sys.argv[2:])
    from scripts.pico_setup_gui import run

    return run()


if __name__ == "__main__":
    raise SystemExit(main())
