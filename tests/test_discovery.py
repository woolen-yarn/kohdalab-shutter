import pytest

from server.discovery import (
    DISCOVERY_REQUEST,
    MAX_REQUESTS_PER_POLL,
    DiscoveryResponder,
)


class FakeSocket:
    def __init__(self, packets=(), fail_bind=False, fail_close=False, fail_send=False):
        self.packets = list(packets)
        self.fail_bind = fail_bind
        self.fail_close = fail_close
        self.fail_send = fail_send
        self.bound = None
        self.timeout = None
        self.closed = False
        self.sent = []

    def bind(self, address):
        if self.fail_bind:
            raise OSError("bind failed")
        self.bound = address

    def settimeout(self, timeout):
        self.timeout = timeout

    def recvfrom(self, _size):
        if not self.packets:
            raise OSError("no packets")
        return self.packets.pop(0)

    def sendto(self, data, address):
        if self.fail_send:
            raise OSError("send failed")
        self.sent.append((data, address))

    def close(self):
        self.closed = True
        if self.fail_close:
            raise OSError("close failed")


class FakeSocketModule:
    AF_INET = 2
    SOCK_DGRAM = 2

    def __init__(self, packets=(), fail_bind=False, fail_socket=False, **socket_kwargs):
        self.sock = FakeSocket(packets, fail_bind, **socket_kwargs)
        self.fail_socket = fail_socket

    def socket(self, family, kind):
        assert (family, kind) == (self.AF_INET, self.SOCK_DGRAM)
        if self.fail_socket:
            raise OSError("socket failed")
        return self.sock


@pytest.mark.parametrize(
    ("device_id", "tcp_port", "port"),
    [
        ("", 12345, 12346),
        ("z", 12345, 12346),
        ("a" * 65, 12345, 12346),
        (1, 12345, 12346),
        ("abc", True, 12346),
        ("abc", 0, 12346),
        ("abc", 12345, False),
        ("abc", 12345, 65536),
    ],
)
def test_rejects_invalid_settings(device_id, tcp_port, port):
    with pytest.raises(ValueError):
        DiscoveryResponder(FakeSocketModule(), device_id, tcp_port, port)


def test_start_configures_nonblocking_socket_and_stop_closes_it():
    module = FakeSocketModule()
    responder = DiscoveryResponder(module, "a1b2", 12345)

    assert responder.start() is True
    assert module.sock.bound[1] == 12346
    assert module.sock.timeout == 0

    responder.stop()
    assert module.sock.closed is True
    assert responder.sock is None


def test_start_is_idempotent_and_stop_is_safe_when_not_started():
    module = FakeSocketModule()
    responder = DiscoveryResponder(module, "A1B2", 12345)

    responder.stop()
    assert responder.start() is True
    assert responder.start() is True
    assert responder._response == b"KOHDALAB_SHUTTER_V1 A1B2 12345"


def test_start_failure_closes_socket():
    module = FakeSocketModule(fail_bind=True)
    responder = DiscoveryResponder(module, "a1b2", 12345)

    assert responder.start() is False
    assert module.sock.closed is True
    assert responder.sock is None


def test_socket_creation_failure_needs_no_cleanup():
    responder = DiscoveryResponder(FakeSocketModule(fail_socket=True), "a1b2", 12345)

    assert responder.start() is False
    assert responder.sock is None


def test_start_failure_ignores_close_error():
    module = FakeSocketModule(fail_bind=True, fail_close=True)
    responder = DiscoveryResponder(module, "a1b2", 12345)

    assert responder.start() is False
    assert module.sock.closed is True


def test_stop_ignores_close_error():
    module = FakeSocketModule(fail_close=True)
    responder = DiscoveryResponder(module, "a1b2", 12345)
    assert responder.start()

    responder.stop()

    assert responder.sock is None


def test_ignores_malformed_requests_and_answers_valid_ones():
    address = ("10.0.0.2", 40000)
    module = FakeSocketModule([(b"invalid", address), (DISCOVERY_REQUEST, address)])
    responder = DiscoveryResponder(module, "a1b2", 12345)
    assert responder.start()

    responder.poll()

    assert module.sock.sent == [(b"KOHDALAB_SHUTTER_V1 a1b2 12345", address)]


def test_poll_handles_at_most_four_requests_per_tick():
    packets = [
        (DISCOVERY_REQUEST, ("10.0.0.{}".format(index), 40000)) for index in range(6)
    ]
    module = FakeSocketModule(packets)
    responder = DiscoveryResponder(module, "a1b2", 12345)
    assert responder.start()

    responder.poll()

    assert len(module.sock.sent) == MAX_REQUESTS_PER_POLL
    assert len(module.sock.packets) == 2


def test_poll_is_safe_before_start_and_ignores_send_failure():
    responder = DiscoveryResponder(FakeSocketModule(), "a1b2", 12345)
    responder.poll()

    module = FakeSocketModule(
        [(DISCOVERY_REQUEST, ("10.0.0.2", 40000))], fail_send=True
    )
    responder = DiscoveryResponder(module, "a1b2", 12345)
    assert responder.start()
    responder.poll()
    assert module.sock.sent == []
