#!/usr/bin/env python3
"""Safely remove the AWS resources created by deploy_agentcore.py."""

from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path
from typing import Any, Callable

import boto3
from botocore.exceptions import ClientError
from bedrock_agentcore_starter_toolkit.operations.runtime import (
    destroy_bedrock_agentcore,
)

from deploy_agentcore import (
    EXPECTED_ACCOUNT_ID,
    GATEWAY_NAME,
    LAMBDA_NAME,
    LAMBDA_ROLE_NAME,
    REGION,
    RUNTIME_NAME,
    STATE_PATH,
    TARGET_NAME,
    load_state,
)

CONFIG_PATH = Path(__file__).resolve().parent.parent / ".bedrock_agentcore.yaml"
LOGGER = logging.getLogger("destroy_agentcore")


def is_not_found(error: ClientError) -> bool:
    return error.response["Error"]["Code"] in {
        "NoSuchEntity",
        "ResourceNotFoundException",
        "NotFound",
        "NotFoundException",
    }


def destruction_plan(state: dict[str, Any]) -> list[str]:
    cognito = state.get("cognito", {})
    return [
        f"AgentCore Runtime: {state.get('runtime_id', RUNTIME_NAME)}",
        f"Gateway target: {state.get('target_id', TARGET_NAME)}",
        f"Gateway: {state.get('gateway_id', GATEWAY_NAME)}",
        f"Lambda: {LAMBDA_NAME}",
        f"Cognito domain: {cognito.get('domain_prefix', 'from deployment state')}",
        f"Cognito user pool: {cognito.get('user_pool_id', 'from deployment state')}",
        "Dedicated IAM roles and deployment log groups",
        "Runtime deployment object in the shared S3 bucket (bucket is preserved)",
    ]


def wait_until_missing(
    getter: Callable[[], Any],
    *,
    resource_name: str,
    attempts: int = 60,
) -> None:
    for _ in range(attempts):
        try:
            getter()
        except ClientError as error:
            if is_not_found(error):
                return
            raise
        time.sleep(2)
    raise TimeoutError(f"Timed out deleting {resource_name}")


def delete_runtime(session: boto3.Session, state: dict[str, Any]) -> None:
    control = session.client("bedrock-agentcore-control")
    runtime_id = state.get("runtime_id")
    runtime_role_arn = state.get("runtime_role_arn")

    if runtime_id and not runtime_role_arn:
        try:
            runtime_role_arn = control.get_agent_runtime(
                agentRuntimeId=runtime_id
            ).get("roleArn")
        except ClientError as error:
            if not is_not_found(error):
                raise

    if CONFIG_PATH.exists():
        result = destroy_bedrock_agentcore(
            config_path=CONFIG_PATH,
            agent_name=RUNTIME_NAME,
            force=True,
        )
        if result.errors:
            raise RuntimeError("; ".join(result.errors))
    elif runtime_id:
        try:
            control.delete_agent_runtime(agentRuntimeId=runtime_id)
        except ClientError as error:
            if not is_not_found(error):
                raise

    if runtime_id:
        wait_until_missing(
            lambda: control.get_agent_runtime(agentRuntimeId=runtime_id),
            resource_name=f"Runtime {runtime_id}",
        )
        delete_log_group(
            session,
            f"/aws/bedrock-agentcore/runtimes/{runtime_id}-DEFAULT",
        )

    if runtime_role_arn:
        delete_iam_role(session.client("iam"), runtime_role_arn)


def find_gateway(control: Any, state: dict[str, Any]) -> dict[str, Any] | None:
    gateway_id = state.get("gateway_id")
    if gateway_id:
        try:
            return control.get_gateway(gatewayIdentifier=gateway_id)
        except ClientError as error:
            if not is_not_found(error):
                raise

    response = control.list_gateways(maxResults=100)
    match = next(
        (item for item in response.get("items", []) if item["name"] == GATEWAY_NAME),
        None,
    )
    if not match:
        return None
    return control.get_gateway(gatewayIdentifier=match["gatewayId"])


def delete_gateway(session: boto3.Session, state: dict[str, Any]) -> str | None:
    control = session.client("bedrock-agentcore-control")
    gateway = find_gateway(control, state)
    if not gateway:
        return state.get("gateway_role_arn")

    gateway_id = gateway["gatewayId"]
    gateway_role_arn = gateway.get("roleArn")
    targets = control.list_gateway_targets(
        gatewayIdentifier=gateway_id,
        maxResults=100,
    ).get("items", [])
    for target in targets:
        control.delete_gateway_target(
            gatewayIdentifier=gateway_id,
            targetId=target["targetId"],
        )
        wait_until_missing(
            lambda target_id=target["targetId"]: control.get_gateway_target(
                gatewayIdentifier=gateway_id,
                targetId=target_id,
            ),
            resource_name=f"Gateway target {target['targetId']}",
        )

    control.delete_gateway(gatewayIdentifier=gateway_id)
    wait_until_missing(
        lambda: control.get_gateway(gatewayIdentifier=gateway_id),
        resource_name=f"Gateway {gateway_id}",
    )
    return gateway_role_arn


def delete_lambda(session: boto3.Session) -> None:
    client = session.client("lambda")
    try:
        client.delete_function(FunctionName=LAMBDA_NAME)
    except ClientError as error:
        if not is_not_found(error):
            raise
    delete_log_group(session, f"/aws/lambda/{LAMBDA_NAME}")
    delete_iam_role(
        session.client("iam"),
        f"arn:aws:iam::{EXPECTED_ACCOUNT_ID}:role/{LAMBDA_ROLE_NAME}",
    )


def delete_cognito(session: boto3.Session, state: dict[str, Any]) -> None:
    cognito_state = state.get("cognito")
    if not cognito_state:
        raise RuntimeError(
            f"{STATE_PATH} has no Cognito resource IDs; refusing an incomplete cleanup"
        )

    client = session.client("cognito-idp")
    user_pool_id = cognito_state["user_pool_id"]
    domain_prefix = cognito_state.get("domain_prefix")
    if domain_prefix:
        try:
            client.delete_user_pool_domain(
                UserPoolId=user_pool_id,
                Domain=domain_prefix,
            )
        except ClientError as error:
            if not is_not_found(error):
                raise

        for _ in range(60):
            try:
                response = client.describe_user_pool_domain(Domain=domain_prefix)
            except ClientError as error:
                if is_not_found(error):
                    break
                raise
            if not response.get("DomainDescription"):
                break
            time.sleep(2)
        else:
            raise TimeoutError(f"Timed out deleting Cognito domain {domain_prefix}")

    for attempt in range(30):
        try:
            client.delete_user_pool(UserPoolId=user_pool_id)
            break
        except ClientError as error:
            if is_not_found(error):
                break
            if (
                error.response["Error"]["Code"] == "InvalidParameterException"
                and attempt < 29
            ):
                time.sleep(2)
                continue
            raise


def delete_log_group(session: boto3.Session, name: str) -> None:
    try:
        session.client("logs").delete_log_group(logGroupName=name)
    except ClientError as error:
        if not is_not_found(error):
            raise


def delete_iam_role(iam: Any, role_arn: str) -> None:
    role_name = role_arn.rsplit("/", 1)[-1]
    try:
        attached_policies = iam.list_attached_role_policies(RoleName=role_name).get(
            "AttachedPolicies", []
        )
        for policy in attached_policies:
            iam.detach_role_policy(
                RoleName=role_name,
                PolicyArn=policy["PolicyArn"],
            )
        for policy_name in iam.list_role_policies(RoleName=role_name).get(
            "PolicyNames", []
        ):
            iam.delete_role_policy(
                RoleName=role_name,
                PolicyName=policy_name,
            )
        iam.delete_role(RoleName=role_name)
        for policy in attached_policies:
            delete_orphaned_toolkit_policy(iam, policy["PolicyArn"])
    except ClientError as error:
        if not is_not_found(error):
            raise


def delete_orphaned_toolkit_policy(iam: Any, policy_arn: str) -> None:
    account_policy_prefix = f"arn:aws:iam::{EXPECTED_ACCOUNT_ID}:policy/"
    policy_name = policy_arn.rsplit("/", 1)[-1]
    if not policy_arn.startswith(account_policy_prefix) or not policy_name.startswith(
        ("BedrockAgentCoreGateway", "BedrockAgentCoreRuntime")
    ):
        return

    entities = iam.list_entities_for_policy(PolicyArn=policy_arn)
    if any(
        entities.get(key)
        for key in ("PolicyGroups", "PolicyUsers", "PolicyRoles")
    ):
        return
    for version in iam.list_policy_versions(PolicyArn=policy_arn).get(
        "Versions", []
    ):
        if not version["IsDefaultVersion"]:
            iam.delete_policy_version(
                PolicyArn=policy_arn,
                VersionId=version["VersionId"],
            )
    iam.delete_policy(PolicyArn=policy_arn)


def gateway_role_is_unused(session: boto3.Session, role_arn: str) -> bool:
    control = session.client("bedrock-agentcore-control")
    for item in control.list_gateways(maxResults=100).get("items", []):
        gateway = control.get_gateway(gatewayIdentifier=item["gatewayId"])
        if gateway.get("roleArn") == role_arn:
            return False
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Remove the V-cycle contradiction finder AWS resources."
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Perform deletion; without this flag only the deletion plan is shown",
    )
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args()
    state = load_state()
    if not state:
        raise RuntimeError(f"Deployment state not found: {STATE_PATH}")

    print("Resources selected for deletion:")
    for resource in destruction_plan(state):
        print(f"- {resource}")
    if not args.yes:
        print("\nDry run only. Re-run with --yes to delete these resources.")
        return 0

    session = boto3.Session(region_name=REGION)
    account_id = session.client("sts").get_caller_identity()["Account"]
    if account_id != EXPECTED_ACCOUNT_ID:
        raise RuntimeError(f"Refusing to delete from unexpected AWS account {account_id}")

    delete_runtime(session, state)
    gateway_role_arn = delete_gateway(session, state)
    delete_lambda(session)
    delete_cognito(session, state)

    if gateway_role_arn and gateway_role_is_unused(session, gateway_role_arn):
        delete_iam_role(session.client("iam"), gateway_role_arn)
    elif gateway_role_arn:
        LOGGER.info("Preserving Gateway role because another Gateway still uses it")

    STATE_PATH.unlink(missing_ok=True)
    print("\nCleanup complete. Run deploy_agentcore.py to create a fresh deployment.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
