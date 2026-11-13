# Common control API validation

Date: 2026-10-29. Target: 0.6.2. Host: macOS ARM64.

- Device-free Rust tests: 63 passed across the selected application/workspace and common contract suites.
- Shared Python SDK: 9 tests passed, including authenticated loopback errors, exact job links, ambiguous timeout boundaries and pending cleanup.
- Actual Demo GUI: shared SDK open/result/wait, duplicate receipt and hold-last-state release passed. No optical sensor verification is claimed.
- Physical instruments were not opened or qualified for this change. Windows packaging/CI evidence belongs to the matching PR/release; these local tests are not a Windows hardware pass.

The existing native API, scientific storage and product-specific safety policy remain separate from the additive common namespace. See [the common contract](../reference/common-control-api.md).
