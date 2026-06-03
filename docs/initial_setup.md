# Initial Setup

This guide prepares a Windows control PC or a macOS development machine for KohdaLab Shutter Controller.

## 1. Install Tools

### Windows PowerShell

Install Git, GitHub CLI, and uv:

```powershell
winget install --id Git.Git -e --source winget
winget install --id GitHub.cli -e --source winget
winget install --id astral-sh.uv -e --source winget
```

Close and reopen PowerShell, then check:

```powershell
git --version
gh --version
uv --version
```

### macOS

Install Homebrew if needed, then install the tools:

```bash
brew install git gh uv
```

Check:

```bash
git --version
gh --version
uv --version
```

## 2. Configure Git and GitHub

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

## 3. Clone the Repository

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

## 4. Create the Python Environment

Install dependencies:

```bash
uv sync --frozen
```

## 5. Verify the Environment

Run the hardware-free checks first:

```bash
uv run python -m compileall client server
uv run python -m client.cli --help
```

## 6. Configure Wi-Fi Credentials

Create the local Wi-Fi config from the example:

```bash
cp server/wifi_config.example.py server/wifi_config.py
```

Edit `server/wifi_config.py` for the local network. Do not commit this file.

## 7. Run the Tools

CLI:

```bash
uv run python -m client.cli --help
```

GUI:

```bash
uv run python -m client.gui
```

Pico W deployment uses `mpremote`; see [Usage guide](usage.md) for hardware notes.

## 8. Recommended Git Workflow

Work through pull requests rather than pushing directly to `main`:

```bash
git switch -c feature/my-change
git status
git add <files>
git commit -m "Describe the change"
git push -u origin feature/my-change
gh pr create
```

The `main` branch requires the Ubuntu and Windows checks to pass before merge.

## References

- uv installation: https://docs.astral.sh/uv/getting-started/installation/
- GitHub CLI: https://github.com/cli/cli
- Git downloads: https://git-scm.com/downloads
