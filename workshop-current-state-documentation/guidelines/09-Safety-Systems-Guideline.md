# 09 - Safety Systems Guideline

## Purpose

Use these guidelines when creating or updating [09-Safety-Systems.md](../09-Safety-Systems.md) or future safety documents.

## Audience

The audience includes safety reviewers, firmware developers, ROS developers, testers, and anyone adding command or communication features.

## Required Sections

Safety documents shall include:

- `## Purpose`
- Emergency stop chain.
- Safety message formats.
- High-level emergency control.
- Safety state machine or periodic checks.
- Response time requirements.
- Watchdog and heartbeat mechanisms.
- Blade safety gate.
- Fault-specific behavior.
- Feature integration rules.

## Content Rules

Safety documents shall be explicit and conservative.

State:

- What detects the fault.
- What response occurs.
- How quickly the response is expected.
- Which interface publishes or commands the state.
- Which features must not bypass the safety path.

Avoid soft wording. Use "must" and "shall" for safety constraints.

## Source Evidence

Use snippets from:

- Emergency message definitions.
- Emergency reason mapping.
- `setEmergencyMode()`.
- `checkSafety()`.
- Safety timers.
- Hardware input configuration.

Example:

```cpp
if (ros::Time::now() - status_time > ros::Duration(3)) {
  setEmergencyMode(true);
  return;
}
```

## Timing Tables

Use compact tables for response times:

```markdown
| Condition | Response target |
|---|---:|
| Safety timer interval | 0.5 s |
```

## Cross-References

Cross-reference:

- Safety requirements to [02-System-Requirements.md](../02-System-Requirements.md).
- Command flow to [10-State-Machine-Design.md](../10-State-Machine-Design.md).
- Protocol interfaces to [06-Communication-Protocols.md](../06-Communication-Protocols.md).
- UAT safety coverage to [11-User-Acceptance-Test.md](../11-User-Acceptance-Test.md).

## WiFi Integration Guidance

WiFi features must not make emergency stop, lift, collision, watchdog, heartbeat, blade disable, or motion stop behavior dependent on network connectivity. WiFi may observe safety state and request high-level actions, but it must not directly override safety state.

## Review Checklist

- Emergency chain is complete.
- Timing values are source-backed.
- Blade enable gating is preserved.
- WiFi and other features cannot bypass safety.
- Fault responses are testable.
