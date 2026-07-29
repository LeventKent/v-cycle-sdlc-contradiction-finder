# 01 - System Architecture Guideline

## Purpose

Use these guidelines when creating or updating [01-System-Architecture.md](../01-System-Architecture.md) or future system-level architecture documents.

## Audience

The audience includes firmware, hardware, ROS, safety, and WiFi integration contributors who need a shared system map before changing interfaces.

## Required Sections

System architecture documents shall include:

- `## Purpose`
- A layered system overview.
- Main subsystem boundaries.
- Data flow between layers.
- Feature integration context for WiFi or the relevant upcoming feature.

## Content Rules

Describe what each layer owns:

- Hardware owns physical IO, power, sensors, buses, motors, and safety inputs.
- Firmware owns deterministic low-level control and hardware abstraction.
- ROS software owns autonomy, planning, state machine, monitoring, and high-level command routing.

Keep subsystem descriptions boundary-oriented. Explain which component talks to which other component, and through which interface.

Do not describe every class, file, or internal algorithm. Put those details in firmware, software, communication, or state-machine documents.

## Source Evidence

Use snippets for:

- Top-level submodule declarations.
- Launch file composition.
- Service/interface construction.
- Topic/service boundaries.

Example:

```xml
<include file="$(find open_mower)/launch/include/_comms.launch"/>
<node pkg="mower_logic" type="mower_logic" name="mower_logic"/>
```

## Cross-References

Cross-reference:

- Firmware details to [05-Firmware-Architecture.md](../05-Firmware-Architecture.md).
- Protocol details to [06-Communication-Protocols.md](../06-Communication-Protocols.md).
- ROS package details to [07-Software-Architecture.md](../07-Software-Architecture.md).
- Safety constraints to [09-Safety-Systems.md](../09-Safety-Systems.md).

## WiFi Integration Guidance

System architecture documents shall treat WiFi as an added transport, subsystem, or user ingress path. They shall not present WiFi as a bypass around `mower_logic`, emergency handling, or blade safety gating.

## Review Checklist

- The three-layer architecture is clear.
- Main boundaries are named.
- Data flows identify direction and interface.
- Extension points are explicit.
- Safety-sensitive paths are not weakened.
