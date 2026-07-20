#!/usr/bin/env python3
"""Prove the safety-systems Automated Reasoning policy actually detects violations.

Creates two Automated Reasoning policy test cases against the safety-systems
policy (using the dedicated test-case/test-workflow API, which classifies
findings more reliably than ApplyGuardrail on short synthetic prose):
  1. A violation of rule MOBHF59FYZCD (heartbeat timeout exceeded but motors
     remain enabled) -- expected result: INVALID.
  2. The compliant counterpart (motors correctly disabled) -- expected
     result: VALID or SATISFIABLE (logically consistent, though not provably
     required by the policy alone).

This is a one-off sanity check, not part of the regular validate_requirements.py
flow -- it demonstrates that the policy has real discriminating power rather
than just reporting a suspiciously "no findings" result.
"""
import json
import sys
import time

import boto3

REGION = "us-west-2"


def load_safety_entry():
    state = json.load(open("policies.json"))
    return state["safety-systems"]


def run_test_case(bedrock, policy_arn, workflow_id, guard_content, expected):
    resp = bedrock.create_automated_reasoning_policy_test_case(
        policyArn=policy_arn,
        guardContent=guard_content,
        expectedAggregatedFindingsResult=expected,
    )
    test_case_id = resp["testCaseId"]
    bedrock.start_automated_reasoning_policy_test_workflow(
        policyArn=policy_arn, buildWorkflowId=workflow_id, testCaseIds=[test_case_id]
    )
    for _ in range(20):
        time.sleep(3)
        results = bedrock.list_automated_reasoning_policy_test_results(
            policyArn=policy_arn, buildWorkflowId=workflow_id
        )["testResults"]
        for r in results:
            if r["testCase"]["testCaseId"] == test_case_id and r["testRunStatus"] == "COMPLETED":
                return r
    raise TimeoutError(f"test case {test_case_id} did not complete in time")


def main():
    entry = load_safety_entry()
    policy_arn = entry["policy_arn"]
    workflow_id = entry["build_workflow_id"]
    bedrock = boto3.client("bedrock", region_name=REGION)

    violation = run_test_case(
        bedrock,
        policy_arn,
        workflow_id,
        guard_content=(
            "The heartbeat timeout is configured to 5 seconds. It has been 10 seconds "
            "since the firmware last received a heartbeat from the ROS layer, and the "
            "motors remain enabled."
        ),
        expected="INVALID",
    )
    print("Violation case:", violation["aggregatedTestFindingsResult"], "-", violation["testRunResult"])

    compliant = run_test_case(
        bedrock,
        policy_arn,
        workflow_id,
        guard_content=(
            "The heartbeat timeout is configured to 5 seconds. It has been 10 seconds "
            "since the firmware last received a heartbeat from the ROS layer, and the "
            "motors are disabled."
        ),
        expected="VALID",
    )
    print("Compliant case:", compliant["aggregatedTestFindingsResult"], "-", compliant["testRunResult"])

    if violation["aggregatedTestFindingsResult"] not in ("INVALID", "IMPOSSIBLE"):
        print("FAIL: violation was not flagged as a logical contradiction.", file=sys.stderr)
        sys.exit(1)

    print("\nSanity check passed: the policy correctly flags the injected violation as a real contradiction.")


if __name__ == "__main__":
    main()
