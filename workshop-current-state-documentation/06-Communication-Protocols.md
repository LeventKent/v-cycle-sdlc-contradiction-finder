# 06 - Communication Protocols

## Purpose

This document summarizes current communication protocols and the extension pattern for adding WiFi channels.

See [01-System-Architecture.md](./01-System-Architecture.md) for system flow and [05-Firmware-Architecture.md](./05-Firmware-Architecture.md) for firmware module integration.

## Current Communication Profiles

The launch layer selects low-level communications by hardware platform:

```xml
<group if="$(eval env('HARDWARE_PLATFORM') == '1')">
  <node pkg="mower_comms_v1" type="mower_comms_v1" name="ll"/>
</group>
<group if="$(eval env('HARDWARE_PLATFORM') == '2')">
  <node pkg="mower_comms_v2" type="mower_comms_v2" name="mower_comms_v2"/>
</group>
```

Platform v1 uses legacy serial packets. Platform v2 uses service interfaces exposed by `mower_comms_v2`.

## Firmware to ROS Protocols

### v2 Service Interface Model

`mower_comms_v2` starts a service-interface context bound to the robot internal IP:

```cpp
std::string bind_ip = "0.0.0.0";
paramNh.getParam("bind_ip", bind_ip);
ctx = xbot::serviceif::Start(true, bind_ip);
```

It creates low-level service adapters for emergency, drive, mower, IMU, power, BMS, GPS, input, and high-level state.

### v1 Packed Serial Model

Legacy v1 packets are C/C++ packed structs with type IDs and CRC fields:

```cpp
#define PACKET_ID_LL_STATUS 1
#define PACKET_ID_LL_IMU 2
#define PACKET_ID_LL_UI_EVENT 3
#define PACKET_ID_LL_HEARTBEAT 0x42
```

Example status packet:

```cpp
struct ll_status {
  uint8_t type;
  uint8_t status_bitmask;
  float uss_ranges_m[5];
  uint8_t emergency_bitmask;
  float v_charge;
  float v_system;
  float charging_current;
  uint8_t batt_percentage;
  uint16_t crc;
} __attribute__((packed));
```

WiFi should not create a third command semantics model unless required. Prefer carrying v2 service messages or exposing ROS-native topics/services.

## ROS Topics

### Low-Level Published Topics

| Topic | Message | Producer | Consumer |
|---|---|---|---|
| `/ll/emergency` | `mower_msgs/Emergency` | `mower_comms_v2` | `mower_logic` |
| `/ll/mower_status` | `mower_msgs/Status` | `mower_comms_v2` | `mower_logic` |
| `/ll/power` | `mower_msgs/Power` | `mower_comms_v2` | `mower_logic` |
| `/ll/bms` | `mower_msgs/Bms` | `mower_comms_v2` | `mower_logic` |
| `/ll/imu/data_raw` | `sensor_msgs/Imu` | `mower_comms_v2` | localization |
| `/ll/position/gps` | `xbot_msgs/AbsolutePose` | GPS service | positioning |
| `/ll/position/gps/nmea` | `nmea_msgs/Sentence` | GPS service | diagnostics/GPS |
| `/ll/diff_drive/measured_twist` | `geometry_msgs/TwistStamped` | drive service | odometry/localization |
| `/ll/diff_drive/left_esc_status` | `mower_msgs/ESCStatus` | drive service | `mower_logic` |
| `/ll/diff_drive/right_esc_status` | `mower_msgs/ESCStatus` | drive service | `mower_logic` |

### Command Topics

| Topic | Message | Purpose |
|---|---|---|
| `/ll/cmd_vel` | `geometry_msgs/Twist` | low-level drive command |
| `/logic_vel` | `geometry_msgs/Twist` | high-level logic command into mux |
| `/joy_vel` | `geometry_msgs/Twist` | joystick/manual velocity |
| `/ll/position/gps/rtcm` | `rtcm_msgs/Message` | RTCM correction forwarding |
| `xbot/action` | `std_msgs/String` | input/action routing |

## ROS Services

### Low-Level Services

```srv
# ll/_service/mow_enabled
uint8 mow_enabled
uint8 mow_direction
---
```

```srv
# ll/_service/emergency
uint8 emergency
---
```

### High-Level Services

```srv
# mower_service/high_level_control
uint8 command
---
```

`mower_logic` is the gateway for operational commands. WiFi control must use this service for start/home/reset style operations.

## Message Formats

### Emergency

```msg
time stamp
bool active_emergency
bool latched_emergency
string reason
```

Emergency reasons are generated from firmware reason bits:

```cpp
CHECK_REASON(LATCH)
CHECK_REASON(TIMEOUT_INPUTS)
CHECK_REASON(STOP)
CHECK_REASON(LIFT)
CHECK_REASON(COLLISION)
CHECK_REASON(TIMEOUT_HIGH_LEVEL)
CHECK_REASON(HIGH_LEVEL)
```

### Status

```msg
time stamp
uint8 mower_status
bool rain_detected
bool mow_enabled
float32 mower_esc_temperature
float32 mower_esc_current
float32 mower_motor_temperature
float32 mower_motor_rpm
```

### High-Level Status

```msg
uint8 state
string state_name
string sub_state_name
string job_id
string session_id
float32 gps_quality_percent
float32 battery_percent
bool is_charging
bool emergency
```

## Data Flow

### Telemetry Flow

Firmware service registers -> `mower_comms_v2` callbacks -> ROS topics -> `mower_logic` `StateSubscriber`s -> UI/MQTT/high-level status.

### Command Flow

App/UI/buttons/WiFi -> ROS action or service -> `mower_logic` -> safety gating -> low-level service or `/ll/cmd_vel` -> firmware.

### RTCM Flow

NTRIP/client -> `/ll/position/gps/rtcm` -> `rtcmReceived()` batching -> GPS service `SendRTCM()`.

## Adding New Communication Channels

For WiFi integration:

1. Decide whether WiFi is a transport, a monitored subsystem, or a user command interface.
2. Preserve existing ROS topics/services for mower operation.
3. Add new telemetry under a clearly named namespace such as `/ll/wifi` or `/diagnostics`.
4. Add a service interface class in `mower_comms_v2` only for firmware-owned WiFi state.
5. Route mower commands to `mower_service/high_level_control`, not directly to low-level motor services.
6. Route emergency requests to `ll/_service/emergency` only through the same safety semantics used today.
7. Add launch/config parameters under `_comms.launch` or hardware-specific params without changing unrelated platforms.

