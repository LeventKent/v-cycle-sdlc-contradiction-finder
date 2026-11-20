#!/usr/bin/env python3
"""Idempotently deploy the contradiction finder to Amazon Bedrock AgentCore."""

from __future__ import annotations

import json
import logging
import os
import stat
import time
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import ClientError
from bedrock_agentcore_starter_toolkit.operations.gateway.client import GatewayClient
from bedrock_agentcore_starter_toolkit.operations.gateway.create_role import (
    append_lambda_target_permission,
)
from bedrock_agentcore_starter_toolkit.operations.runtime import (
    configure_bedrock_agentcore,
    launch_bedrock_agentcore,
)

REGION = "us-east-2"
EXPECTED_ACCOUNT_ID = "974155583980"
RUNTIME_NAME = "vcycle_contradiction_finder"
GATEWAY_NAME = "vcycle-contradiction-content"
TARGET_NAME = "vcycle-content"
LAMBDA_NAME = "vcycle-contradiction-content"
LAMBDA_ROLE_NAME = f"{LAMBDA_NAME}-role"

HERE = Path(__file__).resolve().parent
REPOSITORY = HERE.parent
CONTENT_ROOT = REPOSITORY / "workshop-current-state-documentation"
STATE_PATH = HERE / ".agentcore-deployment.json"
SCHEMAS_PATH = HERE / "gateway" / "tool_schemas.json"
RUNTIME_REQUIREMENTS = HERE / "requirements.txt"

LOGGER = logging.getLogger("deploy_agentcore")


def load_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return {}
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def save_state(state: dict[str, Any]) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    STATE_PATH.chmod(stat.S_IRUSR | stat.S_IWUSR)


def build_lambda_zip() -> bytes:
    """Build a Lambda bundle containing the handler and all project content."""
    buffer = BytesIO()
    documents = sorted(CONTENT_ROOT.glob("*.md"))
    guidelines = sorted((CONTENT_ROOT / "guidelines").glob("*.md"))
    if len(documents) != 9 or len(guidelines) != 9:
        raise RuntimeError(
            f"Expected 9 documents and 9 guidelines, found "
            f"{len(documents)} and {len(guidelines)}"
        )

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as bundle:
        bundle.write(HERE / "gateway" / "lambda_function.py", "lambda_function.py")
        for path in documents:
            bundle.write(path, f"documents/{path.name}")
        for path in guidelines:
            bundle.write(path, f"guidelines/{path.name}")
    return buffer.getvalue()


def ensure_lambda_role(iam: Any, account_id: str) -> str:
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "lambda.amazonaws.com"},
                "Action": "sts:AssumeRole",
            }
        ],
    }
    try:
        role = iam.get_role(RoleName=LAMBDA_ROLE_NAME)["Role"]
        iam.update_assume_role_policy(
            RoleName=LAMBDA_ROLE_NAME,
            PolicyDocument=json.dumps(trust_policy),
        )
    except iam.exceptions.NoSuchEntityException:
        role = iam.create_role(
            RoleName=LAMBDA_ROLE_NAME,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description="Execution role for the V-cycle AgentCore content Lambda",
        )["Role"]
        time.sleep(10)

    iam.attach_role_policy(
        RoleName=LAMBDA_ROLE_NAME,
        PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
    )
    return role.get(
        "Arn", f"arn:aws:iam::{account_id}:role/{LAMBDA_ROLE_NAME}"
    )


def wait_for_lambda(lambda_client: Any) -> None:
    lambda_client.get_waiter("function_updated_v2").wait(
        FunctionName=LAMBDA_NAME,
        WaiterConfig={"Delay": 2, "MaxAttempts": 60},
    )


def ensure_lambda(lambda_client: Any, role_arn: str, bundle: bytes) -> dict[str, Any]:
    try:
        lambda_client.get_function(FunctionName=LAMBDA_NAME)
        lambda_client.update_function_code(
            FunctionName=LAMBDA_NAME,
            ZipFile=bundle,
            Publish=False,
        )
        wait_for_lambda(lambda_client)
        lambda_client.update_function_configuration(
            FunctionName=LAMBDA_NAME,
            Role=role_arn,
            Runtime="python3.12",
            Handler="lambda_function.lambda_handler",
            Timeout=30,
            MemorySize=256,
            Description="AgentCore Gateway tools for V-cycle documents and guidelines",
        )
        wait_for_lambda(lambda_client)
        return lambda_client.get_function(FunctionName=LAMBDA_NAME)[
            "Configuration"
        ]
    except lambda_client.exceptions.ResourceNotFoundException:
        function = lambda_client.create_function(
            FunctionName=LAMBDA_NAME,
            Runtime="python3.12",
            Role=role_arn,
            Handler="lambda_function.lambda_handler",
            Code={"ZipFile": bundle},
            Description="AgentCore Gateway tools for V-cycle documents and guidelines",
            Timeout=30,
            MemorySize=256,
            Publish=False,
        )
        wait_for_lambda(lambda_client)
        return function


def get_named_gateway(control: Any) -> dict[str, Any] | None:
    response = control.list_gateways(maxResults=100)
    return next(
        (item for item in response.get("items", []) if item["name"] == GATEWAY_NAME),
        None,
    )


def ensure_gateway(
    gateway_client: GatewayClient,
    state: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    control = gateway_client.client
    gateway = get_named_gateway(control)
    client_info = state.get("cognito")

    if gateway:
        gateway = control.get_gateway(gatewayIdentifier=gateway["gatewayId"])
        if not client_info:
            raise RuntimeError(
                f"Gateway {GATEWAY_NAME} exists but {STATE_PATH} does not contain "
                "its Cognito client secret. Restore the state file or delete that "
                "Gateway before redeploying."
            )
        return gateway, client_info

    if client_info:
        authorizer_config = {
            "customJWTAuthorizer": {
                "allowedClients": [client_info["client_id"]],
                "discoveryUrl": (
                    f"https://cognito-idp.{REGION}.amazonaws.com/"
                    f"{client_info['user_pool_id']}/.well-known/openid-configuration"
                ),
            }
        }
    else:
        auth = gateway_client.create_oauth_authorizer_with_cognito(GATEWAY_NAME)
        client_info = auth["client_info"]
        authorizer_config = auth["authorizer_config"]
        state["cognito"] = client_info
        save_state(state)

    gateway = gateway_client.create_mcp_gateway(
        name=GATEWAY_NAME,
        authorizer_config=authorizer_config,
        enable_semantic_search=False,
        enable_observability=False,
    )
    state["cognito"] = client_info
    state["gateway_id"] = gateway["gatewayId"]
    state["gateway_url"] = gateway["gatewayUrl"]
    save_state(state)
    return gateway, client_info


def wait_for_target(control: Any, gateway_id: str, target_id: str) -> dict[str, Any]:
    for _ in range(60):
        target = control.get_gateway_target(
            gatewayIdentifier=gateway_id,
            targetId=target_id,
        )
        status = target["status"]
        if status == "READY":
            return target
        if status in {"CREATE_FAILED", "UPDATE_FAILED", "DELETE_FAILED"}:
            raise RuntimeError(
                f"Gateway target entered {status}: {target.get('statusReasons', [])}"
            )
        time.sleep(2)
    raise TimeoutError("Timed out waiting for the Gateway target")


def ensure_target(
    gateway_client: GatewayClient,
    gateway: dict[str, Any],
    function_arn: str,
) -> dict[str, Any]:
    schemas = json.loads(SCHEMAS_PATH.read_text(encoding="utf-8"))
    target_payload = {
        "lambdaArn": function_arn,
        "toolSchema": {"inlinePayload": schemas},
    }
    append_lambda_target_permission(
        session=gateway_client.session,
        logger=LOGGER,
        role_arn=gateway["roleArn"],
        function_arn=function_arn,
        region=REGION,
    )

    control = gateway_client.client
    response = control.list_gateway_targets(
        gatewayIdentifier=gateway["gatewayId"],
        maxResults=100,
    )
    existing = next(
        (item for item in response.get("items", []) if item["name"] == TARGET_NAME),
        None,
    )
    if not existing:
        for attempt in range(6):
            try:
                return gateway_client.create_mcp_gateway_target(
                    gateway=gateway,
                    name=TARGET_NAME,
                    target_type="lambda",
                    target_payload=target_payload,
                )
            except ClientError as error:
                message = error.response["Error"].get("Message", "")
                if "AssumeRole" not in message or attempt == 5:
                    raise
                LOGGER.info("Gateway role is propagating; retrying in 10 seconds")
                time.sleep(10)
        raise RuntimeError("Unreachable Gateway target retry state")

    control.update_gateway_target(
        gatewayIdentifier=gateway["gatewayId"],
        targetId=existing["targetId"],
        name=TARGET_NAME,
        targetConfiguration={"mcp": {"lambda": target_payload}},
        credentialProviderConfigurations=[
            {"credentialProviderType": "GATEWAY_IAM_ROLE"}
        ],
    )
    return wait_for_target(control, gateway["gatewayId"], existing["targetId"])


def deploy_runtime(
    gateway: dict[str, Any],
    client_info: dict[str, Any],
) -> Any:
    result = configure_bedrock_agentcore(
        agent_name=RUNTIME_NAME,
        entrypoint_path=Path("agentcore_runtime.py"),
        requirements_file=str(RUNTIME_REQUIREMENTS),
        source_path=str(HERE),
        region=REGION,
        non_interactive=True,
        memory_mode="NO_MEMORY",
        deployment_type="direct_code_deploy",
        runtime_type="PYTHON_3_11",
        enable_observability=True,
    )
    env_vars = {
        "AWS_REGION": REGION,
        "OPENAI_BASE_URL": os.environ.get(
            "OPENAI_BASE_URL",
            f"https://bedrock-mantle.{REGION}.api.aws/openai/v1",
        ),
        "MODEL_ID": os.environ.get("MODEL_ID", "openai.gpt-5.6-terra"),
        "AGENTCORE_GATEWAY_URL": gateway["gatewayUrl"],
        "AGENTCORE_GATEWAY_TOKEN_URL": client_info["token_endpoint"],
        "AGENTCORE_GATEWAY_CLIENT_ID": client_info["client_id"],
        "AGENTCORE_GATEWAY_CLIENT_SECRET": client_info["client_secret"],
        "AGENTCORE_GATEWAY_SCOPE": client_info["scope"],
    }
    return launch_bedrock_agentcore(
        config_path=result.config_path,
        agent_name=RUNTIME_NAME,
        env_vars=env_vars,
        auto_update_on_conflict=True,
        force_rebuild_deps=False,
    )


def wait_for_runtime(control: Any, runtime_id: str) -> dict[str, Any]:
    for _ in range(150):
        runtime = control.get_agent_runtime(agentRuntimeId=runtime_id)
        status = runtime["status"]
        if status == "READY":
            return runtime
        if status in {"CREATE_FAILED", "UPDATE_FAILED", "DELETING"}:
            raise RuntimeError(
                f"Runtime entered {status}: {runtime.get('failureReason', '')}"
            )
        time.sleep(2)
    raise TimeoutError("Timed out waiting for the Runtime to become READY")


def ensure_runtime_model_permission(iam: Any, runtime_role_arn: str) -> None:
    role_name = runtime_role_arn.rsplit("/", 1)[-1]
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": "bedrock-mantle:CreateInference",
                "Resource": (
                    f"arn:aws:bedrock-mantle:{REGION}:{EXPECTED_ACCOUNT_ID}:"
                    "project/default"
                ),
            },
            {
                "Effect": "Allow",
                "Action": "bedrock-mantle:CallWithBearerToken",
                "Resource": "*",
            },
        ],
    }
    iam.put_role_policy(
        RoleName=role_name,
        PolicyName="VcycleContradictionFinderModelInference",
        PolicyDocument=json.dumps(policy),
    )


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    session = boto3.Session(region_name=REGION)
    account_id = session.client("sts").get_caller_identity()["Account"]
    if account_id != EXPECTED_ACCOUNT_ID:
        raise RuntimeError(f"Refusing to deploy to unexpected AWS account {account_id}")

    state = load_state()
    role_arn = ensure_lambda_role(session.client("iam"), account_id)
    function = ensure_lambda(
        session.client("lambda"), role_arn, build_lambda_zip()
    )

    gateway_client = GatewayClient(region_name=REGION)
    gateway, client_info = ensure_gateway(gateway_client, state)
    target = ensure_target(gateway_client, gateway, function["FunctionArn"])

    state.update(
        {
            "region": REGION,
            "lambda_arn": function["FunctionArn"],
            "gateway_id": gateway["gatewayId"],
            "gateway_url": gateway["gatewayUrl"],
            "gateway_role_arn": gateway["roleArn"],
            "target_id": target["targetId"],
            "cognito": client_info,
        }
    )
    save_state(state)

    launch = deploy_runtime(gateway, client_info)
    runtime = wait_for_runtime(gateway_client.client, launch.agent_id)
    ensure_runtime_model_permission(
        session.client("iam"),
        runtime["roleArn"],
    )
    state.update(
        {
            "runtime_name": RUNTIME_NAME,
            "runtime_id": launch.agent_id,
            "runtime_arn": launch.agent_arn,
            "runtime_role_arn": runtime["roleArn"],
        }
    )
    save_state(state)
    public_state = {key: value for key, value in state.items() if key != "cognito"}
    print(json.dumps(public_state, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
