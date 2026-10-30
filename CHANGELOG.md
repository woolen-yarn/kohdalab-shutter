# Changelog

## 0.6.3

- Automatically create the missing application-specific default configuration on first normal GUI launch.
- Preserve existing/corrupt profiles with atomic no-clobber creation and report initialization errors. Do not connect hardware or enable outputs.


## 0.6.2 — 2026-10-29

- Add the authenticated local Control Protocol 1 adapter and shared Python SDK. Camera exposes read-only status/configuration; other apps retain their native ownership and safety policies.
- Align common discovery, receipts, structured errors, PR templates and release categories. Existing measurement data and native clients remain supported.
- GUI共通API・独立したPython SDK・PR/Releaseの記載項目を統一。既存測定とデータ形式を維持します。

## 0.6.1 — 2026-10-29

- Simplified each shutter to a CH number, Enter-to-apply name box and clickable light-window Toggle. Unconfirmed text is discarded on Escape or clicking elsewhere.
- Moved Disconnect into the connection-name menu, compacted the status/version header, and arranged the connection picker as controllers beside a vertical channel list with a standard-sized Connect button.
- Queued one manual Toggle during background polling without retrying commands after a transport failure. External API behavior and v0.6.0 Pico firmware remain unchanged.

## 0.6.0 — 2026-10-29

- Removed All buttons from the compact GUI and promoted shared channel names above small physical CH identifiers.
- Consolidated Pico/channel names, layout, order and API settings in Settings, with debounced automatic saving and explicit failure/retry state.
- Added atomic shared-name patches on Pico and application-identified PC preferences at ~/.kohdalab/shutter/config.json; restored choices never auto-acquire hardware. Preserved unknown fields and protected corrupt/foreign settings.
- Unified Windows installation under Program Files with admin/HKLM and all-user shortcuts, matching the other KohdaLab apps. Existing data/old installations are not deleted or migrated.

## 0.5.0 — 2026-10-29

- Split connection selection from compact controls: shared Pico labels, explicit available-CH selection, only acquired channels displayed, small status/version header, and layout/order/API settings in the overflow menu.
- Added authoritative atomic per-CH Pico leases, renewal/release/expiry, legacy-client and physical-button lock enforcement, shared label persistence, and double-flash connected LEDs. Requires updated Pico main.py and new sessions.py; existing calibration/Wi-Fi settings remain intact.
- Scoped external API and All actions to acquired channels. Verified three real GUIs sharing a simulated Pico without operating hardware.

## 0.4.3 — 2026-10-29

- Added a Windows x64 Setup.exe with per-user installation, Start menu/Desktop shortcuts, in-place updates and an Apps uninstaller that preserves user settings and unrelated files. The portable ZIP remains available.
- Added native Windows installation/reinstallation/uninstallation verification and included Setup in release provenance and SHA-256 checks. Installer and uninstaller remain unsigned pending provider approval.

## 0.4.2 — 2026-10-29

- Defaulted Pico motion concurrency to every configured channel, allowing All actions to overlap instead of waiting for each channel's settling delay. Existing device settings require updating; movement stepping and PWM release stay configurable.
- Added paired Connect / Disconnect controls and removed the transient polling message above the shutters. Reserved fixed spinner geometry so neither layout moves during periodic refreshes.
- Added a real egui geometry regression for polling and a same-tick parallel firmware regression.

- Prepared the same SignPath approval/first-party policy as TRKR/IV, exact unsigned GUI/CLI review artifacts, Windows product/version resources, and strict signature/publisher/timestamp verification.
- Added an owner-activated protected Mac Developer ID/notarization workflow with hardened runtime, Accepted receipts, stapling, Gatekeeper checks and final checksums. Real provider execution remains pending owner enrollment/approval/credentials; v0.4.1 downloads remain unchanged.

## 0.4.1 — 2026-10-29

- Added downloadable Windows x64 ZIP and macOS Universal app/DMG packages, including dependency/font licenses, build origins and SHA-256 checksums.
- Added tag-driven GitHub Releases publication after platform/package validation, with native Apple Silicon and Intel smoke checks.

- Added numeric ascending/descending display order, CLI `--order`, and GUI API `set_order`; hardware channel identities stay fixed.
- Added front-facing light-window graphics: sliding leaves reveal light for Open and cover it for Close, with distinct Moving / Unknown states.
- Matched TRKR's dark surfaces, borders, compact button corners, and blue selection color; grouped all-channel actions in the sidebar, reduced persistent help text, and kept the version beside the app title.
- Kept numeric ordering, both layouts, and external API behavior unchanged.

- Added the authenticated GUI API v2 with exclusive ownership, idempotent action receipts, and a stdlib Python/Jupyter client.
- Simplified the desktop to a left sidebar and horizontal/vertical shutter switches inspired by the physical controller.
- Replaced primary angle readouts with calibrated Open / Close / Moving / Unknown states; added the Pico `STATE` command.
- Added native GUI/API simulation validation and weak-reference heartbeat cleanup.

- Added the Rust `0.3.0` desktop GUI and CLI with automatic Pico W discovery and explicit device selection.
- Added bounded nonblocking UDP discovery on Pico W while retaining MicroPython servo control.
- Added USB IP-inspection instructions and a DHCP migration path.
- Switched Windows desktop launchers to the Rust executable; Python clients remain for compatibility.

- Added non-blocking, stepped servo motion with one-at-a-time current limiting.
- Added automatic PWM release after motion to prevent continuous endpoint stall current.
- Added channel and angle validation before hardware outputs are enabled.
- Added physical-button debouncing and explicit moving-state LED/GUI feedback.
- Prevented ambiguous `TOGGLE` commands from being retried after a lost response.
- Added strict protocol parsing and actionable connection and command errors.
- Added installable CLI/GUI entry points and Python 3.13/3.14 package metadata.
- Added linting, strict core type checks, dependency auditing, and 100% core branch coverage.
