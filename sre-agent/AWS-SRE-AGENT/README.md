# SRE Agent AWS Prototype

This repository contains a prototype SRE investigation agent for Kubernetes incidents.

The agent accepts an incident-style input, plans an investigation, calls Kubernetes tools through an AWS Bedrock AgentCore Gateway / MCP tool layer, collects evidence, and returns a structured investigation summary.

## Current Status

This is a prototype / POC.

Current focus:

- Manual incident input
- Kubernetes investigation workflow
- LangGraph-style agent flow
- AWS Bedrock model usage
- AgentCore Gateway tool access
- Read-only evidence collection
- Human-reviewed output

This is not yet a production-ready autonomous remediation system.

## Repository Structure

```text
.
├── invoke_remote.py              # Invoke deployed remote AgentCore runtime
├── pyproject.toml                # Python project dependencies/config
├── run.py                        # Local runner entrypoint
├── src
│   ├── main.py                   # Main app entrypoint
│   ├── agent
│   │   ├── graph.py              # Agent workflow graph
│   │   ├── nodes.py              # Planner/evidence/evaluator/summary nodes
│   │   ├── state.py              # Shared investigation state
│   │   ├── intake.py             # Input parsing
│   │   ├── gateway_client.py     # AgentCore Gateway client
│   │   ├── tool_registry.py      # Tool definitions/registry
│   │   └── prompts
│   │       └── investigation.py  # Investigation prompts
│   ├── mcp_client
│   │   └── client.py             # MCP client logic
│   └── model
│       └── load.py               # Model loading/config
└── test
    └── test_agent.py             # Basic tests
```

## Prerequisites

Install:

- Python 3.12+
- Git
- AWS CLI
- Access to AWS Bedrock model
- Access to AWS Bedrock AgentCore Gateway, if testing remote/tool flow

Optional but recommended:

- `uv` for Python dependency management

## Required Environment Variables

Create a local `.env` file if needed, but do not commit it.

```bash
export AWS_REGION="ca-central-1"
export AWS_DEFAULT_REGION="ca-central-1"

# Required when testing AgentCore Gateway tool calls
export GATEWAY_URL="<REPLACE_WITH_AGENTCORE_GATEWAY_MCP_URL>"

# Optional
export GATEWAY_TIMEOUT="30"
export TOOL_PREFIX="sre-mcp-v3___"
export MODEL_ID="anthropic.claude-3-haiku-20240307-v1:0"
```

## Local Setup

```bash
# Clone repo
git clone https://github.com/Ashmin77/sreagent-aws.git
cd sreagent-aws

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Upgrade pip
python -m pip install --upgrade pip

# Install project dependencies
pip install -e .
```

If using `uv`:

```bash
uv venv
source .venv/bin/activate
uv pip install -e .
```

## Run Tests

```bash
pytest -q
```

Expected result:

```text
tests pass
```

If tests fail because environment variables are missing, export the required variables listed above.

## Run Locally

```bash
python run.py
```

Or:

```bash
python -m src.main
```

The local run should execute the agent workflow using the configured model and available tool/client configuration.

## Test Remote AgentCore Runtime

Use this only after the agent has been deployed to AWS AgentCore Runtime.

```bash
python invoke_remote.py
```

Before running this, confirm:

```bash
aws sts get-caller-identity
echo "$AWS_REGION"
echo "$GATEWAY_URL"
```

## Example Incident Input

Example Kubernetes alert this prototype is designed to investigate:

```text
Pod default/crashloop-demo is in waiting state.
Reason: CrashLoopBackOff
Container: app
Namespace: default
Cluster: demo-cluster
```

Expected investigation behavior:

1. Parse alert context
2. Identify namespace, pod, container, and reason
3. Plan investigation steps
4. Call available Kubernetes tools
5. Collect pod status, events, logs, and deployment context
6. Summarize likely cause and next recommended actions

## Expected Output

The agent should return a structured investigation summary containing:

- Incident summary
- Evidence collected
- Likely cause
- Confidence level
- Gaps or missing evidence
- Recommended next steps

Example shape:

```text
Summary:
The pod is in CrashLoopBackOff.

Evidence:
- Pod restart count increased
- Last container state shows terminated
- Logs show application startup failure

Likely Cause:
Application container exits during startup.

Recommended Next Steps:
- Review application config
- Check recent deployment/image change
- Validate required environment variables/secrets
```

## Security Notes

This prototype should remain read-only.

Recommended guardrails:

- Use least-privilege IAM
- Use read-only Kubernetes RBAC
- Do not allow destructive actions
- Do not expose secrets to the model
- Redact tokens, passwords, kubeconfig, and certificates
- Keep human approval for any remediation

## Known Limitations

Current known prototype limitations:

- Manual alert input
- No persistent evidence database
- Context window limits may truncate large logs
- Tool calls may duplicate during early workflow testing
- Confidence scoring is basic
- Production observability and evaluation are still being validated
- PagerDuty ingestion is not yet implemented

## Future Improvements

Planned improvements:

- PagerDuty alert ingestion
- Evidence storage in object storage
- Evaluation IDs for investigation runs
- Better loop control
- Better tool-selection validation
- CloudWatch/X-Ray tracing validation
- Token, latency, and model metric tracking
- More structured RCA output
- Multi-source evidence support such as Kubernetes, Elastic, Grafana, and cloud APIs

## License

Internal prototype.
