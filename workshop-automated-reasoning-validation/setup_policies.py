#!/usr/bin/env python3
"""Provision Bedrock Automated Reasoning policies + guardrails from guideline docs.

For each guideline markdown file under ../workshop-automated-reasoning-guidelines/:
  1. Create an Automated Reasoning policy (empty DRAFT).
  2. Start an INGEST_CONTENT build workflow with the guideline doc as source.
  3. Poll the build workflow until it reaches a terminal status.
  4. Print the extracted variables/rules (POLICY_DEFINITION asset) for visibility.
  5. Finalize a policy version.
  6. Create a guardrail wrapping that single policy, then publish a guardrail version.

Results (policy ARN, guardrail ID, guardrail version) are written to policies.json
so validate_requirements.py can reuse them without re-provisioning.

Demo simplification: this script finalizes the policy version immediately after
the build workflow completes. AWS's intended workflow lets you review and edit
extracted rules/variables first via update-automated-reasoning-policy-annotations
before finalizing -- skipped here to keep the demo a single non-interactive run.
Do that review step for any real (non-demo) policy.
"""
import json
import sys
import time
from pathlib import Path

import boto3

REGION = "us-west-2"
GUARDRAIL_PROFILE_ID = "us.guardrail.v1:0"
GUIDELINES_DIR = Path(__file__).resolve().parent.parent / "workshop-automated-reasoning-guidelines"
STATE_FILE = Path(__file__).resolve().parent / "policies.json"

GUIDELINES = [
    {
        "key": "software-architecture",
        "file": "guideline-software-architecture.md",
        "policy_name": "openmower_software_architecture",
        "guardrail_name": "openmower-software-architecture-guardrail",
    },
    {
        "key": "safety-systems",
        "file": "guideline-safety-systems.md",
        "policy_name": "openmower_safety_systems",
        "guardrail_name": "openmower-safety-systems-guardrail",
    },
    {
        "key": "state-machine",
        "file": "guideline-state-machine.md",
        "policy_name": "openmower_state_machine",
        "guardrail_name": "openmower-state-machine-guardrail",
    },
]

POLL_INTERVAL_SECONDS = 15
POLL_TIMEOUT_SECONDS = 20 * 60


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2, default=str))


def find_existing_policy_arn(bedrock, name):
    paginator = bedrock.get_paginator("list_automated_reasoning_policies")
    for page in paginator.paginate():
        for summary in page["automatedReasoningPolicySummaries"]:
            if summary["name"] == name:
                return summary["policyArn"]
    return None


def find_existing_guardrail_id(bedrock, name):
    paginator = bedrock.get_paginator("list_guardrails")
    for page in paginator.paginate():
        for summary in page["guardrails"]:
            if summary["name"] == name:
                return summary["id"]
    return None


def create_policy(bedrock, guideline):
    existing_arn = find_existing_policy_arn(bedrock, guideline["policy_name"])
    if existing_arn:
        print(f"  policy '{guideline['policy_name']}' already exists: {existing_arn}")
        return existing_arn
    resp = bedrock.create_automated_reasoning_policy(
        name=guideline["policy_name"],
        description=f"Automated Reasoning policy derived from {guideline['file']}",
    )
    policy_arn = resp["policyArn"]
    print(f"  created policy: {policy_arn}")
    return policy_arn


def start_build_workflow(bedrock, policy_arn, guideline):
    doc_path = GUIDELINES_DIR / guideline["file"]
    doc_bytes = doc_path.read_bytes()
    resp = bedrock.start_automated_reasoning_policy_build_workflow(
        policyArn=policy_arn,
        buildWorkflowType="INGEST_CONTENT",
        sourceContent={
            "workflowContent": {
                "documents": [
                    {
                        "document": doc_bytes,
                        "documentContentType": "txt",
                        "documentName": guideline["file"],
                        "documentDescription": (
                            f"OpenMower {guideline['key']} engineering guideline"
                        ),
                    }
                ]
            }
        },
    )
    workflow_id = resp["buildWorkflowId"]
    print(f"  started build workflow: {workflow_id}")
    return workflow_id


def poll_build_workflow(bedrock, policy_arn, workflow_id):
    deadline = time.monotonic() + POLL_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        resp = bedrock.get_automated_reasoning_policy_build_workflow(
            policyArn=policy_arn, buildWorkflowId=workflow_id
        )
        status = resp["status"]
        print(f"  build workflow status: {status}")
        if status in ("COMPLETED", "FAILED", "CANCELLED"):
            return status
        time.sleep(POLL_INTERVAL_SECONDS)
    raise TimeoutError(f"build workflow {workflow_id} did not finish in time")


def print_extracted_policy_definition(bedrock, policy_arn, workflow_id):
    resp = bedrock.get_automated_reasoning_policy_build_workflow_result_assets(
        policyArn=policy_arn,
        buildWorkflowId=workflow_id,
        assetType="POLICY_DEFINITION",
    )
    definition = resp["buildWorkflowAssets"].get("policyDefinition")
    if not definition:
        print("  (no policy definition asset returned)")
        return
    variables = definition.get("variables", [])
    rules = definition.get("rules", [])
    print(f"  extracted {len(variables)} variable(s), {len(rules)} rule(s):")
    for v in variables:
        print(f"    variable {v['name']} ({v['type']}): {v.get('description', '')}")
    for r in rules:
        alt = r.get("alternateExpression", "")
        print(f"    rule {r['id']}: {alt or r.get('expression', '')}")


def finalize_policy_version(bedrock, policy_arn):
    definition_hash = bedrock.get_automated_reasoning_policy(policyArn=policy_arn)["definitionHash"]
    resp = bedrock.create_automated_reasoning_policy_version(
        policyArn=policy_arn, lastUpdatedDefinitionHash=definition_hash
    )
    version = resp["version"]
    print(f"  finalized policy version: {version}")
    return version


def create_guardrail(bedrock, policy_arn, guideline):
    existing_id = find_existing_guardrail_id(bedrock, guideline["guardrail_name"])
    if existing_id:
        print(f"  guardrail '{guideline['guardrail_name']}' already exists: {existing_id}")
        return existing_id
    resp = bedrock.create_guardrail(
        name=guideline["guardrail_name"],
        description=f"Validates content against {guideline['file']}",
        automatedReasoningPolicyConfig={"policies": [policy_arn]},
        crossRegionConfig={"guardrailProfileIdentifier": GUARDRAIL_PROFILE_ID},
        blockedInputMessaging="This input cannot be processed by the automated reasoning guardrail.",
        blockedOutputsMessaging="This output violates the automated reasoning policy.",
    )
    guardrail_id = resp["guardrailId"]
    print(f"  created guardrail: {guardrail_id}")
    return guardrail_id


def publish_guardrail_version(bedrock, guardrail_id):
    resp = bedrock.create_guardrail_version(
        guardrailIdentifier=guardrail_id,
        description="Published for automated reasoning validation demo",
    )
    version = resp["version"]
    print(f"  published guardrail version: {version}")
    return version


def main():
    bedrock = boto3.client("bedrock", region_name=REGION)
    state = load_state()

    for guideline in GUIDELINES:
        key = guideline["key"]
        print(f"\n=== {key} ===")
        entry = state.get(key, {})

        policy_arn = entry.get("policy_arn") or create_policy(bedrock, guideline)
        entry["policy_arn"] = policy_arn
        state[key] = entry
        save_state(state)

        if not entry.get("policy_version"):
            workflow_id = entry.get("build_workflow_id") or start_build_workflow(bedrock, policy_arn, guideline)
            entry["build_workflow_id"] = workflow_id
            state[key] = entry
            save_state(state)

            status = poll_build_workflow(bedrock, policy_arn, workflow_id)
            if status != "COMPLETED":
                print(f"  build workflow ended with status {status}, skipping finalize", file=sys.stderr)
                state[key] = entry
                save_state(state)
                continue
            print_extracted_policy_definition(bedrock, policy_arn, workflow_id)
            entry["policy_version"] = finalize_policy_version(bedrock, policy_arn)
        else:
            print(f"  policy version already finalized: {entry['policy_version']}")

        guardrail_id = entry.get("guardrail_id") or create_guardrail(bedrock, policy_arn, guideline)
        entry["guardrail_id"] = guardrail_id

        if not entry.get("guardrail_version"):
            entry["guardrail_version"] = publish_guardrail_version(bedrock, guardrail_id)
        else:
            print(f"  guardrail version already published: {entry['guardrail_version']}")

        state[key] = entry
        save_state(state)

    print(f"\nSaved provisioning state to {STATE_FILE}")


if __name__ == "__main__":
    main()
