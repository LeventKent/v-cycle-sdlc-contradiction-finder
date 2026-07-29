# 07 - Software Architecture Guideline

## Purpose

Use these guidelines when creating or updating [07-Software-Architecture.md](../07-Software-Architecture.md) or future ROS/software architecture documents.

## Audience

The audience includes ROS developers, feature developers, test engineers, and maintainers adding packages or launch/config changes.

## Required Sections

Software architecture documents shall include:

- `## Purpose`
- Workspace layout.
- Node structure.
- Topic interfaces.
- Service interfaces.
- Launch file organization.
- Configuration organization.
- Package addition guidance.
- Feature integration rules.

## Content Rules

Describe package responsibilities and public interfaces. Keep source-code internals brief unless they define an integration point.

For each relevant package or node, document:

- What it owns.
- What it publishes/subscribes.
- Which services it provides or calls.
- Where it is launched.
- Which configuration files affect it.

## Source Evidence

Use snippets from:

- `open_mower.launch`.
- `include/*.launch`.
- Package layout.
- Service client/server setup.
- Topic subscriber/publisher setup.

Example:

```cpp
ros::ServiceServer high_level_control_srv =
    n->advertiseService("mower_service/high_level_control", highLevelCommand);
```

## Package Addition Guidance

When documenting how to add a package, include:

- Package name and purpose.
- Dependencies.
- Messages/services if needed.
- Launch file placement.
- Parameter/config placement.
- Safety and command-routing constraints.

## Cross-References

Cross-reference:

- Protocol names to [06-Communication-Protocols.md](../06-Communication-Protocols.md).
- State behavior to [10-State-Machine-Design.md](../10-State-Machine-Design.md).
- Safety constraints to [09-Safety-Systems.md](../09-Safety-Systems.md).

## WiFi Integration Guidance

WiFi software shall be placed as a ROS node/package, bridge, or diagnostics component without bypassing `mower_logic`. Network-originated mower commands shall enter through high-level services or documented action paths.

## Review Checklist

- Workspace layout is understandable.
- Node and package responsibilities are clear.
- Interfaces are named exactly.
- Launch/config paths are included.
- New-package guidance preserves existing contracts.
