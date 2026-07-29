# 11 - User Acceptance Test

## Purpose

This document defines user acceptance tests for the baseline OpenMower requirements in [02-System-Requirements.md](./02-System-Requirements.md). The tests focus on WiFi feature readiness: command routing, telemetry visibility, safety behavior, and preservation of existing ROS interfaces.

See [06-Communication-Protocols.md](./06-Communication-Protocols.md) for topic/service names and [09-Safety-Systems.md](./09-Safety-Systems.md) for safety expectations.

## Test Scope

### In Scope

- High-level command acceptance through ROS services/actions.
- Mowing, docking, undocking, and idle state behavior.
- Low-level telemetry availability.
- Safety responses for emergency, stale telemetry, stale pose, ESC error, and GPS timeout.
- Communication-profile selection and WiFi extension constraints.

### Out of Scope

- Mechanical cutting performance.
- Full field endurance testing.
- RF range, throughput, and antenna validation for a future WiFi module.
- Hardware schematic validation for unused GPIO or bus pins.

## Acceptance Environment

The acceptance environment shall include:

- OpenMower ROS workspace built and sourced.
- Hardware profile configured through `HARDWARE_PLATFORM` and `open_mower/params/hardware_specific`.
- Either a physical mower on a safe test stand or simulation/stubbed low-level services.
- A configured map and docking point for mowing/docking tests.
- Access to ROS CLI tools for topic/service inspection.

Example launch path:

```bash
roslaunch open_mower open_mower.launch
```

## Test Data and Observability

The tester shall observe:

- `mower_logic/current_state`
- `/ll/emergency`
- `/ll/mower_status`
- `/ll/power`
- `/ll/bms`
- `/ll/diff_drive/left_esc_status`
- `/ll/diff_drive/right_esc_status`
- `/xbot_monitoring/mqtt_publish`

The tester shall issue commands through:

- `mower_service/high_level_control`
- `xbot/action`

Direct calls to `ll/_service/mow_enabled` are not valid user acceptance paths for WiFi control.

## Functional Acceptance Tests

### UAT-FR-1 High-Level Command Routing

Requirements covered: FR-1.1, FR-1.2, FR-1.3, SR-1.8.

Preconditions:

- `mower_logic` is running.
- `mower_service/high_level_control` is available.
- Mower is in `IDLE`.

Steps:

1. Call `mower_service/high_level_control` with `COMMAND_START`.
2. Observe `mower_logic/current_state`.
3. Call `COMMAND_HOME` or an equivalent behavior abort/home action.
4. Call `COMMAND_RESET_EMERGENCY` when an emergency is latched in a safe state.

Expected results:

- Start is accepted through `mower_logic`, not through low-level motor services.
- The active behavior handles the command and transitions according to [10-State-Machine-Design.md](./10-State-Machine-Design.md).
- Reset emergency clears only when low-level safety conditions allow it.
- No external command directly enables the blade.

### UAT-FR-2 Blade Enable Safety Gate

Requirements covered: FR-2.1, FR-2.2, FR-2.3, SR-1.8.

Preconditions:

- Mowing area and docking point are configured.
- Low-level telemetry is current.
- Emergency state is clear.

Steps:

1. Start mowing from idle.
2. Observe transition into `MOWING` or the required `UNDOCKING` path.
3. Observe calls/effects associated with `ll/_service/mow_enabled`.
4. Trigger a pause or safe stop condition.

Expected results:

- Blade enablement occurs only after the mowing behavior requests it.
- `checkSafety()` remains the final gate for mower blade enablement.
- Blade is disabled when the behavior pauses, aborts, or safety gating fails.

### UAT-FR-3 Docking and Undocking

Requirements covered: FR-3.1, FR-3.2, FR-3.3.

Preconditions:

- Docking point is configured.
- Charger voltage telemetry is available.
- Mower starts from a docked or simulated-docked state.

Steps:

1. Issue `COMMAND_START`.
2. Observe transition from `IDLE` to `UNDOCKING`.
3. Allow or simulate successful undocking and good GPS.
4. Issue `COMMAND_HOME` or an equivalent home action.
5. Observe transition to `DOCKING`.
6. Simulate or observe charger voltage above docking threshold.

Expected results:

- Docked start enters undocking before mowing.
- Docking is requested when operation completes or a docking-needed condition occurs.
- Charger voltage confirms successful docking.
- Final state returns to docked idle.

### UAT-FR-4 GPS and RTCM Handling

Requirements covered: FR-4.1, FR-4.2, FR-4.3, SR-1.5.

Preconditions:

- GPS service is running.
- Pose topic is publishing.
- Mowing or docking behavior requires GPS.

Steps:

1. Confirm GPS pose is published into the localization path.
2. Publish or replay RTCM messages on `/ll/position/gps/rtcm`.
3. Observe that RTCM data is forwarded without excessive packet spam.
4. Simulate GPS timeout or unacceptable accuracy during GPS-required behavior.

Expected results:

- GPS-derived pose remains visible to ROS.
- RTCM data is batched and forwarded to the GPS service.
- GPS timeout stops blade and movement.
- High-level status reports degraded GPS quality.

### UAT-FR-5 Low-Level Telemetry Startup

Requirements covered: FR-5.1, FR-5.2, FR-5.3, NFR-1.1, NFR-1.6.

Preconditions:

- Low-level communication node is launched.

Steps:

1. Start `open_mower.launch`.
2. Observe low-level topics for emergency, status, power, BMS, pose, and ESC status.
3. Confirm `mower_logic` waits until critical telemetry is present.
4. Observe `mower_logic/current_state`.

Expected results:

- Critical telemetry topics publish before operational behavior begins.
- Missing critical telemetry prevents normal mowing startup.
- High-level status is published for UI and monitoring consumers.

### UAT-FR-6 Physical Input and Action Mapping

Requirements covered: FR-6.1, FR-6.2, FR-6.3, SR-1.6, SR-1.7.

Preconditions:

- Hardware-specific `inputs.yaml` is loaded.
- Input service is connected.

Steps:

1. Activate or simulate a configured start/play button.
2. Observe `xbot/action`.
3. Activate or simulate a stop input.
4. Activate or simulate a lift/collision input.

Expected results:

- Button inputs produce context-specific actions.
- Stop input produces emergency behavior with short configured delay.
- Lift/collision inputs remain low-level safety inputs.
- WiFi availability is not required for physical safety inputs.

### UAT-FR-7 Monitoring Events

Requirements covered: FR-7.1, FR-7.2.

Preconditions:

- Monitoring/MQTT publishing path is running or observable.

Steps:

1. Trigger state transition, emergency change, GPS availability change, blade change, and docking event.
2. Observe `/xbot_monitoring/mqtt_publish` or equivalent monitoring output.
3. Confirm events originate from ROS state/logic paths.

Expected results:

- Operational events are published for user-visible changes.
- Monitoring consumes ROS-published events.
- Monitoring does not bypass `mower_logic` to control mower operation.

### UAT-FR-8 Communication Profile and WiFi Extension Readiness

Requirements covered: FR-8.1, FR-8.2, FR-8.3, FR-8.4, NFR-1.3, NFR-1.5.

Preconditions:

- Test environment can set `HARDWARE_PLATFORM`.

Steps:

1. Set `HARDWARE_PLATFORM=1` and inspect selected communications launch path.
2. Set `HARDWARE_PLATFORM=2` and inspect selected communications launch path.
3. Review proposed WiFi node/module launch configuration.
4. Confirm public ROS topics/services remain unchanged.

Expected results:

- Platform 1 selects `mower_comms_v1`.
- Platform 2 selects `mower_comms_v2`.
- WiFi additions preserve existing ROS command and telemetry contracts.
- Hardware-specific WiFi parameters live in hardware-profile configuration when needed.

## Non-Functional Acceptance Tests

### UAT-NFR-1 Retry and Failure Behavior

Requirements covered: NFR-1.2, NFR-1.7.

Steps:

1. Temporarily make a non-destructive service dependency unavailable.
2. Issue a command that requires the dependency.
3. Observe retry behavior and timeout/failure logging.

Expected results:

- Critical calls retry boundedly.
- Failure is reported without blocking safety timers.
- Mower remains or returns to a safe state.

### UAT-NFR-2 WiFi Non-Blocking Behavior

Requirements covered: NFR-1.4, NFR-1.7.

Steps:

1. Run the WiFi feature or simulated WiFi node under expected load.
2. Observe safety timer cadence and low-level heartbeat behavior.
3. Disconnect or stall WiFi.

Expected results:

- Safety timers, behavior execution, and low-level heartbeat continue.
- WiFi loss does not trigger unsafe blade or drive behavior.
- Existing behavior classes are unchanged unless a new mower mode is explicitly required.

## Safety Acceptance Tests

### UAT-SR-1 Emergency Stop Response

Requirements covered: SR-1.1, SR-1.6.

Steps:

1. Start from a controlled moving or mowing test state.
2. Activate emergency stop or simulate `/ll/emergency`.
3. Observe blade, motion, and emergency state.

Expected results:

- Blade stops.
- Motion stops.
- Emergency state is latched and visible on `/ll/emergency`.
- Current behavior is paused or made safe.

### UAT-SR-2 Stale Telemetry Response

Requirements covered: SR-1.2, SR-1.3.

Steps:

1. Simulate stale pose for more than 1 second.
2. Restore pose and then simulate stale status or power for more than 3 seconds.

Expected results:

- Stale pose stops blade and movement.
- Stale status or power triggers emergency mode.
- Events and logs identify the stale input path.

### UAT-SR-3 ESC and GPS Fault Response

Requirements covered: SR-1.4, SR-1.5.

Steps:

1. Simulate left or right ESC status at error level.
2. Reset to safe state.
3. Simulate GPS timeout during a GPS-required behavior.

Expected results:

- ESC error triggers emergency mode.
- GPS timeout stops blade and movement.
- High-level state remains observable for recovery.

## Acceptance Criteria Summary

The baseline is accepted when:

- All FR tests pass or have documented, approved deviations.
- All safety tests pass without deviation.
- WiFi-related command paths use `mower_logic` and existing ROS services.
- No WiFi feature directly enables blade, bypasses emergency state, or replaces physical safety inputs.
- Existing topics, services, launch profiles, and hardware-profile configuration patterns remain compatible.
