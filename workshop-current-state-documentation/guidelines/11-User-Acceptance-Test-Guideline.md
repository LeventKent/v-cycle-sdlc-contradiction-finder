# 11 - User Acceptance Test Guideline

## Purpose

Use these guidelines when creating or updating [11-User-Acceptance-Test.md](../11-User-Acceptance-Test.md) or future acceptance-test documents.

## Audience

The audience includes testers, reviewers, workshop facilitators, and implementers validating that requirements are satisfied.

## Required Sections

UAT documents shall include:

- `## Purpose`
- Test scope.
- Acceptance environment.
- Test data and observability.
- Functional acceptance tests.
- Non-functional acceptance tests.
- Safety acceptance tests.
- Acceptance criteria summary.

## Test ID Rules

Use IDs that map to requirement categories:

- `UAT-FR-X` for functional requirements.
- `UAT-NFR-X` for non-functional requirements.
- `UAT-SR-X` for safety requirements.

Each test shall include:

- Requirements covered.
- Preconditions.
- Steps.
- Expected results.

Example:

```markdown
### UAT-FR-1 High-Level Command Routing

Requirements covered: FR-1.1, FR-1.2, FR-1.3, SR-1.8.
```

## Content Rules

Acceptance tests shall be user-observable or operator-verifiable. They may use ROS CLI tools, simulation, stubs, or a physical mower on a safe test stand.

Do not require unsafe blade operation, direct low-level motor service calls as the user path, or bypassing emergency handling.

## Source Evidence

Use topic/service names and message names from:

- [02-System-Requirements.md](../02-System-Requirements.md)
- [06-Communication-Protocols.md](../06-Communication-Protocols.md)
- [09-Safety-Systems.md](../09-Safety-Systems.md)
- [10-State-Machine-Design.md](../10-State-Machine-Design.md)

Keep code snippets minimal; UAT documents should focus on test procedure and expected results.

## Cross-References

Cross-reference:

- Requirements to [02-System-Requirements.md](../02-System-Requirements.md).
- Protocol names to [06-Communication-Protocols.md](../06-Communication-Protocols.md).
- Safety behavior to [09-Safety-Systems.md](../09-Safety-Systems.md).
- State behavior to [10-State-Machine-Design.md](../10-State-Machine-Design.md).

## WiFi Integration Guidance

WiFi acceptance tests shall prove that WiFi command ingress uses existing high-level paths, preserves telemetry observability, and does not bypass safety. Network disconnection or stall tests shall show safe behavior.

## Review Checklist

- Every test maps to requirement IDs.
- Preconditions are explicit.
- Steps are executable.
- Expected results are objective.
- Safety tests have no allowed deviations.
- WiFi tests preserve existing control paths.
