# Initial setup / 初期設定

This guide prepares a control PC or development machine. A Rust build is the normal desktop path; Python/uv is only needed to maintain the Pico W or use the compatibility client.

このガイドは制御PCまたは開発PCを準備します。PCアプリの標準はRustビルドです。Python/uvはPico Wの保守と互換クライアントにだけ必要です。

## 1. Install tools / ツールの導入

### Windows PowerShell

Install Rust, Git, GitHub CLI, and uv:

```powershell
winget install --id Rustlang.Rustup -e
winget install --id Git.Git -e --source winget
winget install --id GitHub.cli -e --source winget
winget install --id astral-sh.uv -e --source winget
```

Close and reopen PowerShell, then check:

```powershell
git --version
gh --version
uv --version
cargo --version
```

### macOS

Install Homebrew if needed, then install the tools:

```bash
brew install rust git gh uv
```

Check:

```bash
git --version
gh --version
uv --version
```

## 2. Configure Git and GitHub / Git・GitHubの設定

Set your Git identity once per machine:

```bash
git config --global user.name "Your Name"
git config --global user.email "your-email@example.com"
```

Log in to GitHub:

```bash
gh auth login
gh auth setup-git
```

Use the browser login flow when prompted. For private repositories, confirm that `gh auth status` shows an authenticated account with repository access.

## 3. Clone the repository / リポジトリの取得

For the KohdaLab organization repository:

```bash
gh repo clone Kohdalab/kohdalab-shutter
cd kohdalab-shutter
```

For the personal mirror:

```bash
gh repo clone woolen-yarn/kohdalab-shutter
cd kohdalab-shutter
```

## 4. Build the Rust desktop app / Rustデスクトップアプリのビルド

Install stable Rust from https://www.rust-lang.org/tools/install. On Windows, include the Visual Studio C++ Build Tools.

```sh
cargo build --release --locked
cargo run --bin kohdalab-shutter -- discover
cargo run --bin kohdalab-shutter-gui
```

See [Pico W setup and discovery](rust-client.md) for firmware updates and USB IP inspection. Python is needed for Pico uploads and compatibility clients.

## 5. Create the Python environment / Python環境の作成

Install dependencies:

```bash
uv sync --all-extras --frozen
```

## 6. Verify / 確認

Run the hardware-free checks first:

```bash
cargo fmt --check
cargo clippy --locked --all-targets -- -D warnings
cargo test --locked --all-targets
uv run ruff check .
uv run mypy
uv run pytest --cov --cov-report=term-missing
```

## 7. Configure Wi-Fi credentials / Wi-Fi認証情報の設定

Create the local Wi-Fi config from the example:

```bash
cp server/wifi_config.example.py server/wifi_config.py
```

Edit `server/wifi_config.py` for the local network. Do not commit this file.

## 8. Operate / 操作

CLI:

```bash
cargo run --bin kohdalab-shutter -- --help
```

GUI:

```bash
cargo run --bin kohdalab-shutter-gui
```

Pico W deployment uses `mpremote`; see [Usage guide](usage.md) for hardware notes.

## 9. Recommended Git workflow / 推奨Git手順

Work through pull requests rather than pushing directly to `main`:

```bash
git switch -c feature/my-change
git status
git add <files>
git commit -m "Describe the change"
git push -u origin feature/my-change
gh pr create
```

Confirm the CI checks pass before merging into `main`.

## References / 参考

- uv installation: https://docs.astral.sh/uv/getting-started/installation/
- GitHub CLI: https://github.com/cli/cli
- Git downloads: https://git-scm.com/downloads
