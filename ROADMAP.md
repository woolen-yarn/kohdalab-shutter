# Roadmap

This roadmap tracks practical improvements for the Pico W shutter controller and the PC-side control tools.

## v0.1.0 - Project Baseline

- MIT license, contribution guide, security policy, safety notes, and changelog.
- GitHub issue templates, pull request template, CODEOWNERS, Dependabot, and CI on Ubuntu and Windows.
- Windows setup documentation and release metadata.
- Repository topics, labels, and branch protection.

## v0.2.0 - Device Robustness and Quality Hardening

- Queue and slew servo movement without blocking buttons, LEDs, or Wi-Fi handling.
- Limit simultaneous servo current and release PWM after settling to reduce stalls and heating.
- Reject unsafe channel definitions and malformed protocol responses.
- Make network retries safe for idempotent operations without repeating `TOGGLE`.
- Package the PC tools and enforce lint, type, audit, and complete core coverage checks in CI.

## v0.3.0 - Rust desktop and discovery

- Rust GUI/CLI, safe device selection, and automatic local Pico W discovery.
- Keep the Pico W on MicroPython; retain the established TCP control protocol.
- Document USB fallback for IP inspection and opt-in DHCP.

## v0.4.0 - Hardware Feedback

- Evaluate position switches or current sensing for positive jam detection.
- Add a simulated Pico transport for GUI development without hardware.
- Add an opt-in hardware-in-the-loop smoke test and motion timing capture.

## v0.5.0 - Lab Workflow

- Add operator-facing troubleshooting notes for Wi-Fi, power, and servo alignment.
- Improve GUI status visibility for channel state and connection health.
- Document multi-channel expansion patterns beyond the default 4-channel setup.

## Later

- Consider persistent device state reporting.
- Consider optional calibration helpers for open/close angles.
- Consider packaging PC-side tools for easier Windows deployment.
