import pytest

from client import cli


class FakeClient:
    address = ("pico.local", 12345)
    host = "pico.local"

    def __init__(self):
        self.calls = []

    def status(self):
        self.calls.append(("status", None))
        return {1: 90, 0: 0}

    def open(self, channel):
        self.calls.append(("open", channel))
        return "OK"

    def close(self, channel):
        self.calls.append(("close", channel))
        return "OK"

    def toggle(self, channel):
        self.calls.append(("toggle", channel))
        return "OK"

    def send(self, command):
        self.calls.append(("send", command))
        return "UNKNOWN"


def test_dispatches_commands():
    client = FakeClient()
    assert cli.run_command(client, "status") == "CH0=0, CH1=90"
    assert cli.run_command(client, "open", 0) == "OK"
    assert cli.run_command(client, "close", 1) == "OK"
    assert cli.run_command(client, "toggle", 2) == "OK"
    assert cli.run_command(client, "PING") == "UNKNOWN"


@pytest.mark.parametrize("command", ["open", "close", "toggle"])
def test_commands_require_channel(command):
    with pytest.raises(ValueError, match="channel number required"):
        cli.run_command(FakeClient(), command)


def test_main_runs_command_with_legacy_host(monkeypatch, capsys):
    captured = {}

    def client_factory(host, port, timeout, retries):
        captured.update(host=host, port=port, timeout=timeout, retries=retries)
        return FakeClient()

    monkeypatch.setattr(cli, "ShutterClient", client_factory)
    cli.main(
        [
            "pico.local",
            "--port",
            "5432",
            "--timeout",
            "1.5",
            "--retries",
            "2",
            "open",
            "3",
        ]
    )
    assert captured == {
        "host": "pico.local",
        "port": 5432,
        "timeout": 1.5,
        "retries": 2,
    }
    assert capsys.readouterr().out == "OK\n"


def test_main_uses_sys_argv_and_enters_shell(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(cli.sys, "argv", ["program"])
    monkeypatch.setattr(cli, "ShutterClient", lambda *_args, **_kwargs: client)
    called = []
    monkeypatch.setattr(cli, "run_shell", called.append)
    cli.main()
    assert called == [client]


def test_main_reports_command_error(monkeypatch, capsys):
    client = FakeClient()
    monkeypatch.setattr(cli, "ShutterClient", lambda *_args, **_kwargs: client)
    monkeypatch.setattr(cli, "run_command", lambda *_args: 1 / 0)
    with pytest.raises(SystemExit) as error:
        cli.main(["status"])
    assert error.value.code == 1
    assert "ERROR: division by zero" in capsys.readouterr().out


def test_interactive_shell(monkeypatch, capsys):
    client = FakeClient()
    entries = iter(["", "open", "status", "nonsense x", "quit"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(entries))
    cli.run_shell(client)
    output = capsys.readouterr().out
    assert "channel number required" in output
    assert "CH0=0, CH1=90" in output
    assert "invalid literal" in output


@pytest.mark.parametrize("error", [EOFError(), KeyboardInterrupt()])
def test_interactive_shell_handles_terminal_exit(monkeypatch, capsys, error):
    client = FakeClient()

    def stop(_prompt):
        raise error

    monkeypatch.setattr("builtins.input", stop)
    cli.run_shell(client)
    assert "Connected to pico.local:12345" in capsys.readouterr().out
