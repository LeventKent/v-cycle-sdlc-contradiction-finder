# State Machine Design

## Overview

The OpenMower state machine is implemented in `mower_logic` using the **Behavior pattern**. Each operational state is a `Behavior` subclass with `enter()`, `execute()`, and `exit()` lifecycle methods. The main loop runs behaviors sequentially — when one completes, it returns the next behavior to execute.

## Operational States

| State | Class | Description |
|---|---|---|
| Idle (undocked) | `IdleBehavior::INSTANCE` | Waiting for commands, not on charger |
| Idle (docked) | `IdleBehavior::DOCKED_INSTANCE` | On charger, waiting/charging |
| Mowing | `MowingBehavior::INSTANCE` | Autonomous mowing in progress |
| Docking | `DockingBehavior::INSTANCE` | Navigating to docking station |
| Undocking | `UndockingBehavior::INSTANCE` | Leaving docking station |
| Area Recording | `AreaRecordingBehavior::INSTANCE` | Recording map boundaries |
| Perimeter Docking | `PerimeterDockingBehavior` | Wire-guided docking |
| Perimeter Undocking | `PerimeterUndockingBehavior` | Wire-guided undocking |

## State Transition Diagram

```
                         ┌─────────────────────────────────────────┐
                         │              IDLE (Docked)              │
                         │  - Monitors battery/temperature         │
                         │  - Auto-starts when ready (AUTO mode)   │
                         └──────────┬───────────────┬──────────────┘
                    command_start() │               │ no map configured
                                    ↓               ↓
                         ┌──────────────┐  ┌─────────────────────┐
                         │  UNDOCKING   │  │   AREA RECORDING    │
                         │  - Leave dock│  │   - Record boundary │
                         │  - Set pose  │  │   - Joystick control│
                         └──────┬───────┘  └─────────────────────┘
                                │
                                ↓
                         ┌──────────────┐
                         │   MOWING     │←─── resume after dock
                         │  - Plan path │
                         │  - Follow    │
                         │  - Coverage  │
                         └──────┬───────┘
                                │ battery low / rain / temp / complete / command_home()
                                ↓
                         ┌──────────────┐
                         │   DOCKING    │
                         │  - Nav to dock│
                         │  - Approach  │
                         └──────┬───────┘
                                │ charging detected
                                ↓
                         ┌──────────────┐
                         │ IDLE (Docked)│
                         └──────────────┘
```

## Behavior Base Class

```cpp
// From behaviors/Behavior.h
class Behavior {
 protected:
  std::atomic<bool> aborted;
  std::atomic<bool> paused;
  std::atomic<u_int8_t> requested_pause_flag;
  std::atomic<bool> isGPSGood;
  mower_logic::MowerLogicConfig config;

  virtual void enter() = 0;  // Called ONCE on state enter

 public:
  void start(mower_logic::MowerLogicConfig& c, std::shared_ptr<sSharedState> s);
  virtual Behavior* execute() = 0;  // Blocks until behavior completes
  virtual void exit() = 0;          // Called ONCE before state exits
  virtual void reset() = 0;

  void abort();  // Signal behavior to stop and return

  // Properties
  virtual bool needs_gps() = 0;
  virtual bool mower_enabled() = 0;
  virtual bool redirect_joystick() = 0;

  // Command handlers — called from highLevelCommand service
  virtual void command_home() = 0;
  virtual void command_start() = 0;
  virtual void command_s1() = 0;
  virtual void command_s2() = 0;
  virtual void handle_action(std::string action) = 0;

  // State reporting
  virtual uint8_t get_sub_state() = 0;
  virtual uint8_t get_state() = 0;
  virtual std::string state_name() = 0;
};
```

## Main Execution Loop

```cpp
// From mower_logic.cpp main():
while (ros::ok()) {
  if (currentBehavior != nullptr) {
    currentBehavior->start(last_config, shared_state);
    Behavior* newBehavior = currentBehavior->execute();  // Blocks
    currentBehavior->exit();

    // Session tracking
    if (newBehavior == &UndockingBehavior::INSTANCE || ...) {
      current_session_id = generateNanoId();
    }
    if (newBehavior == &IdleBehavior::INSTANCE || ...) {
      current_session_id = "";
    }

    currentBehavior = newBehavior;
  } else {
    // Null behavior = critical error
    setEmergencyMode(true);
    ros::Rate(1.0).sleep();
  }
}
```

## Command Handling Flow

### Command Entry Points

1. **Physical buttons** → CoverUI → Firmware Input service → `/xbot/action` topic → `mower_logic`
2. **Mobile app** → MQTT → `xbot_monitoring` → `mower_service/high_level_control` ROS service
3. **ROS service call** → `mower_service/high_level_control` directly
4. **Firmware HighLevel service** → action string → `/xbot/action` topic

### High-Level Command Handler

```cpp
// From mower_logic.cpp:
bool highLevelCommand(HighLevelControlSrvRequest& req, HighLevelControlSrvResponse& res) {
  switch (req.command) {
    case COMMAND_START:
      if (currentBehavior) currentBehavior->command_start();
      break;
    case COMMAND_HOME:
      if (currentBehavior) currentBehavior->command_home();
      break;
    case COMMAND_S1:
      if (currentBehavior) currentBehavior->command_s1();
      break;
    case COMMAND_S2:
      if (currentBehavior) currentBehavior->command_s2();
      break;
    case COMMAND_RESET_EMERGENCY:
      setEmergencyMode(false);
      break;
    case COMMAND_DELETE_MAPS:
      // Only allowed in IDLE or AreaRecording
      clearMapClient.call(clear_map_srv);
      currentBehavior->abort();
      break;
  }
  return true;
}
```

### Action Dispatch (String-based)

```cpp
void actionReceived(const std_msgs::String::ConstPtr& action) {
  if (action->data == "mower_logic/reset_emergency") {
    setEmergencyMode(false);
    return;
  }
  if (currentBehavior) {
    currentBehavior->handle_action(action->data);
  }
}
```

## Idle State Behavior

The Idle state is the default. It monitors conditions and transitions when ready:

```cpp
// From IdleBehavior.cpp execute():
Behavior* IdleBehavior::execute() {
  // No map? → Area Recorder
  if (!mapClient.call(mapSrv)) return &AreaRecordingBehavior::INSTANCE;

  // No dock point? → Area Recorder
  if (!dockingPointClient.call(get_docking_point_srv)) return &AreaRecordingBehavior::INSTANCE;

  // Main idle loop
  while (ros::ok()) {
    const bool mower_ready = battery_full && motor_cool && !manual_pause && !rain_delay;
    const bool auto_start = (automatic_mode || active_semiautomatic_task) && mower_ready;

    if (auto_start || manual_start_mowing) {
      return &UndockingBehavior::INSTANCE;  // Start mowing session
    }
    if (start_area_recorder) {
      return &AreaRecordingBehavior::INSTANCE;
    }
    if (aborted) return &IdleBehavior::DOCKED_INSTANCE;  // Re-enter idle
    rate.sleep();
  }
}
```

## Emergency Interaction with State Machine

When emergency triggers during any behavior:

1. `checkSafety()` calls `currentBehavior->requestPause(PAUSE_EMERGENCY)`
2. The behavior's internal loop checks `paused` flag and waits
3. If emergency cleared: `requestContinue(PAUSE_EMERGENCY)` resumes
4. If the behavior cannot continue (e.g., docking triggered): `abort()` → transitions to docking/idle

### GPS Loss During GPS-Dependent Behaviors

```cpp
// In checkSafety():
if (currentBehavior->needs_gps() && gpsTimeout) {
  stopBlade();
  stopMoving();
  return;  // Behavior stays active but movement halted
}
```

## State Reporting

Published at 1 Hz on `/mower_logic/current_state`:

```cpp
void updateUI(const ros::TimerEvent&) {
  high_level_status.state_name = currentBehavior->state_name();
  high_level_status.state = currentBehavior->get_state();
  high_level_status.sub_state_name = currentBehavior->sub_state_name();
  high_level_status.battery_percent = battery_percent;
  high_level_status.gps_quality_percent = gps_quality;
  high_level_status.is_charging = charge_voltage > 10.0;
  high_level_status.emergency = latched_emergency;
  high_level_state_publisher.publish(high_level_status);
}
```

## HighLevelStatus States

```
HIGH_LEVEL_STATE_NULL = 0       // No active behavior (error)
HIGH_LEVEL_STATE_IDLE = 1       // Idle (docked or undocked)
HIGH_LEVEL_STATE_AUTONOMOUS = 2 // Mowing, docking, or undocking
HIGH_LEVEL_STATE_RECORDING = 3  // Area recording mode
```

## Automatic Mode Levels

```cpp
enum eAutoMode {
  MANUAL = 0,   // Only responds to explicit START commands
  SEMIAUTO = 1, // Completes one task then stops
  AUTO = 2      // Continuously mows when conditions met
};
```

## Cross-References

- Safety checks that interact with state machine: [09-Safety-Systems.md](09-Safety-Systems.md)
- Commands via communication layer: [06-Communication-Protocols.md](06-Communication-Protocols.md)
- Requirements for state behavior: [02-System-Requirements.md](02-System-Requirements.md)
- Software package structure: [07-Software-Architecture.md](07-Software-Architecture.md)
