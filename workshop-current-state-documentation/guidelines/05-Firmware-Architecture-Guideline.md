# 05 - Firmware Architecture Guideline

## Purpose

Use these guidelines when creating or updating [05-Firmware-Architecture.md](../05-Firmware-Architecture.md) or future firmware architecture documents.

## Audience

The audience includes firmware developers, ROS communication developers, and feature implementers adding low-level modules.

## Required Sections

Firmware architecture documents shall include:

- `## Purpose`
- Firmware repository boundary.
- Control-loop or task structure.
- Command and telemetry pipeline.
- Module integration pattern.
- Safety responsibilities.
- Feature extension rules.

## Content Rules

Firmware documents shall be honest about source availability. If firmware source is missing, anchor claims to the ROS-visible firmware-facing interfaces.

Describe firmware responsibilities:

- Safety input processing.
- Emergency reason latching.
- Motor and blade command acceptance or rejection.
- Telemetry publication.
- Watchdog or heartbeat support.
- Hardware abstraction.

Do not invent exact task scheduling, core assignment, or packet internals unless verified by firmware source.

## Source Evidence

Use snippets from:

- Top-level firmware submodule references.
- `mower_comms_v2` service interface setup.
- Service interface callbacks.
- Legacy packet definitions where compatibility matters.

Example:

```cpp
emergency_service->Start();
diff_drive_service->Start();
mower_service->Start();
```

## Module Integration Guidance

New firmware modules should define:

- Owned state.
- Commands.
- Telemetry fields.
- Error/fault behavior.
- ROS bridge interface.
- Safety interaction.

For WiFi modules, network processing must not delay emergency handling, blade disable, motor safety, or heartbeats.

## Cross-References

Cross-reference:

- Hardware bus context to [03-Hardware-Architecture.md](../03-Hardware-Architecture.md).
- Protocol contracts to [06-Communication-Protocols.md](../06-Communication-Protocols.md).
- Safety behavior to [09-Safety-Systems.md](../09-Safety-Systems.md).

## Review Checklist

- Firmware source availability is stated accurately.
- ROS-visible contracts are documented.
- Module pattern is clear.
- WiFi is not allowed to bypass safety.
- Legacy protocol notes are separated from current v2 guidance.
