"""
rca_builder.py
Builds cited RCA with:
- Every claim references a specific evidence_id
- Cluster, region, project in output
- Real token tracking from Gemini usage_metadata
- Estimated cost per investigation
- Full structured observability event to Cloud Logging (ADR Appendix C)
"""
import json
import logging
import os
from datetime import datetime, timezone

from agent.state import AgentState
from agent.gemini_client import llm_json, get_session_usage
from agent.prompts import RCA_BUILDER_SYSTEM, RCA_BUILDER_USER
from agent.otel import trace_node

log = logging.getLogger("sre-agent.rca_builder")

EVIDENCE_BUCKET = os.environ.get("EVIDENCE_BUCKET", "sreagent-demo-evidence")
GEMINI_MODEL    = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")


def _evidence_digest(state: AgentState) -> str:
    store = state.get("evidence_store", {})
    if not store:
        return "No evidence collected."
    lines = []
    for ev_id, ev in store.items():
        cluster_info = ""
        if ev.get("cluster"):
            cluster_info = f" [{ev.get('cluster')}/{ev.get('region','')}]"
        lines.append(f"[{ev_id}]{cluster_info} {ev.get('summary','')[:150]}")
        for f in ev.get("key_facts", [])[:4]:
            lines.append(f"  • {f}")
        lines.append(f"  raw_ref: {ev.get('raw_ref','')}")
    return "\n".join(lines)


def _write_observability_log(state: AgentState, rca: dict, usage: dict) -> None:
    """
    Write full structured audit event to Cloud Logging.
    ADR Appendix C — queryable by run_id, cluster, confidence_band.
    """
    try:
        from google.cloud import logging as cloud_logging
        client   = cloud_logging.Client()
        logger_c = client.logger("sre-agent-investigations")

        inv = state["investigation"]
        ctx = state.get("resolved_context", {})

        tokens_input  = inv.get("tokens_input", 0)  + usage.get("tokens_input", 0)
        tokens_output = inv.get("tokens_output", 0) + usage.get("tokens_output", 0)
        tokens_total  = tokens_input + tokens_output
        cost_usd      = round(inv.get("estimated_cost_usd", 0.0) + usage.get("cost_usd", 0.0), 6)

        entry = {
            # Run identity
            "run_id":             state["run_id"],
            "incident_id":        state["incident_id"],
            "timestamp":          datetime.now(timezone.utc).isoformat(),

            # Incident context
            "incident_type":      ctx.get("incident_type", "Unknown"),
            "namespace":          ctx.get("namespace", ""),
            "pod":                ctx.get("pod", ""),

            # Multi-cluster routing — key for management demo
            "cluster":            ctx.get("cluster_name", ""),
            "cluster_region":     ctx.get("cluster_region", ""),
            "project_id":         ctx.get("project_id", ""),
            "mcp_source":         ctx.get("mcp_source", ""),

            # Investigation metrics
            "iterations":         inv.get("current_step", 0),
            "loop_exit_reason":   inv.get("loop_exit_reason", "unknown"),
            "tools_called":       [h.get("tool") for h in state.get("tool_history", [])],
            "sources_skipped":    state.get("sources_skipped", []),

            # Evidence chain
            "evidence_ids":       state.get("evidence_ids", []),
            "evaluation_ids":     state.get("evaluation_ids", []),
            "gcs_evidence_path":  f"gs://{EVIDENCE_BUCKET}/{state['run_id']}/",

            # Confidence
            "confidence_score":   inv.get("confidence", 0.0),
            "confidence_band":    inv.get("confidence_band", "escalate"),
            "requires_human_review": rca.get("requires_human_review", True),

            # Real token tracking from Gemini metadata
            "tokens_input":       tokens_input,
            "tokens_output":      tokens_output,
            "tokens_total":       tokens_total,
            "estimated_cost_usd": cost_usd,

            # Model info
            "model_name":         GEMINI_MODEL,
            "prompt_version":     "v1.0",
            "graph_version":      "v1.0",

            # Outcome
            "validation_status":  "pending",
        }

        logger_c.log_struct(entry, severity="INFO")
        log.info(
            "observability event written run_id=%s cluster=%s tokens=%d cost=$%.6f",
            state["run_id"], ctx.get("cluster_name", ""), tokens_total, cost_usd,
        )

    except Exception as e:
        log.warning("Failed to write observability log: %s", e)


@trace_node("langgraph.rca_builder")
def rca_builder(state: AgentState) -> dict:
    log.info("node=rca_builder run_id=%s", state["run_id"])

    ctx             = state.get("resolved_context", {})
    inv             = state["investigation"]
    confidence      = inv.get("confidence", 0.0)
    confidence_band = inv.get("confidence_band", "escalate")
    theory          = state.get("working_theory", "")
    evidence_ids    = state.get("evidence_ids", [])

    no_evidence = len(evidence_ids) == 0

    result, usage = llm_json(
        RCA_BUILDER_SYSTEM,
        RCA_BUILDER_USER.format(
            query=state["incident_envelope"].get("user_query", ""),
            incident_type=ctx.get("incident_type", "Unknown"),
            theory=theory,
            confidence_band=confidence_band,
            evidence_digest=_evidence_digest(state),
            evidence_ids=json.dumps(evidence_ids),
            cluster=ctx.get("cluster_name", ""),
            region=ctx.get("cluster_region", ""),
            project=ctx.get("project_id", ""),
        ),
        max_tokens=1024,
    )

    # Final safety gate: no evidence means no auto-confidence, no auto-approval.
    if no_evidence:
        confidence = 0.0
        confidence_band = "escalate"
        result["likely_root_cause"] = "No evidence was extracted, so root cause cannot be determined."
        result["evidence_gaps"] = [
            "No evidence IDs were created from tool output.",
            "Fix evidence extraction/state handoff before trusting RCA output.",
        ]
        result["reasoning_trace"] = [
            "The agent cannot prove a root cause without evidence IDs.",
            "Successful tool calls alone are not enough; their outputs must be extracted and cited.",
            "Confidence is forced to 0.0 and human review is required.",
        ]

    # Enforce required fields
    requires_review = confidence_band != "auto" or no_evidence
    result["confidence_score"]      = confidence
    result["confidence_band"]       = confidence_band
    result["requires_human_review"] = requires_review
    result["run_id"]                = state["run_id"]
    result["evidence_chain"]        = evidence_ids
    result["sources_skipped"]       = state.get("sources_skipped", [])

    actual_sources = []
    for h in state.get("tool_history", []):
        src = h.get("mcp_source")
        if src and src not in actual_sources:
            actual_sources.append(src)

    # Add cluster routing info to RCA output. Use actual MCP sources used,
    # not only the primary source selected during context resolution.
    result["investigation_context"] = {
        "cluster":            ctx.get("cluster_name", ""),
        "cluster_region":     ctx.get("cluster_region", ""),
        "project_id":         ctx.get("project_id", ""),
        "primary_mcp_source":  ctx.get("mcp_source", ""),
        "actual_mcp_sources":  actual_sources,
        "namespace":          ctx.get("namespace", ""),
    }

    # Add real token tracking to RCA output
    total_tokens = inv.get("tokens_total", 0)    + usage.get("tokens_total", 0)
    total_cost   = inv.get("estimated_cost_usd", 0.0) + usage.get("cost_usd", 0.0)
    # result["token_usage"] = {
    #     "tokens_input":       inv.get("tokens_input", 0)  + usage.get("tokens_input", 0),
    #     "tokens_output":      inv.get("tokens_output", 0) + usage.get("tokens_output", 0),
    #     "tokens_total":       total_tokens,
    #     "estimated_cost_usd": round(total_cost, 6),
    #     "model":              GEMINI_MODEL,
    # }

    log.info(
        "rca_builder confidence=%.2f band=%s cluster=%s tokens=%d cost=$%.6f requires_review=%s",
        confidence, confidence_band,
        ctx.get("cluster_name", ""),
        total_tokens, total_cost, requires_review,
    )

    # Write full structured observability event to Cloud Logging
    _write_observability_log(state, result, usage)

    return {
        "final_summary": result,
        "investigation": {
            "status":             "done",
            "tokens_total":       total_tokens,
            "estimated_cost_usd": round(total_cost, 6),
        },
    }
