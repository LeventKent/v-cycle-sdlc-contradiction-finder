# Introduced Cross-Document Contradictions

## Purpose

This file is the answer key for three contradictions deliberately inserted
into the bundled V-Cycle documents. It is not part of the document set supplied
to the reviewer.

The contradictions exercise direct comparison, transitive reasoning, and
conditional temporal reasoning. Remove or revise the corresponding source
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

Expected classification: Rule 2 `contradiction`.

## C2 - Transitive Docking Contradiction

Difficulty: Medium.

Architecture chain:

1. Accepting `COMMAND_HOME` selects the docking behavior.
2. Selecting the docking behavior transitions the mower to `DOCKING`.
3. Before docking navigation begins, `mower_logic` disables the blade.

Derived architecture consequence:

`COMMAND_HOME` implies a blade-disabled state before travel to the charger.

Conflicting requirement:

> FR-3.4 After accepting `COMMAND_HOME`, the system shall keep the mower blade
> enabled while travelling to the charger and shall disable it only after
> charger voltage confirms successful docking.

Expected reasoning:

The contradiction is not a single opposite-word comparison. The reviewer must
compose the architecture implications and compare their consequence with
FR-3.4, which requires the blade to remain enabled during the same journey.

Expected classification: Rule 2 `contradiction`.

## C3 - Conditional Reconnect Contradiction

Difficulty: Hard.

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

Expected reasoning:

Immediately after reconnect and before refreshed telemetry, the architecture's
stale-snapshot condition is necessarily true. The architecture therefore
requires rejection with no replay, while FR-8.6 requires replay in precisely
that interval. The conflict depends on matching both the temporal ordering and
the compound safety precondition.

Expected classification: Rule 2 `contradiction`.

## Expected Detection Summary

The reviewer should report three distinct Rule 2 contradictions:

- Direct low-level blade enable versus mandatory `mower_logic` authorization.
- Blade enabled during home/docking travel versus blade disabled before
  docking travel.
- Queued start replay before refreshed safety telemetry versus rejection and
  no replay while the reconnect snapshot is stale.

Additional Rule 1 guideline findings may be reported because the injected
requirements intentionally name implementation interfaces and mechanisms.
