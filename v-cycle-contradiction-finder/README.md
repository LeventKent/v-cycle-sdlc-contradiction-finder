# Multi-Agent Contradiction Finder

This local Strands sample compares two V-cycle Markdown documents:

- `ContradictionHandlerAgent` finds candidate contradictions and keeps context
  for follow-up questions.
- `ReviewerAgent` reviews all candidates in one stateless tool call.
- `ContradictionResolverAgent` suggests one to three corrections for every
  confirmed contradiction in one stateless tool call.

The agents run locally. Only model inference is remote, through the
OpenAI-compatible AWS Bedrock endpoint configured by the repository `.env`.
Nothing is deployed to AWS.

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

The program reads `AWS_REGION`, `OPENAI_BASE_URL`, and `MODEL_ID` from `.env`
and authenticates with `aws_bedrock_token_generator.provide_token`.

## Test

```bash
.venv/bin/python -m unittest discover \
  -s v-cycle-contradiction-finder/tests \
  -v
```

The answer key under `demo-helper-artifacts` is not loaded by the program.
