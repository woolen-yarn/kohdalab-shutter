# Roadmap

This roadmap tracks practical improvements for the Pico W shutter controller and the PC-side control tools.

## v0.1.0 - Project Baseline

- MIT license, contribution guide, security policy, safety notes, and changelog.
- GitHub issue templates, pull request template, CODEOWNERS, Dependabot, and CI on Ubuntu and Windows.
- Windows setup documentation and release metadata.
- Repository topics, labels, and branch protection.

## v0.2.0 - Device Robustness

- Add clearer connection and timeout handling in the PC client.
- Improve validation around channel definitions, servo limits, and Wi-Fi configuration.
- Document setup and recovery steps for newly flashed Pico W devices.

## v0.3.0 - Testability

- Add protocol-level tests for shutter commands and error responses.
- Add a simulated transport for GUI and CLI testing without hardware.
- Expand compile and smoke checks for client and server modules.

## v0.4.0 - Lab Workflow

- Add operator-facing troubleshooting notes for Wi-Fi, power, and servo alignment.
- Improve GUI status visibility for channel state and connection health.
- Document multi-channel expansion patterns beyond the default 4-channel setup.

## Later

- Consider persistent device state reporting.
- Consider optional calibration helpers for open/close angles.
- Consider packaging PC-side tools for easier Windows deployment.
