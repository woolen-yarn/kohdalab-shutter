import socket
import time

from .protocol import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    ENCODING,
    LINE_ENDING,
    ProtocolError,
    parse_status,
)


class ShutterConnectionError(OSError):
    """Raised when the Pico cannot be reached after safe retries."""


class CommandError(ProtocolError):
    """Raised when the Pico rejects a syntactically valid command."""


class ShutterClient:
    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        timeout: float = 2.0,
        retries: int = 5,
    ) -> None:
        if not isinstance(host, str) or not host.strip():
            raise ValueError("host cannot be empty")
        if (
            not isinstance(port, int)
            or isinstance(port, bool)
            or not 1 <= port <= 65535
        ):
            raise ValueError("port must be in 1..65535")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if not isinstance(retries, int) or isinstance(retries, bool) or retries < 1:
            raise ValueError("retries must be at least one")
        self.host = host
        self.port = port
        self.timeout = timeout
        self.retries = retries

    @property
    def address(self) -> tuple[str, int]:
        return (self.host, self.port)

    def send(self, command: str, retry: bool = True) -> str:
        if (
            not isinstance(command, str)
            or not command.strip()
            or "\n" in command
            or "\r" in command
        ):
            raise ValueError("command must be one non-empty line")

        delay = 0.1
        attempts = self.retries if retry else 1
        last_error: OSError | None = None
        for attempt in range(
            attempts
        ):  # pragma: no branch - every path returns or breaks
            try:
                with socket.create_connection(
                    self.address, timeout=self.timeout
                ) as sock:
                    sock.sendall(command.encode(ENCODING) + LINE_ENDING)
                    response = sock.makefile("rb", buffering=0).readline()
                if not response:
                    raise ShutterConnectionError(
                        "Pico closed the connection without a response"
                    )
                return response.decode(ENCODING, errors="replace").strip()
            except (ConnectionResetError, BrokenPipeError, OSError) as exc:
                last_error = exc
                if attempt == attempts - 1:
                    break
                time.sleep(delay)
                delay *= 2

        raise ShutterConnectionError(
            "Cannot communicate with {}:{} after {} attempt(s): {}".format(
                self.host, self.port, attempts, last_error
            )
        ) from last_error

    def status(self) -> dict[int, int]:
        return parse_status(self.send("STATUS"))

    def open(self, channel: int) -> str:
        return self._command("OPEN", channel)

    def close(self, channel: int) -> str:
        return self._command("CLOSE", channel)

    def toggle(self, channel: int) -> str:
        # A lost response does not prove whether TOGGLE ran. Retrying could
        # immediately reverse a successful move, so it is attempted once.
        return self._command("TOGGLE", channel, retry=False)

    def _command(self, operation: str, channel: int, retry: bool = True) -> str:
        if not isinstance(channel, int) or isinstance(channel, bool) or channel < 0:
            raise ValueError("channel must be a non-negative integer")
        response = self.send("{} {}".format(operation, channel), retry=retry)
        if response != "OK":
            raise CommandError(
                "Pico rejected {} {}: {}".format(operation, channel, response)
            )
        return response
