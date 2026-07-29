# Multi-Agent Contradiction Finder

V-cycle projects distribute architecture decisions, requirements, safety rules,
and implementation constraints across separate documents. A statement can look
correct in isolation while contradicting a rule or a chain of implications in
another artifact. This sample demonstrates how a small Strands multi-agent
system can find those cross-document contradictions, independently review them,
and suggest corrections.

## How it works

The sample uses the Strands agents-as-tools pattern:

1. The stateful `contradiction_handler_agent` analyzes two or more documents as
   one corpus, deduplicates candidate contradictions, and composes reasoning
   chains that may span several artifacts.
2. The stateless `reviewer_agent` receives the complete candidate contradictions in one
   tool call and rejects false positives.
3. The stateless `contradiction_resolver_agent` receives only confirmed
   contradictions and proposes one to three corrections for each.
4. Pydantic models validate evidence, reviewer verdicts, resolutions, and the
   final report before it is returned.

The local CLI supplies document content directly. The AgentCore variant accepts
document names and retrieves each document and its corresponding guideline
through AgentCore Gateway. AgentCore Runtime hosts the Strands workflow; the
Gateway Lambda only serves Markdown content with stable source line numbers.

## Introduced contradictions

The workshop documents deliberately contain three cross-document
contradictions:

- A direct conflict over whether WiFi manual trim may bypass `mower_logic`.
- A transitive conflict between the `COMMAND_HOME` docking sequence and the
  required blade state while travelling to the charger.
- A conditional/temporal conflict over replaying a queued start command before
  refreshed safety status is available after WiFi reconnect.

The complete validation key is
[introduced-contradictions.md](../demo-helper-artifacts/introduced-contradictions.md).
It is not packaged into the Gateway or supplied to any agent at runtime.

## Local run

Ensure the AWS SSO session is valid, then run from the repository root:

```bash
.venv/bin/python v-cycle-contradiction-finder/find_contradictions.py \
  workshop-current-state-documentation/01-System-Architecture.md \
  workshop-current-state-documentation/02-System-Requirements.md
```

The Markdown report is followed by a prompt for stateful questions. Add
`--no-interactive` for a one-shot run. The latest Markdown and JSON reports are
always written to `agent-outputs`; `--json PATH` writes an additional JSON copy
to the requested location.

Every successful local or AgentCore CLI call also writes the latest Markdown
and JSON reports to:

```text
v-cycle-contradiction-finder/agent-outputs/contradiction-report.md
v-cycle-contradiction-finder/agent-outputs/contradiction-report.json
```

The program reads `AWS_REGION`, `OPENAI_BASE_URL`, and `MODEL_ID` from `.env`
and authenticates with `aws_bedrock_token_generator.provide_token`.

## AgentCore deployment

The deployment creates:

- an AgentCore Runtime named `vcycle_contradiction_finder`;
- an AgentCore Gateway with a single Lambda target;
- a Cognito client-credentials authorizer for Runtime-to-Gateway access;
- `get_document` and `get_guideline` Gateway tools containing all nine project
  documents and all nine guidelines.

Install the deployment dependencies into the supplied environment:

```bash
.venv/bin/pip install \
  -r v-cycle-contradiction-finder/requirements-deploy.txt
```

Deploy or update all resources:

```bash
.venv/bin/python v-cycle-contradiction-finder/deploy_agentcore.py
```

The script is idempotent and refuses to deploy outside account `974155583980`
and region `us-east-2`. It does not modify other AgentCore runtimes. Cognito
client credentials and generated resource IDs are stored in the ignored
`v-cycle-contradiction-finder/.agentcore-deployment.json` with permissions
`0600`.

## Call the endpoint

The Runtime accepts between two and nine unique top-level Markdown filenames.
The CLI below invokes the deployed AgentCore endpoint.

With two documents:

```bash
.venv/bin/python v-cycle-contradiction-finder/invoke_agentcore.py \
  01-System-Architecture.md \
  02-System-Requirements.md
```

Equivalent payload:

```json
{
  "document_names": [
    "01-System-Architecture.md",
    "02-System-Requirements.md"
  ]
}
```

With three documents:

```bash
.venv/bin/python v-cycle-contradiction-finder/invoke_agentcore.py \
  01-System-Architecture.md \
  02-System-Requirements.md \
  03-Hardware-Architecture.md
```

Equivalent payload:

```json
{
  "document_names": [
    "01-System-Architecture.md",
    "02-System-Requirements.md",
    "03-Hardware-Architecture.md"
  ]
}
```

Each successful local or AgentCore CLI call overwrites the latest reports under
`v-cycle-contradiction-finder/agent-outputs/`.

## Test

```bash
.venv/bin/python -m unittest discover \
  -s v-cycle-contradiction-finder/tests \
  -v
```

## Cleanup

Preview the resources that the cleanup command will remove:

```bash
.venv/bin/python v-cycle-contradiction-finder/destroy_agentcore.py
```

Delete the deployment, including its Cognito domain and user pool:

```bash
.venv/bin/python v-cycle-contradiction-finder/destroy_agentcore.py --yes
```

The cleanup preserves shared resources, including the AgentCore S3 bucket and
any Gateway IAM role still referenced by another Gateway. It removes the local
deployment state only after the AWS cleanup succeeds. Run `deploy_agentcore.py`
again afterward to create a fresh deployment.
