import pytest

from client.protocol import ProtocolError
from client.transport import CommandError, ShutterClient, ShutterConnectionError


class FakeFile:
    def __init__(self, response):
        self.response = response

    def readline(self):
        return self.response


class FakeSocket:
    def __init__(self, response):
        self.response = response
        self.sent = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def sendall(self, value):
        self.sent.append(value)

    def makefile(self, *_args, **_kwargs):
        return FakeFile(self.response)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"host": ""}, "host"),
        ({"port": True}, "port"),
        ({"port": 0}, "port"),
        ({"timeout": 0}, "timeout"),
        ({"retries": True}, "retries"),
        ({"retries": 0}, "retries"),
    ],
)
def test_validates_client_settings(kwargs, message):
    with pytest.raises(ValueError, match=message):
        ShutterClient(**kwargs)


def test_sends_and_parses_status(monkeypatch):
    sock = FakeSocket(b"CH0=0,CH1=90\n")
    monkeypatch.setattr(
        "client.transport.socket.create_connection", lambda address, timeout: sock
    )
    client = ShutterClient("pico.local", 12345)
    assert client.address == ("pico.local", 12345)
    assert client.status() == {0: 0, 1: 90}
    assert sock.sent == [b"STATUS\n"]


def test_retries_idempotent_command(monkeypatch):
    sock = FakeSocket(b"OK\n")
    attempts = iter([OSError("offline"), sock])
    sleeps = []

    def connect(_address, timeout):
        result = next(attempts)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr("client.transport.socket.create_connection", connect)
    monkeypatch.setattr("client.transport.time.sleep", sleeps.append)
    assert ShutterClient(retries=2).open(0) == "OK"
    assert sleeps == [0.1]


def test_toggle_is_not_retried(monkeypatch):
    attempts = []

    def connect(_address, timeout):
        attempts.append(timeout)
        raise ConnectionResetError("lost response")

    monkeypatch.setattr("client.transport.socket.create_connection", connect)
    with pytest.raises(ShutterConnectionError, match="1 attempt"):
        ShutterClient(retries=5).toggle(0)
    assert len(attempts) == 1


def test_reports_empty_or_failed_response(monkeypatch):
    monkeypatch.setattr(
        "client.transport.socket.create_connection",
        lambda _address, timeout: FakeSocket(b""),
    )
    monkeypatch.setattr("client.transport.time.sleep", lambda _delay: None)
    with pytest.raises(ShutterConnectionError, match="without a response") as error:
        ShutterClient(retries=1).status()
    assert isinstance(error.value.__cause__, ShutterConnectionError)


@pytest.mark.parametrize("command", ["", None, "STATUS\nOPEN 0", "STATUS\r"])
def test_rejects_invalid_command(command):
    with pytest.raises(ValueError, match="one non-empty line"):
        ShutterClient().send(command)


@pytest.mark.parametrize("channel", [-1, True, 1.5])
def test_rejects_invalid_channel(channel):
    with pytest.raises(ValueError, match="channel"):
        ShutterClient().close(channel)


def test_rejects_command_error(monkeypatch):
    monkeypatch.setattr(
        "client.transport.socket.create_connection",
        lambda _address, timeout: FakeSocket(b"ERR\n"),
    )
    with pytest.raises(CommandError, match="rejected CLOSE"):
        ShutterClient().close(1)


def test_surfaces_malformed_status(monkeypatch):
    monkeypatch.setattr(
        "client.transport.socket.create_connection",
        lambda _address, timeout: FakeSocket(b"bad\n"),
    )
    with pytest.raises(ProtocolError):
        ShutterClient().status()
