# V-Cycle SDLC Contradiction Finder

This repository demonstrates how a Strands multi-agent workflow can review V-cycle project documentation, find contradictions across documents, check one document against its guideline, independently review findings, and suggest
resolutions.

The sample runs locally with models served through Amazon Bedrock or as an
Amazon Bedrock AgentCore deployment. The deployed Runtime retrieves documents
and guidelines by filename through AgentCore Gateway.

## Repository map

### [workshop-current-state-code](./workshop-current-state-code/)

Source-code snapshots used as the basis for the workshop documentation:

- [OpenMower](./workshop-current-state-code/OpenMower/) contains the top-level
  project and hardware/firmware references.
- [open_mower_ros](./workshop-current-state-code/open_mower_ros/) contains the
  ROS implementation baseline.

Each snapshot has its own README with project-specific context.

### [workshop-current-state-documentation](./workshop-current-state-documentation/)

The V-cycle document set supplied to the contradiction finder. It contains
system requirements, system and software architecture, hardware and firmware
architecture, communication protocols, safety systems, state-machine design,
and user acceptance tests.

The [guidelines](./workshop-current-state-documentation/guidelines/) subfolder
contains the corresponding authoring and review guideline for each document.
One document name selects document-to-guideline compliance mode; two or more
document names select cross-document contradiction mode.

### [v-cycle-contradiction-finder](./v-cycle-contradiction-finder/)

The runnable Python sample and AgentCore deployment:

- Stateful contradiction handler built with Strands.
- Stateless reviewer and resolver agents exposed as tools.
- Pydantic-validated reports with `contradiction` and
  `guideline_violation` findings.
- Local CLI, AgentCore invocation CLI, deployment, cleanup, and tests.
- Gateway Lambda tools for retrieving documents and guidelines.

See the
[contradiction finder README](./v-cycle-contradiction-finder/README.md) for
setup, CLI examples, architecture details, deployment, testing, and cleanup.

### [demo-helper-artifacts](./demo-helper-artifacts/)

Workshop support material:

- [introduced-contradictions.md](./demo-helper-artifacts/introduced-contradictions.md)
  is the private acceptance key for the deliberately injected findings. It is
  not supplied to the agents at runtime.
- [generate-guideline-prompt.md](./demo-helper-artifacts/generate-guideline-prompt.md)
  captures the prompt used to help generate document guidelines.

### [docs](./docs/)

Architecture assets for the AgentCore deployment:

- [Rendered architecture](./docs/agentcore-contradiction-finder.png)
- [Editable draw.io source](./docs/agentcore-contradiction-finder.drawio)

## Quick start

Use the supplied virtual environment from the repository root:

```bash
.venv/bin/pip install \
  -r v-cycle-contradiction-finder/requirements.txt
```

Run a local three-document contradiction analysis:

```bash
.venv/bin/python v-cycle-contradiction-finder/find_contradictions.py \
  workshop-current-state-documentation/01-System-Architecture.md \
  workshop-current-state-documentation/02-System-Requirements.md \
  workshop-current-state-documentation/11-User-Acceptance-Test.md \
  --no-interactive
```

Invoke an existing AgentCore deployment:

```bash
.venv/bin/python v-cycle-contradiction-finder/invoke_agentcore.py \
  01-System-Architecture.md \
  02-System-Requirements.md \
  11-User-Acceptance-Test.md
```

Both CLIs write the latest Markdown and JSON reports under
`v-cycle-contradiction-finder/agent-outputs/`.
