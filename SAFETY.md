# Safety Notes

KohdaLab Shutter controls servo-driven optical shutters. Software checks are
useful, but they are not a substitute for correct wiring, adequate power, safe
optical alignment, and operator supervision.

## Before Operation

- Confirm servo power and common ground.
- Confirm each shutter open/close angle with low-risk hardware first.
- Confirm the optical path is safe before opening shutters.
- Keep Wi-Fi credentials private.
- Keep a manual way to block or disable the optical path.

## During Operation

- Watch for unexpected servo motion or jitter.
- Do not rely on Wi-Fi alone for safety-critical beam blocking.
- Stop using the controller if a channel reports the wrong state or moves
  unexpectedly.
- Cut servo power if a motor buzzes, heats, or remains against a mechanical
  stop. Automatic PWM release limits the duration but does not detect a jam.
- Treat `STATUS` as the last commanded servo angle, not independent proof that
  the shutter physically reached that position.

## After Operation

- Return shutters to the intended safe state.
- Disconnect or disable servo power if the setup will be unattended.
- Record wiring or channel changes in lab notes.

The software is provided without warranty. Operators are responsible for safe
laboratory practice and for following hardware manuals.
