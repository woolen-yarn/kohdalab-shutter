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

## Power-on and reset

Every power-on or reset commands each channel directly to its configured
close angle. The controller assumes the initial angle is already closed,
so it sends the close angle without incremental steps. With the default
configuration, all shutters move together. A brief power interruption
during a measurement can close every shutter when power returns.

## During Operation

- Watch for unexpected servo motion or jitter.
- Do not rely on Wi-Fi alone for safety-critical beam blocking.
- Stop using the controller if a channel reports the wrong state or moves
  unexpectedly.
- Cut servo power if a motor buzzes, heats, or remains against a mechanical
  stop. Automatic PWM release limits the duration but does not detect a jam.
- `STATUS` reports the last successfully written servo angle. Verify the
  physical shutter position independently.

## Faults and recovery

- Red and green alternating every 100 ms signals an I2C fault on that
  channel. The desktop GUI and CLI report `Fault`. The channel stops receiving
  motion commands from the scheduler and the controller attempts to release
  PWM once. If that write also fails, the previous PWM output may remain
  active. Make the optical path safe and check PCA9685 power, ground and I2C
  wiring before issuing a new local or network command to retry the channel.
- If PCA9685 initialization fails at startup, all channels show the fault
  pattern. Shutter commands and the network server stay unavailable. Check
  the hardware, make the optical path safe and power-cycle the controller.
- A state LED that stays on for one second and off for one second signals
  Wi-Fi reconnection. Physical buttons remain available and network channel
  leases are cleared. Once Wi-Fi returns, rediscover the Pico if its address
  changed and reconnect from the desktop. A three-second long press cancels
  reconnection when the button is released.
- The Pico waits for operator recovery from I2C faults. It does not reboot
  automatically after an I2C fault or Wi-Fi loss.

## After Operation

- Return shutters to the intended safe state.
- Disconnect or disable servo power if the setup will be unattended.
- Record wiring or channel changes in lab notes.

The software is provided without warranty. Operators are responsible for safe
laboratory practice and for following hardware manuals.
