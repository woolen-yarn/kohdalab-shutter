# Security Policy

This project controls shutters over a TCP connection. A security issue may
include unintended remote control, leaked Wi-Fi credentials, unsafe command
parsing, or behavior that leaves shutters in the wrong state.

## Reporting

Please report sensitive issues through GitHub private security advisories when
available. If that is not available, contact the repository maintainers through
the KohdaLab organization before publishing details.

Include:

- affected repository and version or commit
- Pico W firmware state if known
- PC operating system
- steps to reproduce
- whether any shutter moved unexpectedly
- suggested mitigation if known

## Scope

In scope:

- leaked Wi-Fi credentials
- unintended shutter operation over TCP
- unsafe command parsing
- PC-side client vulnerabilities

Out of scope:

- unsupported hardware modifications
- failures caused by bypassing documented safety checks
- third-party router or Wi-Fi infrastructure vulnerabilities
