# Contributing / 開発ガイド

This project controls a physical servo shutter system, so changes should favour predictable hardware behaviour, simple recovery, and clear operator feedback.

このプロジェクトは物理的なサーボシャッターを制御します。変更では予測可能な動作、復旧のしやすさ、明確な操作者への表示を優先してください。

## Development setup / 開発環境

Build the Rust desktop app with `cargo build --locked`. See [Rust client](docs/rust-client.md).

Use `uv` for firmware tests and compatibility clients from the repository root:

```powershell
uv sync --all-extras --all-groups
```

Run hardware-free checks:

```sh
cargo fmt --check
cargo clippy --locked --all-targets -- -D warnings
cargo test --locked --all-targets
python scripts/verify_gui_api.py target/release/kohdalab-shutter-gui
```

```powershell
uv run ruff check .
uv run mypy
uv run pytest --cov --cov-report=term-missing
```

## Change guidelines / 変更の方針

- Keep Rust protocol parsing in `src/protocol.rs` and discovery in `src/discovery.rs`.
- Keep compatibility Python parsing in `client/protocol.py`.
- Keep Rust TCP behavior in `src/transport.rs`; compatibility behavior is in `client/transport.py`.
- Keep Pico-side hardware configuration in `server/settings.py`.
- Keep Wi-Fi credentials out of Git. Use `server/wifi_config.example.py` as the
  shared template.
- Prefer changes that scale with the channel list rather than hard-coding a
  fixed number of channels.

## Hardware changes / ハードウェア変更

For channel or wiring changes, document:

- Pico GPIO pins
- PCA9685 channels
- servo open and close angles
- power supply assumptions
- the smallest safe test after upload

## Pull requests / プルリクエスト

Before opening a pull request:

```powershell
cargo fmt --check
cargo clippy --locked --all-targets -- -D warnings
cargo test --locked --all-targets
python scripts/verify_gui_api.py target/release/kohdalab-shutter-gui
uv run ruff check .
uv run mypy
uv run pytest --cov --cov-report=term-missing
```

If the change affects servo motion or Wi-Fi startup, include the hardware used
and the smallest test performed.

API ownership and receipts live in `src/control.rs`; the bounded local bridge is `src/remote.rs`. Keep external operations on the same GUI command path. Python/Jupyter uses `bindings/python/kohdalab_shutter.py`. See [GUI API](docs/gui-api.md).
