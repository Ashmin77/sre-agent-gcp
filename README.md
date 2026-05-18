# GCP SRE Agent

An AI-powered Site Reliability Engineering co-pilot that autonomously investigates Kubernetes incidents on GCP. Given an incident description, the agent collects evidence from GKE clusters via MCP tools, builds a structured root-cause analysis, and writes all evidence to GCS — without human intervention.

Built with [LangGraph](https://langchain-ai.github.io/langgraph/) and deployed to [Vertex AI Agent Engine](https://cloud.google.com/vertex-ai/generative-ai/docs/agent-engine/overview). Infrastructure is fully managed with Terraform.

---

## How it works

```
Incident query (string)
        │
        ▼
┌────────────────────────────────────────────────────────────────┐
│  SREAgent  (LangGraph — 9 sequential nodes)                    │
│                                                                │
│  input_normalizer → context_resolver → task_planner           │
│                                              │                 │
│                                         mcp_router            │
│                                              │                 │
│                              ┌───────────────┴──────────────┐  │
│                              │          tool_executor        │  │
│                              │  ┌────────────────────────┐  │  │
│                              │  │ GKE Remote MCP         │  │  │
│                              │  │ container.googleapis.com│  │  │
│                              │  │ /mcp/read-only          │  │  │
│                              │  │ (Google-managed)        │  │  │
│                              │  └────────────────────────┘  │  │
│                              │  ┌────────────────────────┐  │  │
│                              │  │ Custom MCP (Cloud Run) │  │  │
│                              │  │ sre-k8s-mcp            │  │  │
│                              │  │ (fallback)             │  │  │
│                              │  └────────────────────────┘  │  │
│                              └───────────────┬──────────────┘  │
│                                              │                 │
│                         evidence_extractor ◄─┘                 │
│                              │                                 │
│                         task_evaluator                         │
│                              │                                 │
│                         loop_controller ────► task_planner     │
│                         (if more evidence      (next tool)     │
│                          is needed)                            │
│                              │ (done)                          │
│                         rca_builder                            │
└──────────────┬───────────────┴────────────────────────────────┘
               │
       ┌───────┴────────────────────────────────────┐
       │  Evidence JSON  →  GCS  (audit trail)      │
       │  RCA summary    →  caller                  │
       │  Structured log →  Cloud Logging           │
       │  Span tree      →  Cloud Trace (OTEL)      │
       └────────────────────────────────────────────┘
```

### Supported incident types

| Incident           | Example query                             |
| ------------------ | ----------------------------------------- |
| `OOMKilled`        | `"oomkilled-pod keeps getting OOMKilled"` |
| `ImagePullBackOff` | `"imagepull-pod is in ImagePullBackOff"`  |
| `CrashLoopBackOff` | `"crashloop-pod is in CrashLoopBackOff"`  |

---

## Repository structure

```
sre-agent-gcp/
├── iac/                          # Terraform — all GCP infrastructure
│   ├── main.tf                   # Project, APIs, buckets, IAM
│   ├── monitoring.tf             # Log-based metrics + alert policies
│   ├── outputs.tf                # All terraform output values
│   ├── variables.tf              # Input variables
│   ├── versions.tf               # Provider versions (Terraform ≥ 1.6)
│   ├── terraform.tfvars.example  # Copy to terraform.tfvars and fill in
│   └── modules/
│       ├── networking/           # VPC, subnet, Cloud NAT
│       ├── iam/                  # Service account + project IAM roles
│       ├── gke/                  # GKE Autopilot cluster
│       └── cloudrun/             # Custom MCP server + Artifact Registry
│
├── agent/                        # LangGraph agent code
│   ├── main.py                   # SREAgent class — Agent Engine entrypoint
│   ├── graph.py                  # LangGraph graph definition (9 nodes)
│   ├── state.py                  # AgentState schema
│   ├── gemini_client.py          # Gemini API wrapper
│   ├── mcp_client.py             # MCP tool client (GKE Remote + Custom)
│   ├── gcs_client.py             # Evidence writer
│   ├── otel.py                   # OpenTelemetry / Cloud Trace setup
│   ├── prompts.py                # LLM prompt templates
│   ├── requirements.txt          # Python dependencies
│   ├── .env.example              # Copy to .env and fill in
│   └── nodes/
│       ├── input_normalizer.py   # Validate and normalise the query
│       ├── context_resolver.py   # Resolve cluster/namespace/pod context
│       ├── task_planner.py       # Plan which MCP tools to call next
│       ├── mcp_router.py         # Choose GKE Remote or Custom MCP
│       ├── tool_executor.py      # Execute the MCP tool call
│       ├── evidence_extractor.py # Extract facts from tool output
│       ├── task_evaluator.py     # Score confidence against evidence
│       ├── loop_controller.py    # Decide continue vs finish
│       └── rca_builder.py        # Produce final RCA
│
├── mcp/                          # Custom MCP server (Cloud Run)
│   ├── server.py                 # FastAPI + MCP server
│   ├── Dockerfile
│   ├── requirements.txt
│   └── tools/
│       ├── pods.py               # Pod list, describe, logs
│       ├── events.py             # Namespace events
│       ├── deployments.py        # Deployment describe
│       └── logs.py               # Container log tail
│
├── k8s/                          # Test incident manifests
│   ├── namespace.yaml            # test-incidents namespace
│   ├── oomkilled-pod.yaml        # Triggers OOMKilled
│   ├── imagepull-pod.yaml        # Triggers ImagePullBackOff
│   └── crashloop-pod.yaml        # Triggers CrashLoopBackOff
│
├── deploy_agent.py               # Deploy LangGraph to Agent Engine
├── invoke_agent.py               # Invoke the deployed Agent Engine agent
├── run.py                        # Local test harness (no Agent Engine)
├── pyproject.toml
└── .python-version               # Python 3.11
```

---

## Prerequisites

| Tool         | Minimum version | Install                                                                                |
| ------------ | --------------- | -------------------------------------------------------------------------------------- |
| `gcloud` CLI | Latest          | [cloud.google.com/sdk](https://cloud.google.com/sdk/docs/install)                      |
| `terraform`  | 1.6+            | [developer.hashicorp.com/terraform](https://developer.hashicorp.com/terraform/install) |
| `kubectl`    | Any             | `gcloud components install kubectl`                                                    |
| `docker`     | Any             | Required only for building the MCP container                                           |
| Python       | 3.11+           | [python.org](https://www.python.org/downloads/)                                        |

**GCP requirements:**

- A GCP billing account ID
- Owner or Editor + appropriate role permissions on the target project
- `gcloud auth application-default login` completed on your workstation

---

## Step-by-step deployment

> **Only one file requires manual edits before you start: `iac/terraform.tfvars`.**
> Everything else — MCP URLs, bucket names, service account emails — is derived automatically.

### 1. Authenticate to GCP

```bash
gcloud auth login
gcloud auth application-default login
```

### 2. Clone the repo

```bash
git clone https://github.com/Ashmin77/sre-agent-gcp.git
cd sre-agent-gcp
```

### 3. Fill in your project details — the only manual config step

```bash
cp iac/terraform.tfvars.example iac/terraform.tfvars
```

Open `iac/terraform.tfvars` and set the two required values:

```hcl
project_id      = "YOUR_GCP_PROJECT_ID"      # globally unique, e.g. "acme-sre-agent-prod"
billing_account = "XXXXXX-XXXXXX-XXXXXX"     # find with: gcloud billing accounts list
region          = "us-central1"              # optional — change if needed
zone            = "us-central1-a"            # optional — must match region
```

That is the only file you ever need to edit. All downstream values (bucket names, service account email, Cloud Run URL) are derived from these two fields by Terraform.

### 4. Deploy infrastructure

```bash
terraform -chdir=iac init
terraform -chdir=iac plan
terraform -chdir=iac apply
```

Terraform creates:
- VPC, subnet, Cloud NAT
- GKE Autopilot cluster (`sre-test-cluster`)
- Service account (`sre-agent-sa`) with least-privilege IAM roles
- Artifact Registry repository for the MCP container image
- Cloud Run MCP service (`sre-k8s-mcp`) — needs the container image built in step 5
- GCS evidence bucket (`YOUR_GCP_PROJECT_ID-evidence`) with 90-day lifecycle + versioning
- GCS staging bucket (`YOUR_GCP_PROJECT_ID-staging`) for Agent Engine deployment artifacts
- Log-based metrics and alert policies in Cloud Monitoring

### 5. Build and push the MCP container image

Terraform creates the registry and Cloud Run service definition but cannot build the image. Run once (and whenever `mcp/` changes):

```bash
PROJECT_ID=$(terraform -chdir=iac output -raw project_id)

# Build and push via Cloud Build
gcloud builds submit ./mcp \
  --tag="us-docker.pkg.dev/${PROJECT_ID}/sre-agent-repo/sre-k8s-mcp:v1" \
  --project="${PROJECT_ID}"

# Redeploy Cloud Run to pick up the new image
terraform -chdir=iac apply -target=module.cloudrun
```

Verify the service is reachable:

```bash
gcloud run services describe sre-k8s-mcp \
  --project="${PROJECT_ID}" \
  --region="$(terraform -chdir=iac output -raw region)" \
  --format="value(status.url)"
```

### 6. Generate agent/.env automatically

This script reads every value from `terraform output` and writes `agent/.env` for you. No manual copy-paste.

```bash
bash scripts/init-env.sh
```

The script prints what it wrote. `agent/.env` is gitignored and must not be committed.

### 7. Set up the Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
pip install -r agent/requirements.txt
pip install "cloudpickle==3.0.0"
pip install "google-cloud-aiplatform[agent_engines]>=1.152.0"
pip install "google-genai>=1.0.0"
pip install "opentelemetry-api>=1.28.0" "opentelemetry-sdk>=1.28.0" "opentelemetry-exporter-gcp-trace>=1.8.0"
```

Verify:

```bash
python -c "import vertexai, cloudpickle; print('ok — cloudpickle', cloudpickle.__version__)"
```

### 8. Connect kubectl and deploy test incidents

```bash
# One-command cluster auth — printed by Terraform
$(terraform -chdir=iac output -raw gke_connect_command)

kubectl get nodes

kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/oomkilled-pod.yaml
kubectl apply -f k8s/imagepull-pod.yaml
kubectl apply -f k8s/crashloop-pod.yaml

# Wait ~2 minutes then confirm pods are in failure states
kubectl get pods -n test-incidents
```

Expected:

```
NAME              READY   STATUS             RESTARTS
oomkilled-pod     0/1     OOMKilled          3
imagepull-pod     0/1     ImagePullBackOff   0
crashloop-pod     0/1     CrashLoopBackOff   5
```

### 9. Test locally

Run the agent against the live GKE cluster from your workstation. No Agent Engine deployment needed yet.

```bash
python run.py "oomkilled-pod keeps getting OOMKilled" \
  --namespace test-incidents --pod oomkilled-pod --severity critical

python run.py "imagepull-pod is in ImagePullBackOff" \
  --namespace test-incidents --pod imagepull-pod --severity high

python run.py "crashloop-pod is in CrashLoopBackOff" \
  --namespace test-incidents --pod crashloop-pod
```

A successful run prints:

```
SRE AGENT — INVESTIGATION REPORT (GCP)
  Run ID    : <uuid>
  Duration  : 45.2s  |  Tool calls: 6
  Evidence  : 4 items → gs://<project>-evidence/<run-id>/

ROOT CAUSE  ✅ HIGH CONFIDENCE (band: high)
   Container memory limit (50Mi) exceeded actual usage ...
```

Confirm evidence written to GCS:

```bash
EVIDENCE_BUCKET=$(terraform -chdir=iac output -raw evidence_bucket_name)
gcloud storage ls -l "gs://${EVIDENCE_BUCKET}/**" | tail -20
```

### 10. Deploy to Agent Engine

Once local tests pass, deploy to Vertex AI Agent Engine. `agent/.env` already contains `STAGING_BUCKET` and `AGENT_SERVICE_ACCOUNT` from step 6, so no extra exports needed.

```bash
python deploy_agent.py
```

The script prints the resource name on completion:

```
Deployment complete
Resource: projects/YOUR-PROJECT-NUMBER/locations/us-central1/reasoningEngines/987654321
```

Add the resource name to `agent/.env`:

```bash
echo "AGENT_RESOURCE_NAME=projects/YOUR-PROJECT-NUMBER/locations/us-central1/reasoningEngines/987654321" >> agent/.env
```

### 11. Invoke the deployed agent

```bash
python invoke_agent.py "oomkilled-pod keeps getting OOMKilled" \
  --namespace test-incidents --pod oomkilled-pod --severity critical

python invoke_agent.py "imagepull-pod is in ImagePullBackOff" \
  --namespace test-incidents --pod imagepull-pod

python invoke_agent.py "crashloop-pod is in CrashLoopBackOff" \
  --namespace test-incidents --pod crashloop-pod
```

### 12. Verify end-to-end

**Evidence in GCS:**

```bash
EVIDENCE_BUCKET=$(terraform -chdir=iac output -raw evidence_bucket_name)
gcloud storage ls -l "gs://${EVIDENCE_BUCKET}/**" | tail -20
gcloud storage cat "gs://${EVIDENCE_BUCKET}/<run-id>/ev_001.json"
```

**Structured logs:**

```bash
PROJECT_ID=$(terraform -chdir=iac output -raw project_id)
gcloud logging read 'jsonPayload.run_id:*' \
  --project="${PROJECT_ID}" \
  --limit=10 \
  --format="table(timestamp,jsonPayload.run_id,jsonPayload.incident_type,jsonPayload.confidence,jsonPayload.status)"
```

**Cloud Trace:** Open [Cloud Trace Explorer](https://console.cloud.google.com/traces) and filter by service name `sre-agent`.

---

## Configuration reference

### The only file you edit: `iac/terraform.tfvars`

| Variable | Required | Description |
|---|---|---|
| `project_id` | Yes | Your GCP project ID (globally unique) |
| `billing_account` | Yes | GCP billing account — `gcloud billing accounts list` |
| `region` | No | Default `us-central1` |
| `zone` | No | Default `us-central1-a` |

### Auto-generated: `agent/.env`

Generated by `bash scripts/init-env.sh` after `terraform apply`. Never edit manually — re-run the script to refresh.

| Variable | Source |
|---|---|
| `PROJECT_ID` | `terraform output -raw project_id` |
| `REGION` | `terraform output -raw region` |
| `GEMINI_MODEL` | Hard-coded `gemini-2.5-flash` |
| `K8S_MCP_URL` | `terraform output -raw custom_mcp_url` |
| `GKE_REMOTE_MCP_URL` | Fixed: `https://container.googleapis.com/mcp/read-only` |
| `EVIDENCE_BUCKET` | `terraform output -raw evidence_bucket_name` |
| `STAGING_BUCKET` | `terraform output -raw staging_bucket_url` |
| `AGENT_SERVICE_ACCOUNT` | `terraform output -raw agent_service_account_email` |
| `AGENT_RESOURCE_NAME` | Added manually after `python deploy_agent.py` |

---

## Terraform outputs reference

Run `terraform -chdir=iac output` to see all values. Key outputs:

| Output name                   | Description                                           |
| ----------------------------- | ----------------------------------------------------- |
| `project_id`                  | GCP project ID                                        |
| `agent_service_account_email` | Runtime service account                               |
| `gke_cluster_name`            | GKE cluster name                                      |
| `gke_connect_command`         | Full `gcloud ... get-credentials` command             |
| `custom_mcp_url`              | Cloud Run MCP server URL                              |
| `mcp_build_command`           | Full `gcloud builds submit` command for the MCP image |
| `evidence_bucket_name`        | Evidence GCS bucket name (no `gs://`)                 |
| `evidence_bucket_url`         | Evidence GCS bucket URL (with `gs://`)                |
| `staging_bucket_name`         | Staging GCS bucket name                               |
| `staging_bucket_url`          | Staging GCS bucket URL (with `gs://`)                 |
| `gke_remote_mcp_url`          | Google-managed GKE Remote MCP endpoint                |
| `summary`                     | Full infrastructure summary block                     |

---

## What Terraform manages

Everything in the table below is created and managed by `terraform apply`. You do not need to create these manually.

| Resource                                               | Terraform file        |
| ------------------------------------------------------ | --------------------- |
| GCP project + billing link                             | `main.tf`             |
| All required APIs                                      | `main.tf`             |
| VPC, subnet, Cloud NAT                                 | `modules/networking/` |
| GKE Autopilot cluster                                  | `modules/gke/`        |
| Service account + IAM roles                            | `modules/iam/`        |
| Artifact Registry repository                           | `modules/cloudrun/`   |
| Cloud Run MCP service + invoker IAM                    | `modules/cloudrun/`   |
| GCS evidence bucket + lifecycle + IAM                  | `main.tf`             |
| GCS staging bucket + IAM                               | `main.tf`             |
| Log-based metrics (invocations, errors, escalations)   | `monitoring.tf`       |
| Alert policies (high error rate, high escalation rate) | `monitoring.tf`       |

**Not managed by Terraform** (by design):

| Item                              | Why                                                |
| --------------------------------- | -------------------------------------------------- |
| MCP container image build         | Requires `docker` / Cloud Build — kept in a script |
| LangGraph Agent Engine deployment | Application packaging — kept in `deploy_agent.py`  |
| k8s test manifests                | Applied once by the operator with `kubectl apply`  |
| Agent invocation                  | Runtime test — kept in `invoke_agent.py`           |
| Agent Registry alpha commands     | API still in alpha                                 |

---

## Updating the MCP server

If you change anything under `mcp/`, rebuild and redeploy:

```bash
PROJECT_ID=$(terraform -chdir=iac output -raw project_id)

# Rebuild
gcloud builds submit ./mcp \
  --tag="us-docker.pkg.dev/${PROJECT_ID}/sre-agent-repo/sre-k8s-mcp:v1" \
  --project="${PROJECT_ID}"

# Redeploy Cloud Run to pick up the new image
terraform -chdir=iac apply -target=module.cloudrun
```

---

## Observability

### Structured logs

Every agent run emits one JSON line to stdout that Cloud Logging captures as `jsonPayload`:

```bash
# All runs
gcloud logging read 'jsonPayload.run_id:*' --project=<project> --limit=20

# Escalations only
gcloud logging read 'jsonPayload.confidence_band="escalate"' --project=<project> --limit=20

# Errors only
gcloud logging read 'jsonPayload.status="error"' --project=<project> --limit=20
```

### Cloud Monitoring

Terraform creates three log-based metrics visible in Cloud Monitoring:

- `logging.googleapis.com/user/sre_agent/invocations`
- `logging.googleapis.com/user/sre_agent/errors`
- `logging.googleapis.com/user/sre_agent/escalations`

Two alert policies are pre-configured (no notification channels by default). To wire up alerts, add your team's channel IDs to `notification_channels` in `iac/monitoring.tf` and re-apply.

### Cloud Trace

The agent instruments every graph node with OpenTelemetry spans. View them in [Cloud Trace Explorer](https://console.cloud.google.com/traces). Expected spans per run:

```
sre_agent.investigation
  ├── input_normalizer
  ├── context_resolver
  ├── task_planner
  ├── mcp_router
  ├── tool_executor  (one span per MCP call)
  ├── evidence_extractor
  ├── task_evaluator
  ├── loop_controller
  └── rca_builder
```

---

## Troubleshooting

**`cloudpickle` version error during `deploy_agent.py`**

Agent Engine requires exactly `cloudpickle==3.0.0`. Install it explicitly:

```bash
pip install "cloudpickle==3.0.0"
pip freeze | grep cloudpickle   # must show 3.0.0
```

**`AGENT_RESOURCE_NAME not set` when running `invoke_agent.py`**

Export the resource name printed by `deploy_agent.py`, or add it to `agent/.env`:

```bash
export AGENT_RESOURCE_NAME="projects/.../reasoningEngines/..."
```

Or list deployed agents:

```bash
gcloud ai reasoning-engines list \
  --region=us-central1 \
  --project=<project-id>
```

**MCP tool returns no results / empty evidence**

Check Cloud Run logs for the MCP server:

```bash
gcloud logging read \
  'resource.type="cloud_run_revision" AND resource.labels.service_name="sre-k8s-mcp"' \
  --project=<project> --limit=50
```

Verify the Cloud Run service has the correct `GKE_CLUSTER_ENDPOINT` env var by checking `terraform output`.

**GKE Remote MCP tool name errors**

Do not use `mcp_gke_*` prefixed names. The real tool names are:

```
list_k8s_events
describe_k8s_resource
get_k8s_resource
```

`list_k8s_api_resources` does not accept a `namespace` parameter — the agent handles this automatically.

**Terraform apply fails on billing**

Ensure your GCP user has `roles/billing.admin` or `roles/billing.projectManager` on the billing account. Verify the billing account ID:

```bash
gcloud billing accounts list
```

---

## Operations guide

For a detailed breakdown of every `gcloud` command, what is Terraform-managed vs manual, and the full handoff checklist, see:

[`gcp-sre-agent-implementation-guide-out-of-terraform-commands.md`](gcp-sre-agent-implementation-guide-out-of-terraform-commands.md)
