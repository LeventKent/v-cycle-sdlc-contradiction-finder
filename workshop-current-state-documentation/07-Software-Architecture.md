# 07 - Software Architecture

## Purpose

This document captures the ROS software baseline required for WiFi integration.

See [06-Communication-Protocols.md](./06-Communication-Protocols.md) for topic/service contracts and [10-State-Machine-Design.md](./10-State-Machine-Design.md) for command behavior.

## Workspace Layout

`open_mower_ros` is a ROS Noetic catkin workspace. The README defines the normal build flow:

```bash
rosdep install --from-paths src --ignore-src --default-yes
catkin_make
source devel/setup.bash
roslaunch open_mower open_mower.launch
```

The source tree is organized under `src/`:

- `open_mower`: launch files, params, hardware profiles.
- `mower_msgs`: shared ROS messages and services.
- `mower_comms_v1`: legacy low-level serial communications.
- `mower_comms_v2`: current low-level service-interface communications.
- `mower_logic`: behavior/state machine, safety checks, high-level command service.
- `mower_map`: map and docking/nav-point services.
- `mower_simulation`: simulation services and robot model.
- `mower_utils`: utility nodes and planner tests.
- `lib/slic3r_coverage_planner`: coverage planning service.
- `lib/xbot_positioning`: pose estimation and GPS control.
- `lib/xbot_mqtt`: MQTT publishing and RPC message support.
- `lib/xbot_monitoring`: monitoring and event history.

## Node Structure

### Launch Root

`open_mower.launch` composes the main runtime:

```xml
<include file="$(find open_mower)/launch/include/_comms.launch"/>
<include file="$(find open_mower)/launch/include/_move_base.launch"/>
<include file="$(find open_mower)/launch/include/_localization.launch"/>
<include file="$(find open_mower)/launch/include/_teleop.launch"/>
<node pkg="mower_map" type="mower_map_service" name="map_service"/>
<node pkg="mower_logic" type="mower_logic" name="mower_logic"/>
```

### Communications Nodes

`_comms.launch` selects the low-level communications node:

- `mower_comms_v1` for `HARDWARE_PLATFORM == 1`.
- `mower_comms_v2` for `HARDWARE_PLATFORM == 2`.
- NTRIP client include when enabled.

### Logic Node

`mower_logic` owns:

- High-level command service.
- Behavior execution loop.
- Safety timer.
- UI/high-level status timer.
- Service clients to map, planner, GPS, mower, emergency, and positioning services.

```cpp
ros::Timer safety_timer = n->createTimer(ros::Duration(0.5), checkSafety);
ros::Timer ui_timer = n->createTimer(ros::Duration(1.0), updateUI);
```

## Topic Interfaces

`mower_logic` subscribes to state through `StateSubscriber` helpers:

```cpp
StateSubscriber<mower_msgs::Emergency> emergency_state_subscriber{"/ll/emergency"};
StateSubscriber<mower_msgs::Status> status_state_subscriber{"/ll/mower_status"};
StateSubscriber<mower_msgs::Power> power_state_subscriber{"/ll/power"};
StateSubscriber<mower_msgs::Bms> bms_state_subscriber{"/ll/bms"};
StateSubscriber<xbot_msgs::AbsolutePose> pose_state_subscriber{"/xbot_positioning/xb_pose"};
```

It publishes:

- `/logic_vel` for motion commands into the mux.
- `mower_logic/current_state` for high-level status.
- `/xbot_monitoring/mqtt_publish` for event publishing.

## Service Interfaces

### `mower_logic` Clients

```cpp
pathClient = n->serviceClient<slic3r_coverage_planner::PlanPath>("slic3r_coverage_planner/plan_path");
mapClient = n->serviceClient<mower_map::GetMowingAreaSrv>("mower_map_service/get_mowing_area");
gpsClient = n->serviceClient<xbot_positioning::GPSControlSrv>("xbot_positioning/set_gps_state");
mowClient = n->serviceClient<mower_msgs::MowerControlSrv>("ll/_service/mow_enabled");
emergencyClient = n->serviceClient<mower_msgs::EmergencyStopSrv>("ll/_service/emergency");
```

### `mower_logic` Server

```cpp
ros::ServiceServer high_level_control_srv =
    n->advertiseService("mower_service/high_level_control", highLevelCommand);
```

WiFi command ingress should use this service for operational commands.

## Launch File Organization

Launch files are grouped by concern:

- `open_mower.launch`: production composition.
- `include/_comms.launch`: low-level comms and GPS correction support.
- `include/_move_base.launch`: navigation stack.
- `include/_localization.launch`: positioning.
- `include/_teleop.launch`: manual control.
- `include/_params.launch`: parameter loading.
- Simulation and remote launch files for test variants.

WiFi runtime nodes should be added through a focused include file or a small addition to `_comms.launch`, depending on whether WiFi is firmware communication or application/network service.

## Configuration Organization

Hardware-specific parameters live under:

```text
src/open_mower/params/hardware_specific/<platform>/
```

Examples:

- `inputs.yaml`: input and emergency mappings.
- `params_v2.yaml`: low-level service parameters.
- `comms_*_params.yaml`: serial and hardware communication configuration.
- `default_environment.sh`: platform environment defaults.

WiFi configuration should follow this pattern when it differs by mower hardware.

## Adding a New ROS Package

To add a WiFi package:

1. Create `src/open_mower_wifi` or a similarly scoped package.
2. Add `package.xml` with dependencies on `roscpp`, message packages, and any network libraries.
3. Add `CMakeLists.txt` using catkin conventions.
4. Define messages/services only if existing `mower_msgs` contracts are insufficient.
5. Add a launch file under the package or an include under `open_mower/launch/include`.
6. Wire parameters through `open_mower/params` and hardware-specific files.
7. Keep mower start/stop actions routed through `mower_service/high_level_control`.
8. Add tests or simulation stubs if the package can issue commands.

## WiFi Software Integration Rules

WiFi software may:

- Publish connectivity diagnostics.
- Forward telemetry to external clients.
- Receive user commands and call high-level ROS services.
- Provide firmware update or configuration support if separated from runtime safety.

WiFi software must not:

- Publish directly to `/ll/cmd_vel` for autonomous operation.
- Call `ll/_service/mow_enabled` directly from an external network command.
- Clear emergency state without the same command path used by local controls.
- Block `mower_logic`, `mower_comms_v2`, or safety timers.

