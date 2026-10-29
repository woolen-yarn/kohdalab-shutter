import argparse
from collections.abc import Sequence
import sys

from .protocol import DEFAULT_HOST, DEFAULT_PORT, format_status
from .transport import ShutterClient

COMMANDS = {"status", "open", "close", "toggle"}


def main(argv: Sequence[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    legacy_host = None
    if argv and not argv[0].startswith("-") and argv[0].lower() not in COMMANDS:
        legacy_host = argv.pop(0)

    parser = argparse.ArgumentParser(
        description="Control the Pico W shutter server over TCP"
    )
    parser.add_argument(
        "--host", "--ip", default=legacy_host or DEFAULT_HOST, help="Pico W IP address"
    )
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="TCP port")
    parser.add_argument(
        "--timeout", type=float, default=2.0, help="Socket timeout in seconds"
    )
    parser.add_argument("--retries", type=int, default=5, help="Connection retry count")

    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("status")

    open_parser = subparsers.add_parser("open")
    open_parser.add_argument("channel", type=int)

    close_parser = subparsers.add_parser("close")
    close_parser.add_argument("channel", type=int)

    toggle_parser = subparsers.add_parser("toggle")
    toggle_parser.add_argument("channel", type=int)

    args = parser.parse_args(argv)
    client = ShutterClient(
        args.host, args.port, timeout=args.timeout, retries=args.retries
    )

    if args.command is None:
        run_shell(client)
        return

    try:
        print(run_command(client, args.command, getattr(args, "channel", None)))
    except Exception as exc:
        print("ERROR:", exc)
        raise SystemExit(1) from exc


def run_command(client: ShutterClient, command: str, channel: int | None = None) -> str:
    if command == "status":
        return format_status(client.status())
    if command == "open":
        if channel is None:
            raise ValueError("channel number required")
        return client.open(channel)
    if command == "close":
        if channel is None:
            raise ValueError("channel number required")
        return client.close(channel)
    if command == "toggle":
        if channel is None:
            raise ValueError("channel number required")
        return client.toggle(channel)
    return client.send(command)


def run_shell(client: ShutterClient) -> None:
    print(
        "Connected to {}:{}. Commands: status | open n | close n | toggle n | quit".format(
            *client.address
        )
    )
    while True:
        try:
            line = input("[{}] > ".format(client.host)).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return

        if not line:
            continue
        if line.lower() in ("quit", "exit"):
            return

        try:
            command, *rest = line.split()
            channel = int(rest[0]) if rest else None
            if command.lower() in ("open", "close", "toggle") and channel is None:
                print("ERR: channel number required")
                continue
            print(run_command(client, command.lower(), channel))
        except Exception as exc:
            print("ERROR:", exc)


if (
    __name__ == "__main__"
):  # pragma: no cover - exercised through the console entry point
    main()
