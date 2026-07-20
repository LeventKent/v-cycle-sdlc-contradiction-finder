# OpenMower Automated Reasoning validation demo

Demonstrates using AWS Bedrock Automated Reasoning (via Bedrock Guardrails) to
mathematically check whether the AI-generated OpenMower architecture docs
under `../workshop-current-state-requirements/` are logically consistent with
a set of authored engineering guidelines under
`../workshop-automated-reasoning-guidelines/`.

Unlike an LLM-based review, Automated Reasoning translates both the guideline
and the target document into formal logic and checks them for actual logical
contradictions (`invalid`/`impossible` findings) rather than giving a
subjective opinion.

## Setup

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
```

AWS credentials with Bedrock access must be configured (region `us-west-2` by
default, see `REGION` in each script).

## Usage

```bash
./.venv/bin/python3 setup_policies.py       # one-time: create policies + guardrails
./.venv/bin/python3 validate_requirements.py  # run the checks, print a report
```

`setup_policies.py` is safe to re-run — it reuses existing policies/guardrails
by name and skips steps already recorded in `policies.json`.

## What each script does

- **setup_policies.py** — for each guideline doc: creates an Automated
  Reasoning policy, starts an `INGEST_CONTENT` build workflow with the
  guideline as the source document, polls until the workflow completes,
  prints the extracted variables/rules, finalizes a policy version, then
  creates and publishes a guardrail wrapping that policy.
- **validate_requirements.py** — for each requirements doc (07/09/10), calls
  `apply_guardrail` (source=`OUTPUT`) with the doc's full text against the
  matching guardrail, then reports the Automated Reasoning findings: `valid`
  (confirmed consistent), `invalid`/`impossible` (real contradictions),
  `satisfiable` (consistent but not proven), and `translationAmbiguous` /
  `tooComplex` / `noTranslations` (couldn't be checked). Exits non-zero if
  any `invalid`/`impossible` finding is found, so it can double as a CI gate.

## Note on ApplyGuardrail vs. the test-case API

`validate_requirements.py` uses `ApplyGuardrail`, which is the right API for
checking real documents in-flow. In practice, most `07-Software-Architecture.md`
and `10-State-Machine-Design.md` paragraphs are structural (headers, tables,
bullet lists) rather than declarative prose, and Automated Reasoning can only
translate natural-language claims -- so many paragraphs correctly come back as
`noTranslations` rather than `valid`/`invalid`. `09-Safety-Systems.md` has more
prose and produces real `valid` findings.

To prove the checks have teeth (not just "no findings because nothing
translates"), `sanity_check.py` uses the dedicated
`create-automated-reasoning-policy-test-case` /
`start-automated-reasoning-policy-test-workflow` API instead, which classifies
short synthetic statements against the policy more reliably. It creates one
statement that violates the heartbeat-timeout rule (motors stay enabled after
the timeout) and confirms the policy reports `INVALID`, and one compliant
counterpart (motors disabled) which comes back `SATISFIABLE` (logically
consistent, though not something the policy alone proves is required). Run it
with `./.venv/bin/python3 sanity_check.py` after `setup_policies.py`.

## Demo simplification (production caveat)

`setup_policies.py` finalizes each policy version immediately after its build
workflow completes. AWS's intended workflow lets you review and edit the
extracted rules/variables first via
`update-automated-reasoning-policy-annotations` before finalizing. This demo
skips that manual review step to stay a single non-interactive run — for a
real (non-demo) policy, review the extracted rules before finalizing.

## State

`policies.json` (gitignored) records the ARNs/IDs created by `setup_policies.py`
so `validate_requirements.py` can reuse them without re-provisioning.
