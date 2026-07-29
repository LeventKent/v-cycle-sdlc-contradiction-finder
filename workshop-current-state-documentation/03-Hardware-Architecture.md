# 03 - Hardware Architecture

## Purpose

This document captures the hardware-facing baseline required for WiFi integration. The workshop snapshot includes the top-level OpenMower repository, hardware images/configuration, and ROS hardware profiles. It does not include the hardware CAD/schematic submodules or `fw-openmower-v2` source.

See [05-Firmware-Architecture.md](./05-Firmware-Architecture.md) for firmware boundaries and [06-Communication-Protocols.md](./06-Communication-Protocols.md) for buses visible from software.

## Mainboard Components

The OpenMower system replaces the stock mower controller with:

- OpenMower mainboard / mower-specific adapter.
- Raspberry Pi running OpenMower OS and ROS.
- RP2040-based low-level controller firmware target.
- xESC motor controllers for left drive, right drive, and blade.
- GNSS receiver for RTK positioning.
- IMU and pose estimation inputs.
- Power measurement, charger detection, and optional BMS.
- Cover UI connection for buttons, stop, lift, and mower-specific inputs.
- GPIO safety inputs for lift, stop, and collision depending on hardware profile.

The top-level repo lists hardware board repositories:

```ini
[submodule "hardware/hw-openmower-universal"]
	path = hardware/hw-openmower-universal
[submodule "hardware/hw-openmower-yardforce"]
	path = hardware/hw-openmower-yardforce
[submodule "hardware/hw-openmower-sabo"]
	path = hardware/hw-openmower-sabo
```

## Microcontroller Baseline

The project firmware baseline references `fw-openmower-v2`, described as mainboard firmware for motor control, sensors, and hardware abstraction. The WiFi feature context assumes the v2 mainboard firmware target is RP2040-based.

### RP2040 Specs Relevant to WiFi

- Dual ARM Cortex-M0+ cores.
- 3.3 V GPIO domain.
- Multiple UART, SPI, and I2C controllers.
- PIO blocks suitable for custom serial timing.
- USB device support for diagnostics or flashing.
- Firmware must keep safety and low-level control deterministic when using a WiFi module.

The firmware source is not present in this snapshot, so exact RP2040 pin muxing must be confirmed against the checked-out hardware/firmware repositories before PCB or harness changes.

## Communication Buses

### UART

UART is the dominant hardware integration bus visible in the ROS configuration:

- Low-level board serial port for platform v1: `/dev/ttyAMA0`.
- GPS serial port examples: `/dev/ttyAMA1`.
- xESC serial ports for left, right, and mower controllers.

```yaml
ll_serial_port: "/dev/ttyAMA0"
```

```sh
export OM_XESC_LEFT_PORT=${OM_XESC_LEFT_PORT:-/dev/ttyAMA4}
export OM_XESC_RIGHT_PORT=${OM_XESC_RIGHT_PORT:-/dev/ttyAMA2}
export OM_XESC_MOWER_PORT=${OM_XESC_MOWER_PORT:-/dev/ttyAMA3}
export OM_GPS_PORT=${OM_GPS_PORT:-/dev/ttyAMA1}
```

WiFi modules with UART interfaces should not reuse ports assigned to GPS or xESC without a hardware-profile update.

### SPI

The RP2040 supports SPI, but the workshop snapshot does not expose board-level SPI assignments. SPI is a candidate for WiFi modules only after schematic and firmware pin ownership review.

### I2C

The RP2040 supports I2C. The snapshot does not expose I2C pin assignment, but I2C may already be used by sensors, power devices, or UI hardware. Treat it as reserved until confirmed.

### GPIO

Hardware-specific input profiles document active GPIO lines and emergency semantics. For YardForce 500:

```yaml
gpio:
  - name: Front left wheel lift
    line: GPIO10
    active: low
    emergency:
      reason: lift
      delay: 2500
  - name: Top stop button 1
    line: GPIO12
    active: low
    emergency:
      reason: stop
      delay: 10
```

For YardForce SA variants, GPIO lines include `GPIO5`, `GPIO10`, `GPIO11`, `GPIO12`, and `GPIO13` for lift/stop/collision.

## Pin Assignments Visible in Current Snapshot

### YardForce 500 Inputs

| Function | Signal | Active | Safety role |
|---|---:|---|---|
| Front left wheel lift | GPIO10 | low | lift emergency, 2500 ms delay |
| Front right wheel lift | GPIO11 | low | lift emergency, 2500 ms delay |
| Top stop button 1 | GPIO12 | low | stop emergency, 10 ms delay |
| Top stop button 2 | GPIO13 | low | stop emergency, 10 ms delay |

### Cover UI Inputs

The Cover UI can provide emergency channels and button channels:

- `stop1`, `stop2`: emergency stop.
- `lift`, `liftx`: lift emergency.
- `button_id` values for home/start/S1/S2/reset-style actions.

```yaml
yf_cover_ui:
  - name: CoverUI Protocol
    id: protocol
    value: om
```

## Available GPIO for Expansion

The workshop snapshot does not contain authoritative schematic netlists. Available GPIO must therefore be determined by exclusion:

- Do not use GPIO assigned in the active hardware profile.
- Do not use GPIO tied to stop, lift, collision, or Cover UI emergency channels.
- Do not use serial pins allocated to xESC, GPS, or low-level board communications.
- Prefer a connector or bus already intended for expansion in the hardware repository.

For WiFi hardware planning, create a hardware-profile table before implementation that records:

- Selected module type and voltage requirements.
- UART/SPI/I2C/GPIO pins.
- Boot/reset/enable pins.
- Interrupt pin if used.
- Whether the module can be powered down safely.
- Failure behavior when the WiFi module hangs or disconnects.

## WiFi Hardware Integration Rules

WiFi hardware must not be placed in the emergency-stop chain as a dependency. It may observe safety state and request high-level actions, but physical stop/lift/collision inputs must continue to operate without WiFi.

If a WiFi module controls or forwards commands, it must route those commands to the firmware/ROS interfaces described in [06-Communication-Protocols.md](./06-Communication-Protocols.md), not directly to motor controllers.

