#!/bin/sh
cd "$(dirname "$0")" || exit 1
if ! command -v uv >/dev/null 2>&1; then
    echo 'Install uv: https://docs.astral.sh/uv/getting-started/installation/'
    printf 'Press Enter to close.'
    read -r answer
    exit 1
fi
uv run --no-project --python 3.13 --with 'mpremote>=1.25,<2' python scripts/upload_pico.py "$@"
result=$?
printf 'Press Enter to close.'
read -r answer
exit "$result"
