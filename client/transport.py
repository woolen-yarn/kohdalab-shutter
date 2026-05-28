import errno
import socket
import time

from .protocol import DEFAULT_HOST, DEFAULT_PORT, ENCODING, LINE_ENDING, parse_status


class ShutterClient:
    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT, timeout=2.0, retries=5):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.retries = retries

    @property
    def address(self):
        return (self.host, self.port)

    def send(self, command):
        delay = 0.1
        for attempt in range(self.retries):
            try:
                with socket.create_connection(self.address, timeout=self.timeout) as sock:
                    sock.sendall(command.encode(ENCODING) + LINE_ENDING)
                    response = sock.makefile("rb", buffering=0).readline()
                if not response:
                    raise RuntimeError("Empty response from server")
                return response.decode(ENCODING, errors="replace").strip()
            except (ConnectionResetError, BrokenPipeError, OSError) as exc:
                if not self._should_retry(exc) or attempt == self.retries - 1:
                    raise
                time.sleep(delay)
                delay *= 2

        raise ConnectionResetError("Connection failed after retries")

    def status(self):
        return parse_status(self.send("STATUS"))

    def open(self, channel):
        return self.send("OPEN {}".format(channel))

    def close(self, channel):
        return self.send("CLOSE {}".format(channel))

    def toggle(self, channel):
        return self.send("TOGGLE {}".format(channel))

    @staticmethod
    def _should_retry(exc):
        return getattr(exc, "errno", None) in (
            errno.ECONNRESET,
            errno.EPIPE,
            errno.EAGAIN,
            errno.ETIMEDOUT,
        )
