# Multi-Agent Contradiction Finder

This local Strands sample compares two V-cycle Markdown documents:

- `ContradictionHandlerAgent` finds candidate contradictions and keeps context
  for follow-up questions.
- `ReviewerAgent` reviews all candidates in one stateless tool call.
- `ContradictionResolverAgent` suggests one to three corrections for every
  confirmed contradiction in one stateless tool call.

The original CLI runs the agents locally. Only model inference is remote,
through the OpenAI-compatible AWS Bedrock endpoint configured by the repository
`.env`.

## Run

Ensure the AWS SSO session is valid, then run from the repository root:

```bash
.venv/bin/python v-cycle-contradiction-finder/find_contradictions.py \
  workshop-current-state-documentation/01-System-Architecture.md \
  workshop-current-state-documentation/02-System-Requirements.md
```

The Markdown report is followed by a prompt for stateful questions. Add
`--no-interactive` for a one-shot run or `--json report.json` to also save the
Pydantic-validated report as JSON.

Every successful local or AgentCore CLI call also writes the latest Markdown
and JSON reports to:

```text
v-cycle-contradiction-finder/agent-outputs/contradiction-report.md
v-cycle-contradiction-finder/agent-outputs/contradiction-report.json
```

The program reads `AWS_REGION`, `OPENAI_BASE_URL`, and `MODEL_ID` from `.env`
and authenticates with `aws_bedrock_token_generator.provide_token`.

## Test

```bash
.venv/bin/python -m unittest discover \
  -s v-cycle-contradiction-finder/tests \
  -v
```

The answer key under `demo-helper-artifacts` is not loaded by the program.

## AgentCore deployment

The deployment sample adds:

- an AgentCore Runtime named `vcycle_contradiction_finder`;
- an AgentCore Gateway with a single Lambda target;
- `get_document` and `get_guideline` Gateway tools containing all nine project
  documents and all nine guidelines.

The Runtime accepts document names, retrieves both documents and their
guidelines through the Gateway, and then runs the same handler, reviewer, and
resolver workflow. No agent code runs in Lambda; Lambda only returns requested
Markdown content with source coordinates.

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

Invoke the deployed Runtime:

```bash
.venv/bin/python v-cycle-contradiction-finder/invoke_agentcore.py \
  01-System-Architecture.md \
  02-System-Requirements.md
```

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
