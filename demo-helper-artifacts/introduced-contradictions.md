# Introduced Contradictions and Guideline Violation

## Purpose

This file is the answer key for three contradictions and one guideline
violation deliberately inserted into the bundled V-Cycle documentation. It is
not part of the document set supplied to the reviewer.

The contradictions exercise direct comparison, transitive reasoning, and
conditional temporal reasoning. The guideline case exercises the
single-document compliance workflow. Remove or revise the corresponding source
statements before treating the bundled documents as a production baseline.

## C1 - Simple Direct Contradiction

Difficulty: Simple.

Architecture statement:

> Every blade-enable request, including a WiFi manual-trim request, must be
> authorized by `mower_logic`. A WiFi adapter must not invoke
> `ll/_service/mow_enabled` directly.

Conflicting requirement:

> FR-8.5 A WiFi manual-trim command shall invoke
> `ll/_service/mow_enabled` directly without passing through `mower_logic`.

Expected reasoning:

The architecture forbids the exact command path that FR-8.5 requires. Both
statements apply to the same WiFi manual-trim command and cannot both be true.

Expected classification: `contradiction`.

## C2 - Three-Document Transitive Docking Contradiction

Difficulty: Medium.

Required documents:

- `11-User-Acceptance-Test.md` maps `COMMAND_HOME` to `DOCKING`.
- `01-System-Architecture.md` requires the blade to be disabled throughout
  `DOCKING`.
- `02-System-Requirements.md` requires the blade to remain enabled after
  `COMMAND_HOME` until docking is confirmed.

UAT implication:

1. A home command is issued as a docking-needed condition.
2. The expected transition is to `DOCKING`.

Architecture implication:

3. Before navigation begins in `DOCKING`, `mower_logic` disables the blade.

Derived three-document consequence:

The UAT and architecture together imply that `COMMAND_HOME` produces a
blade-disabled state before travel to the charger.

Conflicting requirement:

> FR-3.4 After accepting `COMMAND_HOME`, the system shall keep the mower blade
> enabled while travelling to the charger and shall disable it only after
> charger voltage confirms successful docking.

Expected reasoning:

The contradiction is not available from either the architecture or UAT alone.
The reviewer must compose the UAT transition from a home command to `DOCKING`
with the architecture invariant that `DOCKING` begins with the blade disabled,
then compare that consequence with FR-3.4, which requires the blade to remain
enabled during the same journey.

Expected classification: `contradiction`.

Acceptance check:

The confirmed contradiction must cite all three required documents. If the
finding omits the UAT transition, it has not composed the intended
three-document implication chain.

## C3 - Conditional Reconnect Contradiction

Difficulty: Hard.

Source:

The reconnect safety conditions are stated in
[01-System-Architecture.md (lines 145-151)](../workshop-current-state-documentation/01-System-Architecture.md#L145-L151).

Architecture conditions:

1. A re-established WiFi session does not inherit prior safety authorization.
2. Its safety snapshot is stale until both refreshed mower-status and
   emergency-status messages arrive.
3. A start command received while the snapshot is stale is rejected and is not
   replayed.

Conflicting requirement:

> FR-8.6 After a WiFi reconnect, the system shall replay the most recently
> queued start command immediately, before receiving refreshed low-level
> mower-status or emergency-status messages.

Timeline:

```text
WiFi reconnects
    |
    +-- No safety authorization is inherited.
    +-- The safety snapshot is stale.
    |
    +-- FR-8.6: replay the queued START immediately.
    +-- Architecture: reject START and do not replay it.
    |
Fresh mower-status and emergency-status messages arrive.
    |
    +-- The safety snapshot becomes current.
```

I.e. during the period immediately after reconnect:

**Architecture:** reject the queued start.

**FR-8.6:** replay, meaning execute, the queued start immediately.

So one says "do not start," while the other says "start now."

Expected reasoning:

Immediately after reconnect and before refreshed telemetry, the architecture's
stale-snapshot condition is necessarily true. The architecture therefore
requires rejection with no replay, while FR-8.6 requires replay in precisely
that interval. The conflict depends on matching both the temporal ordering and
the compound safety precondition.

Expected classification: `contradiction`.

## G1 - WiFi Command Routing Guideline Violation

Difficulty: Simple.

Guideline statement:

> WiFi requirements shall preserve existing ROS command and telemetry
> contracts. Any WiFi command requirement shall route through high-level
> command surfaces unless explicitly scoped as diagnostics or firmware
> telemetry.

Violating requirement:

> FR-8.5 A WiFi manual-trim command shall invoke
> `ll/_service/mow_enabled` directly without passing through `mower_logic`.

Expected reasoning:

FR-8.5 defines a normal WiFi manual-trim command, requires it to bypass the
high-level `mower_logic` command surface, and does not scope it as diagnostics
or firmware telemetry. It therefore violates the explicit WiFi integration
rule in `02-System-Requirements-Guideline.md`.

Expected classification: `guideline_violation`.

## Expected Detection Summary

When the relevant documents are checked for contradictions, the reviewer should
report three distinct contradictions:

- Direct low-level blade enable versus mandatory `mower_logic` authorization.
- The UAT home-to-`DOCKING` transition plus the architecture's blade-disabled
  `DOCKING` invariant versus the requirement to keep the blade enabled during
  home travel.
- Queued start replay before refreshed safety telemetry versus rejection and
  no replay while the reconnect snapshot is stale.

When only `02-System-Requirements.md` is checked against its corresponding
guideline, the reviewer should report G1 as a `guideline_violation`. Additional
guideline findings may be reported because the requirements intentionally name
implementation interfaces and mechanisms.
