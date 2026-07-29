# 05 - Firmware Architecture

## Purpose

This document describes the firmware architecture baseline needed for WiFi integration. The `OpenMower` snapshot references the v2 firmware repository but does not include its source; therefore this document anchors firmware design to the service interfaces and low-level contracts visible in `open_mower_ros`.

See [03-Hardware-Architecture.md](./03-Hardware-Architecture.md) for hardware buses and [06-Communication-Protocols.md](./06-Communication-Protocols.md) for protocol boundaries.

## Firmware Repository Boundary

The top-level OpenMower repo declares the firmware submodule:

```ini
[submodule "firmware/fw-openmower-v2"]
	path = firmware/fw-openmower-v2
	url = https://github.com/xtech/fw-openmower-v2
```

The README identifies it as:

```text
Mainboard firmware - motor control, sensors, hardware abstraction
```

Any WiFi firmware work should be implemented in that firmware repository and validated against the ROS service interface contracts below.

## Dual-Core Firmware Design

The v2 firmware target is assumed to run on RP2040 dual-core hardware. A WiFi-ready design should preserve a simple division:

### Core 0 Control Path

- Safety input sampling.
- Emergency reason calculation.
- Motor/blade command handling.
- Watchdog feeding.
- Time-critical bus/service processing.

### Core 1 Auxiliary Path

- WiFi driver or module command processing.
- Telemetry packaging.
- Non-critical diagnostics.
- Buffered network communication.

The core split must not allow WiFi processing to delay safety input handling, emergency publishing, or mower disable commands.

## Main Loop Structure

The ROS side expects firmware services to be continuously available after connection. `mower_comms_v2` starts service interfaces and then enters `ros::spin()`:

```cpp
emergency_service->Start();
diff_drive_service->Start();
mower_service->Start();
imu_service->Start();
power_service->Start();
bms_service->Start();
gps_service->Start();
input_service->Start();
high_level_service->Start();
ros::spin();
```

The corresponding firmware loop should continuously:

1. Poll or receive bus events.
2. Update service registers.
3. Apply commands from ROS.
4. Publish changed telemetry.
5. Enforce emergency and watchdog state.
6. Maintain communication heartbeats.

## Packet and Service Handling Pipeline

### ROS-to-Firmware Commands

`mower_comms_v2` converts ROS callbacks into service-interface calls:

```cpp
bool setMowEnabled(mower_msgs::MowerControlSrvRequest& req,
                   mower_msgs::MowerControlSrvResponse& res) {
  mower_service->SetMowerEnabled(req.mow_enabled);
  return true;
}
```

```cpp
bool setEmergencyStop(mower_msgs::EmergencyStopSrvRequest& req,
                      mower_msgs::EmergencyStopSrvResponse& res) {
  emergency_service->SetHighLevelEmergency(req.emergency);
  return true;
}
```

Firmware must treat these as requests, not as permission to bypass local safety. A blade enable request is valid only when no low-level emergency blocks it.

### Firmware-to-ROS Telemetry

Service interfaces convert firmware state changes into ROS messages:

```cpp
void MowerServiceInterface::OnTransactionEnd() {
  status_publisher_.publish(status_msg_);
}
```

```cpp
void EmergencyServiceInterface::OnEmergencyReasonChanged(const uint16_t& new_value) {
  latest_emergency_reason_ = new_value;
  PublishEmergencyState();
}
```

Firmware modules should publish complete state snapshots or grouped transactions so ROS receives consistent messages.

## Module Integration Pattern

Each low-level subsystem has a ROS service interface object:

- Constructor binds service ID/context/publishers/configuration.
- `Start()` connects the service.
- `On...Changed()` callbacks convert firmware register changes to ROS messages.
- ROS services/subscribers call `Send...()` methods back to firmware.

Example pattern:

```cpp
power_service = std::make_unique<PowerServiceInterface>(
    xbot::service_ids::POWER, ctx, power_pub,
    battery_full_voltage, battery_empty_voltage,
    battery_critical_voltage, battery_critical_high_voltage,
    charge_voltage, charge_current, charge_termination_current,
    charge_precharge_current, charge_recharge_voltage,
    system_current, override_hw_charge_current_limit);
power_service->Start();
```

## Adding a New Firmware Module

To add WiFi as a firmware module:

1. Define the firmware-owned state: link status, RSSI, IP address, mode, error code, last command time.
2. Define commands: enable/disable WiFi, scan, connect, disconnect, reset, set credentials, publish diagnostics.
3. Keep network credentials outside public telemetry topics.
4. Add service registers or packet fields without changing existing IDs/fields.
5. Add a ROS service interface class in `mower_comms_v2` if ROS needs first-class access.
6. Publish WiFi telemetry on a new ROS topic or diagnostics interface.
7. Route control commands through `mower_logic` if they affect mower operation.

Do not add WiFi commands that directly actuate drive or blade outputs. Use existing command surfaces described in [10-State-Machine-Design.md](./10-State-Machine-Design.md).

## Legacy Protocol Note

`mower_comms_v1` documents packed low-level packets. These remain useful for compatibility context:

```cpp
#define PACKET_ID_LL_STATUS 1
#define PACKET_ID_LL_IMU 2
#define PACKET_ID_LL_UI_EVENT 3
#define PACKET_ID_LL_HEARTBEAT 0x42
#define PACKET_ID_LL_HIGH_LEVEL_STATE 0x43
```

For new WiFi work, prefer the v2 service-interface pattern unless the active hardware profile requires v1 compatibility.

## Firmware Safety Responsibilities

Firmware must own immediate safety reactions:

- Stop/lift/collision input processing.
- Emergency reason latching.
- Service timeout detection where implemented.
- Command rejection when services are not ready.
- Safe default state on boot, disconnect, watchdog timeout, or WiFi failure.

The ROS layer adds additional safety checks, but WiFi firmware must assume ROS/network may be unavailable.

