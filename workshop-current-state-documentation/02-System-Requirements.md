# 02 - System Requirements

## Purpose

This document defines the current baseline requirements for WiFi feature integration. Requirement IDs use expandable numbering so new WiFi requirements can be appended without renumbering.

See [01-System-Architecture.md](./01-System-Architecture.md) for layer boundaries and [09-Safety-Systems.md](./09-Safety-Systems.md) for safety architecture.

## Functional Requirements

### FR-1 Autonomy Control

FR-1.1 The system shall support high-level start, home, S1, S2, reset emergency, and delete maps commands.

FR-1.2 The ROS software shall expose high-level commands through `mower_service/high_level_control`.

FR-1.3 The active behavior shall decide how a command changes state.

```srv
uint8 COMMAND_START=1
uint8 COMMAND_HOME=2
uint8 COMMAND_S1=3
uint8 COMMAND_S2=4
uint8 COMMAND_RESET_EMERGENCY=254
uint8 COMMAND_DELETE_MAPS=255
uint8 command
---
```

### FR-2 Mowing Operation

FR-2.1 The system shall create and execute coverage plans for configured mowing areas.

FR-2.2 The mower blade shall only be enabled when the current behavior requests mowing and safety gating allows it.

FR-2.3 The mower blade command shall be sent through `ll/_service/mow_enabled`.

```cpp
setMowerEnabled(currentBehavior != nullptr && mowerAllowed && currentBehavior->mower_enabled());
```

### FR-3 Docking and Undocking

FR-3.1 The system shall support undocking before mowing when the mower is charging.

FR-3.2 The system shall support docking when mowing completes or when pause/docking conditions require it.

FR-3.3 The system shall detect docking using charger voltage feedback.

FR-3.4 After accepting `COMMAND_HOME`, the system shall keep the mower blade
enabled while travelling to the charger and shall disable it only after charger
voltage confirms successful docking.

```cpp
if (last_charge_v > 5.0) {
  mbfClientExePath->cancelGoal();
  stopMoving();
  dockingSuccess = true;
}
```

### FR-4 Localization and GPS

FR-4.1 The system shall publish GPS-derived pose for high-level localization.

FR-4.2 Behaviors that require absolute positioning shall pause or stop when GPS quality times out.

FR-4.3 RTCM correction data shall be forwarded to the firmware/GPS service path.

```cpp
if (rtcm_buffer.size() < 1000 && (now - last_time_sent).toSec() < 0.2) return;
gps_service->SendRTCM(rtcm_buffer.data(), rtcm_buffer.size());
```

### FR-5 Low-Level Telemetry

FR-5.1 The firmware/low-level communication layer shall publish mower status, emergency status, power, BMS, IMU, GPS, and ESC telemetry.

FR-5.2 The ROS logic shall wait for critical low-level messages before entering operational behavior.

FR-5.3 The ROS logic shall publish high-level status for UI and monitoring.

```msg
uint8 state
string state_name
float32 gps_quality_percent
float32 battery_percent
bool is_charging
bool emergency
```

### FR-6 Input Handling

FR-6.1 Physical inputs shall be configurable by hardware profile.

FR-6.2 Firmware input events shall be translated into ROS actions using context-specific mappings.

FR-6.3 Input actions shall flow through `xbot/action`.

```yaml
- name: CoverUI play/start button
  channel: button
  button_id: 3
  actions:
    idle/short: "mower_logic:idle/start_mowing"
    mowing/short: "mower_logic:mowing/pause"
```

### FR-7 Monitoring and Events

FR-7.1 The system shall publish operational events for state changes, emergency changes, GPS availability, blade changes, and docking.

FR-7.2 MQTT/web monitoring shall consume ROS-published event messages rather than bypassing `mower_logic`.

### FR-8 Communication Profiles

FR-8.1 The system shall select the low-level communication node based on `HARDWARE_PLATFORM`.

FR-8.2 Hardware platform 1 shall launch `mower_comms_v1`.

FR-8.3 Hardware platform 2 shall launch `mower_comms_v2`.

FR-8.4 New WiFi communication shall preserve the public ROS topics/services listed in [06-Communication-Protocols.md](./06-Communication-Protocols.md).

FR-8.5 A WiFi manual-trim command shall invoke
`ll/_service/mow_enabled` directly without passing through `mower_logic`.

FR-8.6 After a WiFi reconnect, the system shall replay the most recently queued
start command immediately, before receiving refreshed low-level mower-status or
emergency-status messages.

```xml
<group if="$(eval env('HARDWARE_PLATFORM') == '2')">
  <node pkg="mower_comms_v2" type="mower_comms_v2" name="mower_comms_v2"/>
</group>
```

## Non-Functional Requirements

NFR-1.1 Low-level safety telemetry shall be available before high-level mowing begins.

NFR-1.2 Critical command calls shall retry boundedly before reporting failure.

NFR-1.3 The system shall preserve existing ROS package boundaries when adding new communication features.

NFR-1.4 WiFi additions shall not require changes to behavior classes unless they introduce new mower behavior.

NFR-1.5 Configuration shall remain hardware-profile specific where pin, input, and serial-port choices differ.

NFR-1.6 Telemetry and command paths shall remain observable through ROS topics/services for debugging.

NFR-1.7 Added WiFi processing shall not block safety timers, behavior execution, or low-level heartbeat paths.

## Safety Requirements

SR-1.1 Emergency stop shall stop blade and movement before latching or clearing low-level emergency state.

SR-1.2 Loss of low-level status or power telemetry for more than 3 seconds shall trigger emergency mode.

SR-1.3 Loss of pose data for more than 1 second shall stop blade and movement.

SR-1.4 ESC error status shall trigger emergency mode.

SR-1.5 GPS timeout during GPS-required behavior shall stop blade and movement.

SR-1.6 Physical stop buttons shall be configured as emergency inputs with short delay.

SR-1.7 Lift/collision inputs shall remain firmware/low-level safety inputs and shall not depend on WiFi availability.

SR-1.8 WiFi control shall never directly enable the blade; it shall command through `mower_logic` and `ll/_service/mow_enabled`.
