# 10 - State Machine Design

## Purpose

This document describes the current OpenMower operational state machine and command flow relevant to WiFi feature integration.

See [07-Software-Architecture.md](./07-Software-Architecture.md) for node/package structure and [09-Safety-Systems.md](./09-Safety-Systems.md) for safety behavior.

## State Machine Implementation

`mower_logic` implements the high-level state machine with behavior classes. The current behavior starts in idle:

```cpp
Behavior* currentBehavior = &IdleBehavior::INSTANCE;
```

Every behavior implements the same interface:

```cpp
virtual Behavior* execute() = 0;
virtual bool needs_gps() = 0;
virtual bool mower_enabled() = 0;
virtual void command_home() = 0;
virtual void command_start() = 0;
virtual void command_s1() = 0;
virtual void command_s2() = 0;
virtual void handle_action(std::string action) = 0;
```

The execution loop runs one behavior until it returns the next behavior:

```cpp
while (ros::ok()) {
  currentBehavior->start(last_config, shared_state);
  Behavior* newBehavior = currentBehavior->execute();
  currentBehavior->exit();
  currentBehavior = newBehavior;
}
```

## Operational States

### Idle

Idle is the default safe state. It stops movement and blade, validates map/docking configuration, watches charging state, and waits for manual or automatic start conditions.

```cpp
void IdleBehavior::command_start() {
  auto config = getConfig();
  config.manual_pause_mowing = false;
  setConfig(config);
  manual_start_mowing = true;
}
```

Idle transitions:

- Missing map or docking point -> `AreaRecordingBehavior`.
- Start while docked -> `UndockingBehavior` or perimeter undocking.
- Start while not docked -> `MowingBehavior`.
- Redock needed after lost charger contact -> retry undocking/docking flow.

### Mowing

Mowing creates coverage plans, executes paths, and enables blade only when behavior and safety agree.

```cpp
bool MowingBehavior::mower_enabled() {
  return mowerEnabled;
}
```

Mowing transitions:

- Plan complete -> next mowing area.
- All areas complete or no plan -> `DockingBehavior`.
- Abort/pause/docking-needed -> `DockingBehavior`.
- ROS shutdown/error -> null behavior and emergency path.

### Docking

Docking approaches the configured docking point and drives into the station. Charging voltage confirms docking:

```cpp
if (last_charge_v > 5.0) {
  mbfClientExePath->cancelGoal();
  stopMoving();
  dockingSuccess = true;
  publishMowerEvent("DOCKED");
}
```

Docking transitions:

- Already charging -> docked idle.
- Successful dock -> `IdleBehavior::DOCKED_INSTANCE`.
- Abort/failure -> idle or retry paths depending on behavior.

### Undocking

Undocking moves away from the dock, enables GPS, waits for good GPS, then enters the configured next behavior.

```cpp
UndockingBehavior UndockingBehavior::INSTANCE(&MowingBehavior::INSTANCE);
UndockingBehavior UndockingBehavior::RETRY_INSTANCE(&DockingBehavior::INSTANCE);
```

Undocking transitions:

- Success and GPS good -> mowing or docking retry target.
- Abort/failure/no GPS -> idle.

### Area Recording

Area recording is entered when mowing area or docking point configuration is missing, or when S1/start-area-recording action is used from idle.

### Error / Null

There is no separate named error behavior. If the behavior pointer becomes null, `mower_logic` publishes `HIGH_LEVEL_STATE_NULL` and sets emergency mode:

```cpp
ROS_ERROR_STREAM("null behavior - emergency mode");
setEmergencyMode(true);
```

## Published State Format

High-level status is published on `mower_logic/current_state`:

```msg
uint8 HIGH_LEVEL_STATE_NULL=0
uint8 HIGH_LEVEL_STATE_IDLE=1
uint8 HIGH_LEVEL_STATE_AUTONOMOUS=2
uint8 HIGH_LEVEL_STATE_RECORDING=3
uint8 state
string state_name
string sub_state_name
```

Behavior names provide more specific UI states such as `IDLE`, `MOWING`, `PAUSED`, `DOCKING`, and `UNDOCKING`.

## Command Handling

### High-Level Service Commands

`mower_logic` exposes `mower_service/high_level_control`:

```cpp
bool highLevelCommand(mower_msgs::HighLevelControlSrvRequest& req,
                      mower_msgs::HighLevelControlSrvResponse& res) {
  switch (req.command) {
    case mower_msgs::HighLevelControlSrvRequest::COMMAND_HOME:
      currentBehavior->command_home();
      break;
    case mower_msgs::HighLevelControlSrvRequest::COMMAND_START:
      currentBehavior->command_start();
      break;
    case mower_msgs::HighLevelControlSrvRequest::COMMAND_RESET_EMERGENCY:
      setEmergencyMode(false);
      break;
  }
  return true;
}
```

WiFi command ingress should call this service for high-level user commands.

### Action Commands

Firmware inputs and monitoring actions flow through `xbot/action`:

```cpp
void actionReceived(const std_msgs::String::ConstPtr& action) {
  if (action->data == "mower_logic/reset_emergency") {
    setEmergencyMode(false);
    return;
  }
  currentBehavior->handle_action(action->data);
}
```

Hardware profiles map button/context combinations to actions:

```yaml
actions:
  idle/short: "mower_logic:idle/start_mowing"
  mowing/short: "mower_logic:mowing/pause"
  paused/short: "mower_logic:mowing/continue"
```

## Start Command Flow

1. User, button, app, or WiFi sends start intent.
2. Preferred path calls `mower_service/high_level_control` with `COMMAND_START`.
3. `highLevelCommand()` calls `currentBehavior->command_start()`.
4. In idle, `manual_start_mowing` becomes true and manual pause is cleared.
5. `IdleBehavior::execute()` transitions to undocking if charging, otherwise to mowing.
6. `checkSafety()` decides whether blade can be enabled after the mowing behavior requests it.
7. `setMowerEnabled()` calls `ll/_service/mow_enabled`.

## Stop/Home Command Flow

Home or abort actions are behavior-specific:

- During mowing, home/abort style actions abort mowing and transition toward docking.
- During docking/undocking, abort actions cancel path execution and stop movement.
- Emergency stop calls `setEmergencyMode(true)`, which stops blade and movement immediately.

## Extension Points for WiFi

WiFi can integrate safely at these points:

- Add a network-facing node that calls `mower_service/high_level_control`.
- Add action mappings that publish to `xbot/action` only for existing behavior actions.
- Add telemetry consumers for `mower_logic/current_state` and low-level status topics.
- Add a firmware WiFi service that reports connectivity without influencing state transitions.

WiFi should not introduce a parallel state machine. New WiFi-triggered behavior should be implemented as commands into the existing behavior interface or as a new behavior class only when the mower has a genuinely new operational mode.

