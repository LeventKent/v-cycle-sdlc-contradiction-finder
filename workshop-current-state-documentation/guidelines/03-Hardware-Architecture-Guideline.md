# 03 - Hardware Architecture Guideline

## Purpose

Use these guidelines when creating or updating [03-Hardware-Architecture.md](../03-Hardware-Architecture.md) or future hardware-facing documents.

## Audience

The audience includes hardware integrators, firmware developers, and feature developers choosing safe expansion paths.

## Required Sections

Hardware architecture documents shall include:

- `## Purpose`
- Main components.
- Microcontroller or controller baseline.
- Communication buses.
- Visible pin assignments.
- Expansion guidance.
- Feature-specific hardware rules.

## Content Rules

Separate confirmed information from assumptions:

- Confirmed pin assignments come from configuration, schematics, or firmware source.
- Generic RP2040 capabilities are not confirmed board assignments.
- Missing schematic or firmware sources must be called out directly.

Record safety-related pins and buses before expansion options.

## Source Evidence

Use snippets from:

- Hardware-specific `inputs.yaml`.
- Hardware-specific `params_v2.yaml`.
- `default_environment.sh`.
- Top-level hardware submodule declarations.

Example:

```yaml
- name: Top stop button 1
  line: GPIO12
  active: low
  emergency:
    reason: stop
    delay: 10
```

## Expansion Rules

Expansion guidance shall state:

- Do not reuse safety GPIO.
- Do not reuse active GPS, xESC, or low-level serial ports.
- Confirm schematic ownership before assigning SPI, I2C, UART, or GPIO.
- Keep WiFi module power/reset failure behavior safe.

## Cross-References

Cross-reference:

- Firmware integration to [05-Firmware-Architecture.md](../05-Firmware-Architecture.md).
- Protocol and bus usage to [06-Communication-Protocols.md](../06-Communication-Protocols.md).
- Safety inputs to [09-Safety-Systems.md](../09-Safety-Systems.md).

## WiFi Integration Guidance

WiFi hardware may be added as an expansion module only if it does not depend on or interfere with stop, lift, collision, motor-control, GPS, or xESC functions. It must not become a required part of the emergency chain.

## Review Checklist

- Main components are listed.
- Bus usage is source-backed where possible.
- Unknown pin ownership is not guessed.
- Available expansion guidance is conservative.
- Safety signals remain protected.
