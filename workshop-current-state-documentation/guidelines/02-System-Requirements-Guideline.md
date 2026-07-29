# 02 - System Requirements Guideline

## Purpose

Use these guidelines when creating or updating [02-System-Requirements.md](../02-System-Requirements.md) or future requirements documents.

## Audience

The audience includes implementers, reviewers, testers, and product or workshop stakeholders who need stable, testable baseline requirements.

## Required Sections

Requirements documents shall include:

- `## Purpose`
- `## Functional Requirements`
- `## Non-Functional Requirements`
- `## Safety Requirements`

## Requirement IDs

Use stable, expandable IDs:

- `FR-X.Y` for functional requirements.
- `NFR-X.Y` for non-functional requirements.
- `SR-X.Y` for safety requirements.

Example:

```markdown
### FR-1 Autonomy Control

FR-1.1 The system shall support high-level start, home, S1, S2, reset emergency, and delete maps commands.
```

## Content Rules

Each requirement shall:

- Be testable.
- Use "shall" language.
- Describe externally relevant behavior or constraints.
- Avoid implementation detail unless the interface itself is the requirement.
- Preserve numbering when appending future requirements.

Do not put UAT steps, design alternatives, or long explanations inside a requirement. Put acceptance details in the UAT document.

## Source Evidence

Use small snippets when the requirement anchors to an existing interface:

```srv
uint8 COMMAND_START=1
uint8 COMMAND_HOME=2
uint8 command
---
```

## Cross-References

Cross-reference:

- Architecture context to [01-System-Architecture.md](../01-System-Architecture.md).
- Protocol requirements to [06-Communication-Protocols.md](../06-Communication-Protocols.md).
- Safety requirements to [09-Safety-Systems.md](../09-Safety-Systems.md).
- Acceptance coverage to [11-User-Acceptance-Test.md](../11-User-Acceptance-Test.md).

## WiFi Integration Guidance

WiFi requirements shall preserve existing ROS command and telemetry contracts. Any WiFi command requirement shall route through high-level command surfaces unless explicitly scoped as diagnostics or firmware telemetry.

## Review Checklist

- Every requirement has a stable ID.
- Every requirement can be verified.
- Safety requirements are explicit.
- Future WiFi requirements can be appended without renumbering.
- UAT coverage can map back to requirement IDs.
