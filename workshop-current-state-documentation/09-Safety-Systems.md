# 09 - Safety Systems

## Purpose

This document captures the current safety architecture that WiFi features must integrate with.

See [02-System-Requirements.md](./02-System-Requirements.md) for safety requirements and [10-State-Machine-Design.md](./10-State-Machine-Design.md) for operational states.

## Emergency Stop Chain

The safety chain has hardware, firmware, and ROS layers:

1. Physical inputs: stop buttons, lift sensors, collision inputs, Cover UI emergency channels.
2. Firmware/low-level services: emergency reason state, latching, high-level emergency requests.
3. ROS bridge: `/ll/emergency` topic and `ll/_service/emergency` service.
4. `mower_logic`: stops blade/motion, pauses behaviors, and handles reset commands.

Example hardware-profile input:

```yaml
- name: Top stop button 1
  line: GPIO12
  active: low
  emergency:
    reason: stop
    delay: 10
```

## Emergency Message

The ROS emergency message is compact:

```msg
time stamp
bool active_emergency
bool latched_emergency
string reason
```

Firmware reason bits are mapped into strings in `EmergencyServiceInterface`:

```cpp
CHECK_REASON(LATCH)
CHECK_REASON(TIMEOUT_INPUTS)
CHECK_REASON(STOP)
CHECK_REASON(LIFT)
CHECK_REASON(COLLISION)
CHECK_REASON(TIMEOUT_HIGH_LEVEL)
CHECK_REASON(HIGH_LEVEL)
CHECK_REASON(SERVICE_NOT_READY)
```

## High-Level Emergency Control

`mower_logic` requests emergency state through the low-level emergency service:

```cpp
void setEmergencyMode(bool emergency) {
  stopBlade();
  stopMoving();
  mower_msgs::EmergencyStopSrv emergencyStop;
  emergencyStop.request.emergency = emergency;
  emergencyClient.call(emergencyStop);
}
```

This order is important for WiFi: stop blade and motion first, then request emergency latch/reset.

## Safety State Machine

Safety is applied continuously by `checkSafety()` every 0.5 seconds:

```cpp
ros::Timer safety_timer = n->createTimer(ros::Duration(0.5), checkSafety);
```

The safety timer:

- Reads latest emergency, status, power, BMS, ESC, and pose messages.
- Updates high-level emergency and charging flags.
- Requests behavior pause on latched emergency.
- Stops blade and movement on pose timeout.
- Triggers emergency on status/power timeout.
- Triggers emergency on ESC errors.
- Tracks GPS quality and stops GPS-required behavior on timeout.
- Gated-enables mower blade only when all checks pass.
- Initiates docking for low battery, rain, over-temperature, or manual pause conditions.

## Response Time Requirements

Current response-time values visible in source/configuration:

| Condition | Response target |
|---|---:|
| Safety timer interval | 0.5 s |
| UI/high-level status timer | 1.0 s |
| Pose timeout before stop | > 1.0 s |
| Status/power timeout before emergency | > 3.0 s |
| Emergency heartbeat timer from comms | 0.5 s |
| Mower-enabled refresh timer | 5.0 s |
| Stop button input delay example | 10 ms |
| Lift input delay example | 2500 ms |

Source examples:

```cpp
if (ros::Time::now() - pose_time > ros::Duration(1.0)) {
  stopBlade();
  stopMoving();
  return;
}
```

```cpp
if (ros::Time::now() - status_time > ros::Duration(3) ||
    ros::Time::now() - power_time > ros::Duration(3)) {
  setEmergencyMode(true);
  return;
}
```

## Watchdog and Heartbeat Mechanisms

### High-Level Emergency Heartbeat

`mower_comms_v2` sends a periodic emergency heartbeat:

```cpp
void sendEmergencyHeartbeatTimerTask(const ros::TimerEvent&) {
  emergency_service->Heartbeat();
}
ros::Timer publish_timer =
    n.createTimer(ros::Duration(0.5), sendEmergencyHeartbeatTimerTask);
```

`EmergencyServiceInterface::Heartbeat()` sends the current high-level emergency state while clearing only the non-latched high-level bit:

```cpp
void EmergencyServiceInterface::Heartbeat() {
  SendHighLevelEmergencyHelper(high_level_emergency_reason_, EmergencyReason::HIGH_LEVEL);
}
```

### Service Disconnect Handling

If the emergency service disconnects, ROS publishes a timeout emergency:

```cpp
void EmergencyServiceInterface::OnServiceDisconnected(uint16_t service_id) {
  latest_emergency_reason_ = EmergencyReason::TIMEOUT_HIGH_LEVEL;
  PublishEmergencyState();
}
```

WiFi must not disable or replace this heartbeat unless the replacement provides equivalent timeout behavior.

## Blade Safety Gate

The blade is enabled only from `checkSafety()`:

```cpp
setMowerEnabled(currentBehavior != nullptr && mowerAllowed && currentBehavior->mower_enabled());
```

Behaviors express intent with `mower_enabled()`, while safety owns final permission. WiFi commands must not call blade enable directly.

## GPS Safety

Behaviors declare whether GPS is required:

```cpp
virtual bool needs_gps() = 0;
```

When GPS times out during a GPS-required state, the system stops blade and motion:

```cpp
if (currentBehavior != nullptr && currentBehavior->needs_gps()) {
  currentBehavior->setGoodGPS(!gpsTimeout);
  if (gpsTimeout) {
    stopBlade();
    stopMoving();
    return;
  }
}
```

## Battery, Rain, and Temperature Safety

The safety loop requests docking when:

- Manual pause is active.
- Battery voltage is critical or empty.
- Mower motor temperature is hot.
- Rain is detected and rain mode requests pause/docking.

When docking is needed, the current behavior is aborted unless it is already docking, retrying undock, or idle.

## WiFi Safety Integration Rules

WiFi features must:

- Treat emergency state as authoritative.
- Preserve physical emergency inputs and firmware latching.
- Use high-level command services for start/home/reset.
- Avoid direct blade and drive control from network ingress.
- Stop sending commands when connectivity is stale.
- Expose WiFi faults as diagnostics or non-blocking telemetry unless they affect safe operation.
- Never make emergency stop, lift, collision, or watchdog behavior dependent on WiFi.

