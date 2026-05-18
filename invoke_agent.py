#!/usr/bin/env python3
"""
invoke_agent.py — Call the deployed Agent Runtime directly.

Mirrors the AWS invoke_remote.py pattern exactly.
Use this after deploying the LangGraph agent to Gemini Enterprise Agent Runtime.

Usage:
  python invoke_agent.py "imagepull-pod is in ImagePullBackOff" \
      --namespace test-incidents --pod imagepull-pod --severity high

  python invoke_agent.py "oomkilled-pod keeps dying" \
      --namespace test-incidents --pod oomkilled-pod --severity critical

  python invoke_agent.py "crashloop-pod is crashing" \
      --namespace test-incidents --pod crashloop-pod

Environment variables required:
  AGENT_RESOURCE_NAME   Full resource name from Agent Runtime deployment
                        e.g. projects/239722105604/locations/us-central1/reasoningEngines/123456
  PROJECT_ID            sreagent-demo
  REGION                us-central1

How to get AGENT_RESOURCE_NAME after deployment:
  python deploy_agent.py  (prints the resource name)
  OR
  gcloud ai reasoning-engines list --region=us-central1 --project=sreagent-demo
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

# ── Load .env ─────────────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "agent", ".env"))

PROJECT_ID           = os.getenv("PROJECT_ID", "sreagent-demo")
REGION               = os.getenv("REGION", "us-central1")
AGENT_RESOURCE_NAME  = os.getenv("AGENT_RESOURCE_NAME", "")


def _invoke(resource_name: str, payload: dict) -> dict:
    """Call the Agent Runtime and return parsed response."""
    if not resource_name:
        print("ERROR: AGENT_RESOURCE_NAME not set.")
        print("Export it after deploying:")
        print("  export AGENT_RESOURCE_NAME=projects/.../reasoningEngines/...")
        print("  OR run: python deploy_agent.py")
        sys.exit(1)

    try:
        import vertexai
        from vertexai.preview import reasoning_engines

        vertexai.init(project=PROJECT_ID, location=REGION)

        print(f"\n{'─'*60}")
        print(f"  Invoking SRE Agent on Agent Runtime")
        print(f"  Resource: {resource_name}")
        print(f"  Payload:  {json.dumps(payload)}")
        print(f"{'─'*60}")

        started = time.time()

        # Get the deployed agent
        remote_agent = reasoning_engines.ReasoningEngine(resource_name)

        # Invoke — mirrors AWS client.invoke_agent_runtime()
        response = remote_agent.query(**payload)

        duration = round(time.time() - started, 2)
        print(f"\n  ✅ Agent Runtime responded in {duration}s")

        return response

    except Exception as e:
        print(f"ERROR invoking Agent Runtime: {e}")
        sys.exit(1)


def _print_summary(result: dict) -> None:
    summary = result.get("summary", {}) or {}
    print(f"\n{'='*60}")
    print(f"  SRE AGENT — AGENT RUNTIME RESULT")
    print(f"{'='*60}")
    print(f"  Run ID       : {result.get('run_id', '?')}")
    print(f"  Status       : {result.get('status', '?')}")
    print(f"  Confidence   : {result.get('confidence', '?'):.2f}")
    print(f"  Band         : {result.get('confidence_band', '?')}")
    print(f"  Tool calls   : {result.get('tool_calls', '?')}")
    print(f"  Evidence IDs : {result.get('evidence_ids', [])}")
    print(f"  Human review : {result.get('requires_human_review', True)}")
    print(f"\n  Root cause: {summary.get('likely_root_cause', 'N/A')[:120]}")

    errors = result.get("errors", [])
    if errors:
        print(f"\n  Errors: {errors}")

    print("\n  Full JSON:")
    print(json.dumps(result, indent=2))
    print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Invoke deployed SRE Agent on Gemini Enterprise Agent Runtime",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("query",        help="Incident description or alert text")
    parser.add_argument("--namespace",  default="test-incidents")
    parser.add_argument("--pod",        default="")
    parser.add_argument("--cluster",    default="sre-test-cluster")
    parser.add_argument("--deployment", default="")
    parser.add_argument("--severity",   default="high",
                        choices=["low", "medium", "high", "critical"])
    parser.add_argument("--resource-name", default=AGENT_RESOURCE_NAME,
                        help="Agent Runtime resource name (overrides env var)")
    args = parser.parse_args()

    payload = {
        "query":      args.query,
        "namespace":  args.namespace,
        "pod":        args.pod,
        "cluster":    args.cluster,
        "deployment": args.deployment,
        "severity":   args.severity,
    }

    result = _invoke(args.resource_name, payload)
    _print_summary(result)


if __name__ == "__main__":
    main()
