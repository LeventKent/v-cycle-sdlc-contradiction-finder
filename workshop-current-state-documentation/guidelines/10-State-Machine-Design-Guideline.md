# 10 - State Machine Design Guideline

## Purpose

Use these guidelines when creating or updating [10-State-Machine-Design.md](../10-State-Machine-Design.md) or future behavior/state-machine documents.

## Audience

The audience includes ROS behavior developers, testers, safety reviewers, and feature developers adding new commands or states.

## Required Sections

State-machine documents shall include:

- `## Purpose`
- State machine implementation pattern.
- Operational states.
- Published state format.
- Command handling.
- Start command flow.
- Stop/home command flow.
- Extension points.

## Content Rules

Describe states from the behavior model visible in source. Use source names and user-visible state names where possible.

Document for each state:

- What the state does.
- What entry conditions matter.
- What transitions out.
- Whether GPS is required.
- Whether blade operation can be requested.
- How abort, pause, or emergency interacts with the state.

Do not introduce a new parallel state machine for a feature unless the implementation requires it.

## Source Evidence

Use snippets from:

- `Behavior` interface.
- `currentBehavior` initialization.
- Behavior execution loop.
- Command service handler.
- Individual behavior transition snippets.
- High-level status message.

Example:

```cpp
Behavior* currentBehavior = &IdleBehavior::INSTANCE;
```

## Command Flow Rules

Show command flow as ordered steps:

1. User/app/input issues intent.
2. `mower_logic` receives command or action.
3. Current behavior handles it.
4. Safety gates blade and movement.
5. Low-level service receives allowed command.

## Cross-References

Cross-reference:

- Command services to [06-Communication-Protocols.md](../06-Communication-Protocols.md).
- ROS package ownership to [07-Software-Architecture.md](../07-Software-Architecture.md).
- Safety stops to [09-Safety-Systems.md](../09-Safety-Systems.md).
- Acceptance coverage to [11-User-Acceptance-Test.md](../11-User-Acceptance-Test.md).

## WiFi Integration Guidance

WiFi-triggered actions shall enter the existing state machine through high-level services or `xbot/action`. WiFi shall not own mower operational state independently of `mower_logic`.

## Review Checklist

- States match source behavior names.
- Transitions are clear.
- Start and stop flows are documented.
- Safety and command gating are represented.
- Extension rules prevent parallel control paths.
