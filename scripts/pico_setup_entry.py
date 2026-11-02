"""Frozen entry point; private USB subprocess never starts Qt or scans USB."""

import contextlib
import os
from pathlib import Path
import sys


def remote_child(arguments: list[str]) -> int:
    output, *command = arguments
    old_argv, old_stdin = sys.argv, sys.stdin
    sys.argv = ["mpremote", *command]
    try:
        with (
            Path(output).open("w", encoding="utf-8") as stream,
            Path(output + ".err").open("w", encoding="utf-8") as errors,
            open(os.devnull) as null,
        ):
            sys.stdin = null
            with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(errors):
                try:
                    from mpremote.main import main

                    return int(main() or 0)
                except SystemExit as error:
                    return (
                        error.code
                        if isinstance(error.code, int)
                        else (1 if error.code else 0)
                    )
                except Exception:
                    import traceback

                    traceback.print_exc(file=errors)
                    return 1
    finally:
        sys.argv, sys.stdin = old_argv, old_stdin


def main() -> int:
    if sys.argv[1:2] == ["--mpremote"]:
        return remote_child(sys.argv[2:])
    from scripts.pico_setup_gui import run

    return run()


if __name__ == "__main__":
    raise SystemExit(main())
