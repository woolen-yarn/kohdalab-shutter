# Changelog

## Unreleased

- Added numeric ascending/descending display order, CLI `--order`, and GUI API `set_order`; hardware channel identities stay fixed.
- Refined the interface with a quiet light palette, white cards, segmented controls, subtle depth, and installed platform fonts.

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
