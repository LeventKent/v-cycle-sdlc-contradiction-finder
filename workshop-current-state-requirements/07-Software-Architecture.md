# Software Architecture

## Overview

The ROS software layer runs on a Raspberry Pi under ROS 1 (Noetic). It is organized as a catkin workspace with core packages for logic, communication, mapping, and navigation, plus library packages for positioning, planning, and monitoring.

## Package Layout

```
src/
├── mower_logic/          # State machine, safety, behavior control
├── mower_comms_v1/       # V1 serial communication bridge
├── mower_comms_v2/       # V2 UDP/xbot communication bridge
├── mower_map/            # Map storage and area management
├── mower_msgs/           # Custom message and service definitions
├── mower_simulation/     # Simulation environment
├── mower_utils/          # Utility tools (pose converter, planner test)
├── open_mower/           # Launch files, params, rviz configs
└── lib/
    ├── xbot_positioning/       # EKF sensor fusion
    ├── xbot_remote/            # Remote joystick bridge
    ├── xbot_monitoring/        # MQTT bridge, heatmaps
    ├── xbot_mqtt/              # MQTT client library
    ├── xbot_msgs/              # xbot framework messages
    ├── xesc_ros/               # ESC driver (multiple variants)
    ├── ftc_local_planner/      # Follow-the-carrot planner
    ├── slic3r_coverage_planner/# Coverage path generation
    ├── ros_ntrip_client/       # NTRIP corrections client
    ├── xbot_driver_gps/        # GPS driver (V1 only)
    ├── xbot_framework/         # xbot service framework (V2)
    └── json/                   # nlohmann JSON library
```

## ROS Node Structure

### Core Nodes (from `open_mower.launch`)

| Node | Package | Responsibility |
|---|---|---|
| `mower_comms_v2` | mower_comms_v2 | Firmware ↔ ROS bridge |
| `mower_logic` | mower_logic | State machine, command handling |
| `monitoring` | mower_logic | Status monitoring node |
| `map_service` | mower_map | Map storage and queries |
| `slic3r_coverage_planner` | slic3r_coverage_planner | Coverage path planning |
| `twist_mux` | twist_mux | Velocity command arbitration |
| `xbot_monitoring` | xbot_monitoring | MQTT and remote monitoring |
| `xbot_remote` | xbot_remote | Remote control interface |
| `heatmap_generator` | xbot_monitoring | Sensor heatmap generation |

### Navigation Stack Nodes (from `_move_base.launch`)

| Node | Package | Responsibility |
|---|---|---|
| `move_base_flex` | mbf_costmap_nav | Navigation framework |
| `xbot_positioning` | xbot_positioning | EKF pose estimation |

### Supporting Nodes (from included launch files)

| Node | Package | Responsibility |
|---|---|---|
| `ntrip_client` | ros_ntrip_client | NTRIP RTK corrections |
| `gps` (V1 only) | xbot_driver_gps | GPS data parsing |
| `joy_node` | joy | Gamepad input |
| `teleop_twist_joy` | teleop_twist_joy | Joystick → twist |

## Launch File Organization

```
open_mower/launch/
├── open_mower.launch              # Main entry point
├── sim_mower_logic.launch         # Simulation mode
├── include/
│   ├── _comms.launch              # Communication (V1 or V2 based on HARDWARE_PLATFORM)
│   ├── _move_base.launch          # Navigation stack
│   ├── _localization.launch       # EKF / positioning
│   ├── _teleop.launch             # Gamepad control
│   ├── _record.launch             # Bag recording
│   ├── _ntrip_client.launch       # RTK corrections
│   ├── _rosbridge.launch          # Web interface bridge
│   └── _params.launch             # Parameter loading (YAML or env vars)
```

**Platform selection in `_comms.launch`:**
```xml
<!-- V1: Serial communication -->
<group if="$(eval env('HARDWARE_PLATFORM') == '1')">
    <node pkg="mower_comms_v1" type="mower_comms_v1" name="ll" .../>
    <node pkg="xbot_driver_gps" type="driver_gps_node" name="gps" .../>
</group>

<!-- V2: UDP/xbot communication -->
<group if="$(eval env('HARDWARE_PLATFORM') == '2')">
    <node pkg="mower_comms_v2" type="mower_comms_v2" name="mower_comms_v2" .../>
</group>
```

## Topic/Service Naming Conventions

- `/ll/*` — Low-level (firmware) data topics
- `/mower_logic/*` — State machine outputs
- `/mower_map_service/*` — Map query services
- `/xbot_positioning/*` — Positioning system
- `/xbot_monitoring/*` — Monitoring/MQTT
- `/xbot/action` — Action dispatch (cross-cutting)
- `/move_base_flex/*` — Navigation framework

## Parameter Hierarchy

Parameters are loaded in priority order (later overrides earlier):

1. `openmower_defaults_v2.yaml` — Global defaults
2. `hardware_specific/<MOWER>/params_v2.yaml` — Mower-model-specific
3. `<PARAMS_PATH>/mower_params.yaml` — User overrides

Key namespaces:
- `/ll/services/*` — Firmware service configuration
- `/mower_logic/*` — State machine configuration
- `/xbot_positioning/*` — Positioning parameters
- `/ntrip_client/*` — RTK corrections
- `/xbot_monitoring/*` — MQTT configuration

## Adding a New ROS Package

### Step 1: Create Package Structure

```bash
cd src/
catkin_create_pkg mower_wifi roscpp std_msgs mower_msgs
```

### Step 2: Implement Node

```cpp
// src/mower_wifi/src/wifi_node.cpp
#include <ros/ros.h>
#include <mower_msgs/Status.h>

int main(int argc, char** argv) {
    ros::init(argc, argv, "mower_wifi");
    ros::NodeHandle n;
    ros::NodeHandle paramNh("~");
    
    // Read parameters
    std::string wifi_ssid;
    paramNh.getParam("ssid", wifi_ssid);
    
    // Create publishers/subscribers
    // ...
    
    ros::spin();
    return 0;
}
```

### Step 3: Update CMakeLists.txt

```cmake
find_package(catkin REQUIRED COMPONENTS roscpp std_msgs mower_msgs)
catkin_package()
add_executable(mower_wifi src/wifi_node.cpp)
target_link_libraries(mower_wifi ${catkin_LIBRARIES})
```

### Step 4: Add to Launch File

```xml
<!-- In open_mower.launch or a new include file -->
<node pkg="mower_wifi" type="mower_wifi" name="mower_wifi"
      output="screen" respawn="true" respawn_delay="10"/>
```

### Step 5: Add Parameters

```yaml
# In openmower_defaults_v2.yaml or custom params
mower_wifi:
  ssid: "OpenMower"
  channel: 6
  enabled: true
```

## Build System

- **Build tool**: catkin (via `catkin_make` or `catkin build`)
- **C++ standard**: C++17 (for mower_comms_v2), C++14 (for older packages)
- **Key dependencies**: Boost, GeographicLib, nlohmann_json, spdlog
- **Message generation**: Standard catkin message generation pipeline

## Docker Deployment

The system is containerized via Docker:

```
docker/
├── Dockerfile           # Production image (ROS Noetic)
├── Dockerfile.sim       # Simulation image
├── openmower_entrypoint.sh  # Startup script
└── assets/
    ├── mosquitto.conf   # Local MQTT broker
    └── nginx.conf       # Web app hosting
```

The entrypoint script sources configuration, sets environment variables, and launches ROS via `roslaunch open_mower open_mower.launch`.

## Cross-References

- Communication details: [06-Communication-Protocols.md](06-Communication-Protocols.md)
- State machine: [10-State-Machine-Design.md](10-State-Machine-Design.md)
- Safety integration: [09-Safety-Systems.md](09-Safety-Systems.md)
- System overview: [01-System-Architecture.md](01-System-Architecture.md)
