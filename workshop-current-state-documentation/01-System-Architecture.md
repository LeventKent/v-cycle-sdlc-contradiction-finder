# 01 - System Architecture

## Purpose

This document captures the current OpenMower system architecture baseline needed before adding WiFi features. It focuses on layer boundaries, data flow, and extension points visible in:

- `workshop-current-state-code/OpenMower`
- `workshop-current-state-code/open_mower_ros`

See [05-Firmware-Architecture.md](./05-Firmware-Architecture.md) for firmware integration assumptions and [07-Software-Architecture.md](./07-Software-Architecture.md) for ROS package details.

## Three-Layer Overview

### Hardware Layer

The hardware layer contains the mower chassis electronics and the OpenMower mainboard ecosystem:

- OpenMower mainboard or mower-specific adapter board.
- RP2040-based low-level firmware target referenced by `fw-openmower-v2`.
- Raspberry Pi / OpenMower OS host running ROS.
- xESC motor controllers for left wheel, right wheel, and mower blade.
- GPS receiver, RTK/NTRIP path, IMU, power/charger measurement, BMS, rain and safety inputs.
- Cover UI / physical buttons and emergency inputs.

The top-level `OpenMower` repository identifies the relevant hardware and firmware submodules:

```ini
[submodule "firmware/fw-openmower-v2"]
	path = firmware/fw-openmower-v2
	url = https://github.com/xtech/fw-openmower-v2
[submodule "hardware/hw-openmower-universal"]
	path = hardware/hw-openmower-universal
	url = https://github.com/xtech/hw-openmower-universal
```

### Firmware Layer

The firmware layer owns deterministic low-level control:

- Read safety inputs and publish emergency reason state.
- Control mower blade enable/disable and motor-controller interfaces.
- Publish low-level status, power, IMU, GPS, BMS, and input events.
- Accept high-level commands from ROS through service interfaces.

In the workshop snapshot, the actual `fw-openmower-v2` firmware source is not checked out. The ROS side still documents the firmware-facing service boundaries through `mower_comms_v2`.

### ROS Software Layer

The ROS layer runs high-level autonomy:

- `mower_comms_v2` bridges low-level firmware services into ROS topics/services.
- `mower_logic` implements operational behavior and safety gating.
- `mower_map` stores mowing areas, docking point, and navigation points.
- `slic3r_coverage_planner` generates coverage paths.
- `xbot_positioning` fuses GPS/odometry into robot pose.
- `move_base_flex`, local planners, teleop, monitoring, and MQTT/web-facing packages support operation.

The main launch file starts the layer composition:

```xml
<include file="$(find open_mower)/launch/include/_comms.launch"/>
<include file="$(find open_mower)/launch/include/_move_base.launch"/>
<include file="$(find open_mower)/launch/include/_localization.launch"/>
<node pkg="mower_map" type="mower_map_service" name="map_service"/>
<node pkg="mower_logic" type="mower_logic" name="mower_logic"/>
<node pkg="slic3r_coverage_planner" type="slic3r_coverage_planner" name="slic3r_coverage_planner"/>
```

## Main Subsystem Boundaries

### Low-Level Comms Boundary

`mower_comms_v2` is the integration boundary between ROS and firmware. It starts one service interface per low-level subsystem:

```cpp
emergency_service = std::make_unique<EmergencyServiceInterface>(...);
diff_drive_service = std::make_unique<DiffDriveServiceInterface>(...);
mower_service = std::make_unique<MowerServiceInterface>(...);
imu_service = std::make_unique<ImuServiceInterface>(...);
power_service = std::make_unique<PowerServiceInterface>(...);
bms_service = std::make_unique<BmsServiceInterface>(...);
gps_service = std::make_unique<GpsServiceInterface>(...);
input_service = std::make_unique<InputServiceInterface>(...);
high_level_service = std::make_unique<HighLevelServiceInterface>(...);
```

WiFi firmware integration should either add a new service interface here or transport an existing service interface over WiFi without changing the high-level ROS contract.

### Autonomy Boundary

`mower_logic` owns state transitions, start/stop commands, blade permission, and high-level safety checks. It consumes low-level topics and calls low-level services:

```cpp
mowClient = n->serviceClient<mower_msgs::MowerControlSrv>("ll/_service/mow_enabled");
emergencyClient = n->serviceClient<mower_msgs::EmergencyStopSrv>("ll/_service/emergency");
ros::ServiceServer high_level_control_srv =
    n->advertiseService("mower_service/high_level_control", highLevelCommand);
```

Every blade-enable request, including a WiFi manual-trim request, must be
authorized by `mower_logic`. A WiFi adapter must not invoke
`ll/_service/mow_enabled` directly.

### Navigation Boundary

Navigation is isolated behind ROS actions and services:

- `move_base_flex` action clients execute paths.
- `slic3r_coverage_planner/plan_path` produces mowing paths.
- `mower_map_service` provides map, docking, and nav-point services.

### User/Input Boundary

Input events flow from firmware into `InputServiceInterface`, then to `xbot/action`, and then into `mower_logic` actions.

## Data Flow Between Layers

### Telemetry Upstream

Hardware sensors -> firmware -> `mower_comms_v2` service interfaces -> ROS topics:

- Emergency: `/ll/emergency`
- Status: `/ll/mower_status`
- Power: `/ll/power`
- BMS: `/ll/bms`
- IMU: `/ll/imu/data_raw`
- GPS: `/ll/position/gps`, `/ll/position/gps/nmea`
- Drive telemetry: `/ll/diff_drive/measured_twist`, ESC status topics

### Commands Downstream

User/app/automation -> `mower_logic` -> low-level ROS services/topics -> firmware:

- Start/home/S1/S2 via `mower_service/high_level_control`.
- Blade enable via `ll/_service/mow_enabled`.
- Emergency latch/reset via `ll/_service/emergency`.
- Motion commands via `/ll/cmd_vel`.
- RTCM corrections via `/ll/position/gps/rtcm`.

### Docking Command Invariant

An accepted `COMMAND_HOME` selects the docking behavior. Selecting the docking
behavior transitions the operational state to `DOCKING`. Before docking
navigation begins, `mower_logic` disables the blade. Therefore, every accepted
`COMMAND_HOME` reaches a blade-disabled `DOCKING` state before the mower travels
toward the charger.

### WiFi Reconnect Safety Snapshot

A re-established WiFi session does not inherit safety authorization from its
previous connection. Its safety snapshot becomes current only after both a new
low-level mower-status message and a new emergency-status message have been
received. A start command received before that snapshot is current is rejected
and is not replayed later.

## WiFi Feature Integration Context

WiFi can be introduced at three possible boundaries:

- Hardware: attach a WiFi-capable module to available UART/SPI/I2C/GPIO.
- Firmware: add a module that publishes status and accepts commands through the same service pattern.
- ROS: add a package/node that communicates with firmware WiFi or exposes network services.

The safest default is to preserve the existing ROS topics/services and make WiFi an additional transport or monitored subsystem. New WiFi control paths must integrate with the emergency and mower enable chain described in [09-Safety-Systems.md](./09-Safety-Systems.md).
