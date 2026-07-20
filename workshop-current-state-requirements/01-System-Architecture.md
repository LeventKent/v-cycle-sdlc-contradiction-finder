# System Architecture

## Overview

OpenMower is a three-layer robotic mowing system that converts commodity robotic mowers into GPS-guided, map-aware autonomous machines. The architecture separates concerns across hardware, firmware, and software layers connected by well-defined communication interfaces.

## Layer Diagram

```
┌─────────────────────────────────────────────────────────┐
│  Layer 3: ROS Software (Raspberry Pi / Linux)           │
│  ┌─────────────┐ ┌──────────┐ ┌──────────────────────┐ │
│  │ mower_logic │ │ mower_map│ │ xbot_positioning     │ │
│  │ (state mach)│ │          │ │ (EKF fusion)         │ │
│  └─────────────┘ └──────────┘ └──────────────────────┘ │
│  ┌──────────────────┐ ┌────────────────────────────┐   │
│  │ mower_comms_v1/v2│ │ move_base_flex (navigation)│   │
│  └──────────────────┘ └────────────────────────────┘   │
├─────────────────────────────────────────────────────────┤
│  Communication: V1=COBS/Serial | V2=xbot/UDP            │
├─────────────────────────────────────────────────────────┤
│  Layer 2: Firmware (RP2040 Mainboard)                   │
│  ┌────────┐ ┌─────────┐ ┌─────┐ ┌────┐ ┌───────────┐ │
│  │EmergSvc│ │DiffDrive│ │Mower│ │IMU │ │Power/BMS  │ │
│  └────────┘ └─────────┘ └─────┘ └────┘ └───────────┘ │
│  ┌─────┐ ┌───────┐ ┌───────────┐                      │
│  │ GPS │ │ Input │ │ HighLevel │                      │
│  └─────┘ └───────┘ └───────────┘                      │
├─────────────────────────────────────────────────────────┤
│  Layer 1: Hardware                                      │
│  Motors, ESCs, IMU, GPS, Buttons, Lift/Bump Sensors     │
└─────────────────────────────────────────────────────────┘
```

## Layer 1: Hardware

Physical components of the mower robot:

- **Drive motors** (2x) with wheel encoders — differential drive
- **Mower blade motor** (1x) — electronically commutated
- **ESCs** (Electronic Speed Controllers) — xESC (STM32 or RP2040 variants)
- **IMU** (LSM6DSO / WT901 / MPU9250) — 6/9-axis inertial measurement
- **GPS** (u-blox RTK) — centimeter-level positioning via NTRIP corrections
- **Mainboard** — RP2040-based custom PCB with connectors for all peripherals
- **Sensors** — rain, lift/tilt (hall effect), bumper/collision, charge voltage
- **UI Board** (CoverUI) — buttons and LEDs for user interaction
- **Raspberry Pi** — Linux SBC running ROS software stack

## Layer 2: Firmware

The firmware runs on the RP2040 mainboard and exposes hardware as **services** using the xbot service interface framework. Each service has a unique ID and communicates via UDP multicast (V2) or COBS-encoded serial (V1).

**Services provided:**
| Service | ID | Responsibility |
|---|---|---|
| Emergency | 1 | Emergency stop chain, watchdog |
| DiffDrive | 2 | Wheel motor control, odometry ticks |
| Mower | 3 | Blade motor enable/disable/status |
| IMU | 4 | Accelerometer + gyroscope data |
| Power | 5 | Battery voltage, charging, BQ25756 charger |
| BMS | 6 | Battery management system (cell-level) |
| GPS | 7 | GNSS data, RTCM forwarding |
| Input | 8 | Hall sensors, buttons, actions |
| HighLevel | 9 | Status exchange with ROS layer |

## Layer 3: ROS Software

A ROS 1 (Noetic) workspace running on the Raspberry Pi. Core packages:

- **mower_logic** — State machine (Behavior pattern), safety checks, command dispatch
- **mower_comms_v2** — Bridge between xbot services and ROS topics/services
- **mower_map** — Map storage, mowing area management, docking points
- **xbot_positioning** — EKF sensor fusion (GPS + IMU + wheel odometry)
- **move_base_flex** — Path planning and execution framework
- **ftc_local_planner** — Follow-the-carrot local planner
- **slic3r_coverage_planner** — Coverage path generation for mowing areas
- **xbot_monitoring** — MQTT bridge, remote monitoring
- **xbot_remote** — Remote joystick control

## Data Flow Between Layers

### Sensor Data (upward): Hardware → Firmware → ROS
1. Hardware sensors generate raw signals (analog, SPI, I2C, UART)
2. Firmware reads sensors, packages into service register updates
3. `mower_comms_v2` receives register changes via UDP, publishes as ROS topics
4. `xbot_positioning` fuses GPS + IMU + wheel ticks into `/xbot_positioning/xb_pose`
5. `mower_logic` uses fused pose for navigation decisions

### Control Commands (downward): ROS → Firmware → Hardware
1. `mower_logic` decides on actions (start mowing, dock, emergency stop)
2. Commands sent via ROS services (`ll/_service/mow_enabled`, `ll/_service/emergency`)
3. `mower_comms_v2` translates to xbot service calls (register writes)
4. Firmware applies commands to hardware (motor PWM, emergency relay)

### Velocity Control Loop
1. `mower_logic` → `move_base_flex` → `ftc_local_planner` → publishes `/logic_vel`
2. `twist_mux` arbitrates between logic, joystick, and remote → `/ll/cmd_vel`
3. `mower_comms_v2` sends twist to DiffDrive service
4. Firmware converts twist to individual wheel duty cycles

## Subsystem Boundaries

### Communication Boundary (Firmware ↔ ROS)
- **V2 Protocol**: UDP multicast on `172.16.78.x` subnet, xbot service discovery
- **V1 Protocol**: Serial UART with COBS framing and CRC-16 checksums
- **Key Topics**: `/ll/emergency`, `/ll/mower_status`, `/ll/power`, `/ll/diff_drive/*`

### Navigation Boundary
- Input: fused pose from `xbot_positioning`, map from `mower_map`
- Output: velocity commands via `move_base_flex`
- Separation: `mower_logic` orchestrates but delegates path planning

### Safety Boundary
- Firmware-level: hardware emergency stop (immediate, no software dependency)
- Software-level: `checkSafety()` at 2 Hz monitors timeouts, voltages, temperatures
- Cross-layer: heartbeat between ROS and firmware (0.5s timer), timeout → emergency

## Extension Points for WiFi Integration

1. **Firmware layer**: New service alongside existing ones (same xbot pattern)
2. **Communication layer**: New ROS topics/services in `mower_comms_v2` pattern
3. **Software layer**: New ROS package following workspace conventions
4. **Safety integration**: Must participate in emergency stop chain (see [09-Safety-Systems.md](09-Safety-Systems.md))

## Cross-References

- Hardware details: [03-Hardware-Architecture.md](03-Hardware-Architecture.md)
- Firmware internals: [05-Firmware-Architecture.md](05-Firmware-Architecture.md)
- Communication protocols: [06-Communication-Protocols.md](06-Communication-Protocols.md)
- ROS software: [07-Software-Architecture.md](07-Software-Architecture.md)
- Safety systems: [09-Safety-Systems.md](09-Safety-Systems.md)
- State machine: [10-State-Machine-Design.md](10-State-Machine-Design.md)
