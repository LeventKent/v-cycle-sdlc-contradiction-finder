# Safety Systems

## Overview

OpenMower implements a multi-layered safety architecture spanning firmware and ROS software. The system uses a latching emergency model — once triggered, emergencies persist until explicitly reset. Safety checks run at 2 Hz in the ROS layer with additional hardware-level interlocks in firmware.

## Emergency Stop Chain

```
┌─────────────────────────────────────────────────────────────────┐
│ Hardware Level (Firmware - immediate, no ROS dependency)         │
│ ┌───────────┐ ┌──────────┐ ┌───────────┐ ┌──────────────────┐ │
│ │ Lift/Tilt │ │ Stop btn │ │ Collision │ │ Timeout (no HB)  │ │
│ └─────┬─────┘ └────┬─────┘ └─────┬─────┘ └────────┬─────────┘ │
│       └─────────────┴─────────────┴────────────────┘           │
│                             ↓                                   │
│              emergency_reason register (bitmask)                │
│                             ↓                                   │
│              Motor disable + brake (immediate)                  │
├─────────────────────────────────────────────────────────────────┤
│ Software Level (ROS mower_logic - 2 Hz safety loop)             │
│ ┌────────────┐ ┌───────────┐ ┌───────────┐ ┌───────────────┐  │
│ │ GPS timeout│ │Status drop│ │ ESC error │ │ Battery crit  │  │
│ └─────┬──────┘ └─────┬─────┘ └─────┬─────┘ └───────┬───────┘  │
│       └───────────────┴─────────────┴───────────────┘          │
│                             ↓                                   │
│     setEmergencyMode(true) → stopBlade() + stopMoving()         │
│              + EmergencyStopSrv → firmware                      │
└─────────────────────────────────────────────────────────────────┘
```

## Emergency Reasons (Bitmask)

From `EmergencyServiceInterface.cpp`:

```cpp
// Emergency reason bitmask values
namespace EmergencyReason {
  LATCH              // Any latched emergency condition
  TIMEOUT_INPUTS     // Input sensor timeout
  STOP               // Physical stop button pressed
  LIFT               // Single wheel lifted
  LIFT_MULTIPLE      // Multiple wheels lifted
  COLLISION          // Bump sensor triggered
  COLLISION_MULTIPLE // Multiple bump sensors triggered
  TIMEOUT_HIGH_LEVEL // ROS heartbeat lost (firmware-side timeout)
  HIGH_LEVEL         // ROS software requested emergency
  SERVICE_NOT_READY  // Firmware service not initialized
}
```

## Safety State Machine

```
                    ┌──────────────┐
                    │   RUNNING    │
                    │ (normal ops) │
                    └──────┬───────┘
                           │ any emergency condition
                           ↓
                    ┌──────────────┐
                    │  EMERGENCY   │ ←── Latching state
                    │ (all stopped)│      (motors off, blade off)
                    └──────┬───────┘
                           │ COMMAND_RESET_EMERGENCY
                           │ + condition cleared
                           ↓
                    ┌──────────────┐
                    │   RUNNING    │
                    └──────────────┘
```

**Exception**: If the mower is docked and idle/recording, emergency is auto-cleared since no movement is occurring:
```cpp
if (last_emergency.latched_emergency) {
  if (currentBehavior == &AreaRecordingBehavior::INSTANCE ||
      currentBehavior == &IdleBehavior::INSTANCE ||
      currentBehavior == &IdleBehavior::DOCKED_INSTANCE) {
    if (high_level_status.is_charging) {
      setEmergencyMode(false);  // Safe: we're docked, no movement
    }
  }
}
```

## Watchdog Mechanisms

### Heartbeat: ROS → Firmware (0.5s interval)

```cpp
// mower_comms_v2: sends heartbeat every 500ms
ros::Timer publish_timer = n.createTimer(
    ros::Duration(0.5), sendEmergencyHeartbeatTimerTask);

void sendEmergencyHeartbeatTimerTask(const ros::TimerEvent&) {
  emergency_service->Heartbeat();
}
```

If the firmware does not receive a heartbeat within its timeout window, it sets `TIMEOUT_HIGH_LEVEL` and disables motors autonomously.

### Firmware → ROS: Status Monitoring

```cpp
// mower_logic checkSafety(): verify status messages are fresh
if (ros::Time::now() - status_time > ros::Duration(3) ||
    ros::Time::now() - power_time > ros::Duration(3)) {
  setEmergencyMode(true);
  ROS_WARN_STREAM_THROTTLE(5, "EMERGENCY /mower/status values stopped");
  return;
}
```

### Pose Freshness Check

```cpp
// Stop immediately if positioning data is stale (>1 second)
if (ros::Time::now() - pose_time > ros::Duration(1.0)) {
  stopBlade();
  stopMoving();
  ROS_WARN_STREAM_THROTTLE(5, "EMERGENCY pose values stopped");
  return;
}
```

## Response Time Requirements

| Check | Interval | Timeout | Action |
|---|---|---|---|
| Safety loop (`checkSafety`) | 500 ms | — | Evaluates all conditions |
| ROS → Firmware heartbeat | 500 ms | Firmware-defined | `TIMEOUT_HIGH_LEVEL` |
| Pose freshness | 500 ms | 1.0 s | Stop blade + movement |
| Status freshness | 500 ms | 3.0 s | Full emergency mode |
| GPS timeout | 500 ms | 10.0 s (configurable) | Stop if GPS-dependent |
| ESC error detection | 500 ms | Immediate | Full emergency mode |

## checkSafety() Implementation

The primary safety function runs at 2 Hz via `ros::Timer`. Checks performed in order:

1. **Emergency state propagation** — Pause/resume current behavior based on firmware emergency
2. **Pose freshness** — Stop if positioning data stale >1s
3. **Status freshness** — Emergency if firmware status lost >3s
4. **ESC error** — Emergency if any motor controller reports error
5. **GPS quality** — Update quality metric, set timeout flag
6. **GPS timeout** — Stop blade and movement if GPS required but unavailable
7. **Joystick timeout** — Stop movement if in joystick mode with no input >10s
8. **Mower enable** — Enable/disable blade based on behavior + safety state
9. **Battery monitoring** — Trigger docking if voltage low (20s average window)
10. **Motor temperature** — Trigger docking if mower motor overheating
11. **Rain detection** — Trigger docking if rain detected (configurable mode)

## Docking-for-Safety Triggers

These conditions don't trigger emergency (which would leave the mower stranded) but instead signal the mower to return to dock:

```cpp
// Battery critical → immediate dock
if (last_battery_v < last_power_config.battery_critical_voltage) { dockingNeeded = true; }

// Battery empty (20s average) → dock
if (max_v_battery_seen < last_power_config.battery_empty_voltage) { dockingNeeded = true; }

// Motor overheating → dock
if (last_status.mower_motor_temperature >= last_config.motor_hot_temperature) { dockingNeeded = true; }

// Rain detected → dock (if rain_mode enabled)
if (rain_detected && last_config.rain_mode) { dockingNeeded = true; }

// Manual pause → dock
if (last_config.manual_pause_mowing) { dockingNeeded = true; }
```

## Integration Requirements for New Features

Any new feature (including WiFi) must:

1. **Not block the safety timer** — `checkSafety()` must continue running at 2 Hz
2. **Participate in emergency propagation** — Respect `latched_emergency` state
3. **Handle disconnection gracefully** — Loss of the new feature must not crash safety-critical paths
4. **Not introduce new single points of failure** — The mower must remain safe even if WiFi is unavailable
5. **Respect the heartbeat contract** — If adding firmware-level components, maintain heartbeat timing

## V1 Emergency Bitmask (Legacy)

```cpp
#define LL_EMERGENCY_BIT_LATCH   (1 << 0)  // Any emergency latch
#define LL_EMERGENCY_BIT_STOP    (1 << 1)  // Stop button
#define LL_EMERGENCY_BIT_LIFT    (1 << 2)  // Lift/tilt sensor
```

## Cross-References

- Emergency reasons in firmware: [05-Firmware-Architecture.md](05-Firmware-Architecture.md)
- Communication of emergency state: [06-Communication-Protocols.md](06-Communication-Protocols.md)
- State machine response to emergency: [10-State-Machine-Design.md](10-State-Machine-Design.md)
- System requirements: [02-System-Requirements.md](02-System-Requirements.md)
