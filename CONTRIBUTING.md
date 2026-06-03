# Contributing

Thank you for improving KohdaLab Shutter. This project controls a physical
servo shutter system, so changes should favor predictable hardware behavior,
simple recovery, and clear operator feedback.

## Development Setup

Use `uv` from the repository root:

```powershell
uv sync
```

Run hardware-free checks:

```powershell
uv run python -m compileall client server
uv run python -m client.cli --help
```

## Change Guidelines

- Keep PC-side protocol parsing in `client/protocol.py`.
- Keep TCP behavior in `client/transport.py`.
- Keep Pico-side hardware configuration in `server/settings.py`.
- Keep Wi-Fi credentials out of Git. Use `server/wifi_config.example.py` as the
  shared template.
- Prefer changes that scale with the channel list rather than hard-coding a
  fixed number of channels.

## Hardware Changes

For channel or wiring changes, document:

- Pico GPIO pins
- PCA9685 channels
- servo open and close angles
- power supply assumptions
- the smallest safe test after upload

## Pull Requests

Before opening a pull request:

```powershell
uv run python -m compileall client server
uv run python -m client.cli --help
```

If the change affects servo motion or Wi-Fi startup, include the hardware used
and the smallest test performed.
