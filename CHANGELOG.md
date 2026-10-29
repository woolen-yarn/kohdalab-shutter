# Changelog

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
