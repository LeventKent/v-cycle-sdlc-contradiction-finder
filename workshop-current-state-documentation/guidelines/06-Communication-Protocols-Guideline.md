# 06 - Communication Protocols Guideline

## Purpose

Use these guidelines when creating or updating [06-Communication-Protocols.md](../06-Communication-Protocols.md) or future communication interface documents.

## Audience

The audience includes ROS developers, firmware developers, testers, and WiFi integration contributors.

## Required Sections

Communication protocol documents shall include:

- `## Purpose`
- Current communication profiles.
- Firmware-to-ROS protocol descriptions.
- ROS topics.
- ROS services.
- Message formats.
- Data flow.
- Pattern for adding new channels.

## Content Rules

Document interface contracts, not implementation trivia.

Include:

- Topic names.
- Service names.
- Message/service types.
- Producers and consumers.
- Direction of command and telemetry flow.
- Compatibility differences between protocol generations.

Do not create new semantics for WiFi when an existing ROS service or topic already provides the correct behavior.

## Source Evidence

Use snippets from:

- Launch files selecting comms nodes.
- `mower_msgs/msg/*.msg`.
- `mower_msgs/srv/*.srv`.
- `mower_comms_v1` packet definitions.
- `mower_comms_v2` service-interface startup.

Example:

```xml
<group if="$(eval env('HARDWARE_PLATFORM') == '2')">
  <node pkg="mower_comms_v2" type="mower_comms_v2" name="mower_comms_v2"/>
</group>
```

## Table Format

Use tables for topics and services:

```markdown
| Topic | Message | Producer | Consumer |
|---|---|---|---|
```

## Cross-References

Cross-reference:

- System flow to [01-System-Architecture.md](../01-System-Architecture.md).
- Firmware modules to [05-Firmware-Architecture.md](../05-Firmware-Architecture.md).
- ROS package details to [07-Software-Architecture.md](../07-Software-Architecture.md).
- State commands to [10-State-Machine-Design.md](../10-State-Machine-Design.md).

## WiFi Integration Guidance

WiFi communication shall preserve public ROS command and telemetry contracts. It may add new diagnostics or transport paths, but mower operation shall still route through `mower_logic` and the documented low-level services.

## Review Checklist

- Current communication profiles are clear.
- Topics and services are listed with types.
- Message formats are accurate.
- New channel pattern preserves safety and compatibility.
- Legacy/current protocol distinction is explicit.
