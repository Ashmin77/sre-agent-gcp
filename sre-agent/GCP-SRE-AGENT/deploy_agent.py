#!/usr/bin/env python3
"""
deploy_agent.py — Deploy the SRE LangGraph agent to Vertex AI Agent Engine.

Includes:
- New vertexai.agent_engines API
- Dedicated runtime service account
- OpenTelemetry packages for Cloud Trace spans
- Package import: from agent.main import SREAgent
"""

import os
from dotenv import load_dotenv

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(ROOT_DIR, "agent", ".env"))

PROJECT_ID = os.getenv("PROJECT_ID", "your-gcp-project-id")
REGION = os.getenv("REGION", "us-central1")
STAGING_BUCKET = os.getenv("STAGING_BUCKET", "gs://your-gcp-project-id-staging")
SERVICE_ACCOUNT = os.getenv(
    "AGENT_SERVICE_ACCOUNT",
    "sre-agent-sa@your-gcp-project-id.iam.gserviceaccount.com",
)


def deploy() -> str:
    import vertexai
    from vertexai import agent_engines
    from agent.main import SREAgent

    vertexai.init(
        project=PROJECT_ID,
        location=REGION,
        staging_bucket=STAGING_BUCKET,
    )

    print("\nDeploying SRE Agent to Vertex AI Agent Engine...")
    print(f"  Project         : {PROJECT_ID}")
    print(f"  Region          : {REGION}")
    print(f"  Bucket          : {STAGING_BUCKET}")
    print(f"  Service Account : {SERVICE_ACCOUNT}\n")

    remote_agent = agent_engines.create(
        agent_engine=SREAgent(),
        requirements=[
            "cloudpickle==3.0.0",
            "langgraph>=0.2.0",
            "langchain-core>=0.2.0",
            "google-genai>=1.0.0",
            "google-cloud-aiplatform[agent_engines]>=1.152.0",
            "google-cloud-storage>=2.16.0",
            "google-cloud-logging>=3.10.0",
            "google-auth>=2.29.0",
            "google-auth-httplib2>=0.2.0",
            "httpx>=0.28.1",
            "pydantic>=2.7.2",
            "python-dotenv>=1.0.0",
            "typing-extensions>=4.12.0",
            "opentelemetry-api>=1.28.0",
            "opentelemetry-sdk>=1.28.0",
            "opentelemetry-exporter-gcp-trace>=1.8.0",
        ],
        display_name="sre-agent-gcp",
        description="SRE AI Investigation Co-pilot — LangGraph on Agent Engine with OpenTelemetry traces",
        extra_packages=[
            "agent",
        ],
        service_account=SERVICE_ACCOUNT,
    )

    resource_name = remote_agent.resource_name

    print(f"\n{'=' * 72}")
    print("Deployment complete")
    print(f"Resource: {resource_name}")
    print(
        f"Console : https://console.cloud.google.com/vertex-ai/reasoning-engines?project={PROJECT_ID}"
    )
    print("\nNext:")
    print(f'export AGENT_RESOURCE_NAME="{resource_name}"')
    print(
        'python invoke_agent.py "Pod imagepull-pod is in ImagePullBackOff" '
        "--namespace test-incidents --pod imagepull-pod --cluster sre-test-cluster"
    )
    print(f"{'=' * 72}\n")

    return resource_name


if __name__ == "__main__":
    deploy()
