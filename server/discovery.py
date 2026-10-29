"""Small UDP responder used by desktop clients to find a Pico W on the LAN."""

DISCOVERY_REQUEST = b"KOHDALAB_SHUTTER_DISCOVER_V1"
RESPONSE_PREFIX = b"KOHDALAB_SHUTTER_V1"
MAX_REQUESTS_PER_POLL = 4


class DiscoveryResponder:
    """Answer a bounded number of discovery datagrams without blocking control."""

    def __init__(self, socket_module, device_id, tcp_port, port=12346):
        if not self._is_hex_id(device_id):
            raise ValueError("device_id must contain 1..64 hexadecimal characters")
        for name, value in (("tcp_port", tcp_port), ("port", port)):
            if (
                not isinstance(value, int)
                or isinstance(value, bool)
                or not 1 <= value <= 65535
            ):
                raise ValueError("{} must be in 1..65535".format(name))
        self._socket_module = socket_module
        self._response = (
            RESPONSE_PREFIX + b" " + device_id.encode() + b" " + str(tcp_port).encode()
        )
        self.port = port
        self.sock = None

    def start(self):
        if self.sock is not None:
            return True
        sock = None
        try:
            sock = self._socket_module.socket(
                self._socket_module.AF_INET, self._socket_module.SOCK_DGRAM
            )
            sock.bind(("0.0.0.0", self.port))  # noqa: S104 - receive LAN broadcast on every interface
            sock.settimeout(0)
        except Exception:
            if sock is not None:
                try:
                    sock.close()
                except Exception:  # noqa: S110 - cleanup cannot affect discovery failure
                    pass
            return False
        self.sock = sock
        return True

    def stop(self):
        if self.sock is None:
            return
        try:
            self.sock.close()
        except Exception:  # noqa: S110 - shutdown must be best-effort
            pass
        self.sock = None

    def poll(self):
        if self.sock is None:
            return
        for _ in range(MAX_REQUESTS_PER_POLL):
            try:
                request, address = self.sock.recvfrom(128)
            except OSError:
                return
            if request != DISCOVERY_REQUEST:
                continue
            try:
                self.sock.sendto(self._response, address)
            except OSError:
                pass

    @staticmethod
    def _is_hex_id(value):
        if not isinstance(value, str) or not 1 <= len(value) <= 64:
            return False
        for char in value:
            if not ("0" <= char <= "9" or "a" <= char <= "f" or "A" <= char <= "F"):
                return False
        return True
