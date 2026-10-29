## Summary

## Verification

- [ ] `cargo fmt --check`
- [ ] `cargo clippy --locked --all-targets -- -D warnings`
- [ ] `cargo test --locked --all-targets`
- [ ] `uv run ruff check .`
- [ ] `uv run mypy`
- [ ] `uv run pytest --cov --cov-report=term-missing`

## Hardware Impact

- [ ] No hardware-facing behavior changed
- [ ] Hardware-facing behavior changed and was tested with a small safe setup

## Documentation

- [ ] User-facing behaviour or hardware setup is unchanged
- [ ] README and the relevant bilingual guide were updated

## Notes
