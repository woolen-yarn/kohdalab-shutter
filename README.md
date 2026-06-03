# KohdaLab Shutter Controller

[![Test](https://github.com/woolen-yarn/kohdalab-shutter/actions/workflows/test.yml/badge.svg)](https://github.com/woolen-yarn/kohdalab-shutter/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Python](https://img.shields.io/badge/python-3.13-blue)

KohdaLab Shutter Controller controls servo-driven optical shutters over Wi-Fi using a Raspberry Pi Pico W and PCA9685 PWM driver.

## What It Does

- Runs MicroPython control code on a Pico W.
- Provides PC-side CLI and PySide6 GUI tools.
- Controls multiple shutter channels over a simple TCP protocol.
- Keeps Wi-Fi credentials out of version control.

## Quick Start

For a new PC, start with the setup guide:

- [Initial setup](docs/initial_setup.md)

After setup:

```powershell
uv sync --frozen
uv run python -m client.cli --help
uv run python -m client.gui
```

Run checks:

```powershell
uv run python -m compileall client server
uv run python -m client.cli --help
```

## Documentation

- [Initial setup](docs/initial_setup.md): install Git, GitHub CLI, uv, clone the repository, and verify the environment.
- [Usage guide](docs/usage.md): hardware overview, Wi-Fi setup, CLI, GUI, and expansion notes.
- [Specification](docs/specification.md): TCP protocol and channel behavior.
- [Purchase list](docs/purchase-list.md): hardware purchasing notes.
- [Windows setup](docs/windows_setup.md): Windows PC preparation notes.
- [Roadmap](ROADMAP.md): planned milestones.
- [Safety notes](SAFETY.md): safety assumptions and operator responsibilities.
- [Contributing](CONTRIBUTING.md): development workflow and pull request expectations.

## Project Status

`v0.1.0` is the repository baseline: licensing, CI, branch protection, dependency maintenance, and documentation structure are in place. Device robustness and simulated transports are planned next.

## License

MIT. See [LICENSE](LICENSE).
