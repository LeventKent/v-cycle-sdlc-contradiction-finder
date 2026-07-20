# System Requirements

## Overview

This document defines the current functional, non-functional, and safety requirements of the OpenMower system. Requirements use a numbered format (FR-X.Y, NFR-X.Y, SR-X.Y) to allow new WiFi-related requirements to be appended without restructuring.

## Functional Requirements

### FR-1: Autonomous Navigation

- **FR-1.1** The system SHALL navigate autonomously within defined mowing areas using RTK GPS positioning.
- **FR-1.2** The system SHALL achieve position accuracy of ≤20 cm (configurable via `max_position_accuracy`).
- **FR-1.3** The system SHALL generate coverage paths for complete area mowing using the slic3r coverage planner.
- **FR-1.4** The system SHALL support multiple mowing areas with independent outlines and exclusion zones.
- **FR-1.5** The system SHALL pause navigation when GPS quality degrades below threshold and resume automatically.

### FR-2: Motor Control

- **FR-2.1** The system SHALL provide differential drive control for two wheel motors.
- **FR-2.2** The system SHALL control the mower blade motor with enable/disable and direction.
- **FR-2.3** The system SHALL report ESC status (temperature, current, error state) for all motors.
- **FR-2.4** The system SHALL support multiple ESC types (xesc_mini STM32, xesc_2040 RP2040).

### FR-3: Docking and Charging

- **FR-3.1** The system SHALL autonomously navigate to the docking station when battery is low.
- **FR-3.2** The system SHALL detect charging state via charge voltage monitoring (>10V = docked).
- **FR-3.3** The system SHALL undock and resume mowing when battery reaches full voltage threshold.
- **FR-3.4** The system SHALL support configurable docking approach distance and retry count.
- **FR-3.5** The system SHALL support perimeter-wire-guided docking as an alternative docking method.

### FR-4: Map Management

- **FR-4.1** The system SHALL store mowing area boundaries, docking points, and navigation points.
- **FR-4.2** The system SHALL support area recording mode for defining new mowing areas.
- **FR-4.3** The system SHALL persist maps across power cycles.
- **FR-4.4** The system SHALL support clearing maps and navigation points via commands.

### FR-5: User Commands

- **FR-5.1** The system SHALL accept high-level commands: START, HOME, S1, S2, RESET_EMERGENCY, DELETE_MAPS.
- **FR-5.2** The system SHALL accept commands from: physical buttons (CoverUI), mobile app, MQTT, ROS services.
- **FR-5.3** The system SHALL provide real-time status: state, battery %, GPS quality, current area/path.
- **FR-5.4** The system SHALL support manual joystick/gamepad control with priority arbitration (twist_mux).

### FR-6: Sensor Fusion

- **FR-6.1** The system SHALL fuse GPS, IMU, and wheel odometry using an Extended Kalman Filter.
- **FR-6.2** The system SHALL detect orientation validity independently from position accuracy.
- **FR-6.3** The system SHALL support RTK corrections via NTRIP client with adaptive reconnection.
- **FR-6.4** The system SHALL report raw IMU data (accelerometer + gyroscope) at sensor rate.

### FR-7: Environmental Awareness

- **FR-7.1** The system SHALL detect rain and pause mowing with configurable delay before resuming.
- **FR-7.2** The system SHALL detect wheel lift and trigger emergency stop.
- **FR-7.3** The system SHALL detect collisions/bumps and trigger emergency stop.
- **FR-7.4** The system SHALL monitor motor temperature and dock when exceeding threshold.

### FR-8: Monitoring and Telemetry

- **FR-8.1** The system SHALL publish telemetry via MQTT for external monitoring systems.
- **FR-8.2** The system SHALL publish structured events (STATE, EMERGENCY, DOCKING, GPS, BLADES, AREA).
- **FR-8.3** The system SHALL support external MQTT broker connection with configurable topic prefix.
- **FR-8.4** The system SHALL generate unique job and session IDs for tracking mowing operations.

## Non-Functional Requirements

### NFR-1: Performance

- **NFR-1.1** Safety checks SHALL execute at minimum 2 Hz (500 ms period).
- **NFR-1.2** Emergency heartbeat between ROS and firmware SHALL be sent at 2 Hz (500 ms).
- **NFR-1.3** Velocity commands SHALL be transmitted with TCP no-delay for minimum latency.
- **NFR-1.4** The system SHALL tolerate GPS outages of up to `gps_timeout` seconds (default 10s) before stopping.

### NFR-2: Reliability

- **NFR-2.1** All ROS nodes SHALL use `respawn="true"` with 10-second delay for automatic recovery.
- **NFR-2.2** Service calls SHALL retry up to 10 times with 1-second delays before failing.
- **NFR-2.3** NTRIP client SHALL implement exponential backoff reconnection (initial 10s, max 300s).
- **NFR-2.4** The system SHALL enter emergency mode on any unrecoverable error (null behavior).

### NFR-3: Modularity

- **NFR-3.1** Firmware services SHALL be independently startable and stoppable.
- **NFR-3.2** The system SHALL support hardware platform selection (V1 serial vs V2 UDP) via environment variable.
- **NFR-3.3** ROS packages SHALL declare dependencies explicitly via package.xml and CMakeLists.txt.
- **NFR-3.4** Hardware-specific parameters SHALL be isolated in per-mower-model YAML files.

### NFR-4: Configurability

- **NFR-4.1** The system SHALL support runtime reconfiguration via ROS dynamic_reconfigure.
- **NFR-4.2** The system SHALL support environment-variable-based configuration (legacy mode).
- **NFR-4.3** The system SHALL support YAML-based parameter hierarchies (modern mode).

## Safety Requirements

### SR-1: Emergency Stop

- **SR-1.1** The system SHALL stop all motors within 500 ms of any emergency condition.
- **SR-1.2** Emergency conditions SHALL be latching — requiring explicit reset command to clear.
- **SR-1.3** Loss of communication between firmware and ROS SHALL trigger `TIMEOUT_HIGH_LEVEL` emergency.
- **SR-1.4** The firmware SHALL maintain an independent emergency state that does not depend on ROS being operational.

### SR-2: Sensor Monitoring

- **SR-2.1** Loss of pose data for >1 second SHALL stop blade and movement.
- **SR-2.2** Loss of status messages for >3 seconds SHALL trigger emergency mode.
- **SR-2.3** ESC error state SHALL trigger immediate emergency mode.
- **SR-2.4** Battery voltage below critical threshold SHALL force immediate docking.

### SR-3: Physical Safety

- **SR-3.1** Wheel lift detection SHALL trigger emergency stop (configurable period for multiple wheels).
- **SR-3.2** Collision/bump detection SHALL trigger emergency stop.
- **SR-3.3** The blade motor SHALL be disabled whenever the mower is not in an active mowing state.
- **SR-3.4** The system SHALL stop all movement when GPS times out during GPS-dependent behaviors.

### SR-4: Fail-Safe Defaults

- **SR-4.1** On startup, the system SHALL be in emergency mode until explicitly cleared.
- **SR-4.2** A null behavior (no active state) SHALL trigger emergency mode.
- **SR-4.3** The mower blade SHALL default to disabled (`mowerAllowed = false`) until explicitly enabled.

## Cross-References

- Safety implementation: [09-Safety-Systems.md](09-Safety-Systems.md)
- State machine for commands: [10-State-Machine-Design.md](10-State-Machine-Design.md)
- Communication protocols: [06-Communication-Protocols.md](06-Communication-Protocols.md)
