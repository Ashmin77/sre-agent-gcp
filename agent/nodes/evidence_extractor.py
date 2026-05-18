"""
Writes raw sanitized evidence to GCS and stores compressed facts in state.
"""

import json
import logging

from agent.state import AgentState
from agent.gemini_client import llm_json
from agent.gcs_client import write_evidence, redact
from agent.prompts import EVIDENCE_EXTRACTOR_SYSTEM, EVIDENCE_EXTRACTOR_USER
from agent.otel import trace_node

log = logging.getLogger("sre-agent.evidence_extractor")


def _safe_text(value, limit: int = 500) -> str:
    text = str(value or "").replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 15].rstrip() + " ...[truncated]"


@trace_node("langgraph.evidence_extractor")
def evidence_extractor(state: AgentState) -> dict:
    log.info(
        "node=evidence_extractor run_id=%s latest=%s",
        state["run_id"],
        "HAS_DATA" if state.get("latest_tool_result") else "NONE",
    )

    latest = state.get("latest_tool_result")
    if not latest:
        return {"latest_tool_result": None}

    tool = latest.get("tool", "unknown")
    mcp_source = latest.get("mcp_source", "unknown")
    run_id = state["run_id"]
    ctx = state.get("resolved_context", {})
    prefer_pod = ctx.get("pod", "")

    existing_count = len(state.get("evidence_ids", []))
    ev_id = f"ev_{existing_count + 1:03d}"
    eval_id = f"eval_{existing_count + 1:03d}"

    if not latest.get("ok"):
        error_data = {
            "evidence_id": ev_id,
            "tool": tool,
            "mcp_source": mcp_source,
            "error": latest.get("error"),
            "blocked": latest.get("blocked", False),
            "ok": False,
            "cluster": ctx.get("cluster_name", ""),
        }

        raw_ref = write_evidence(run_id, ev_id, error_data)

        ev_entry = {
            "source": tool,
            "mcp_source": mcp_source,
            "cluster": ctx.get("cluster_name", ""),
            "region": ctx.get("cluster_region", ""),
            "summary": _safe_text(f"Tool failed: {latest.get('error', 'unknown')}", 500),
            "key_facts": [],
            "raw_ref": raw_ref,
        }

        return {
            "evidence_ids": [ev_id],
            "evaluation_ids": [eval_id],
            "evidence_store": {ev_id: ev_entry},
            "latest_tool_result": None,
        }

    raw = latest.get("result", {})
    sanitized = redact(raw)

    raw_ref = write_evidence(
        run_id,
        ev_id,
        {
            "evidence_id": ev_id,
            "tool": tool,
            "mcp_source": mcp_source,
            "cluster": ctx.get("cluster_name", ""),
            "cluster_region": ctx.get("cluster_region", ""),
            "project_id": ctx.get("project_id", ""),
            "sanitized": sanitized,
        },
    )

    raw_str = json.dumps(sanitized, indent=2)
    if len(raw_str) > 5000:
        raw_str = raw_str[:5000] + "\n... raw output trimmed for LLM extraction; full sanitized output is in GCS."

    extracted, usage = llm_json(
        EVIDENCE_EXTRACTOR_SYSTEM,
        EVIDENCE_EXTRACTOR_USER.format(
            tool=tool,
            mcp_source=mcp_source,
            evidence_id=ev_id,
            preferred_pod=prefer_pod or "any failing pod",
            raw_output=raw_str,
        ),
        max_tokens=700,
    )

    if not extracted or not extracted.get("summary"):
        extracted = {
            "resource_type": "pod",
            "resource_id": f"{ctx.get('namespace', '')}/{prefer_pod}",
            "summary": f"Results from {tool}",
            "key_facts": [],
        }

    ev_entry = {
        "source": tool,
        "mcp_source": mcp_source,
        "cluster": ctx.get("cluster_name", ""),
        "region": ctx.get("cluster_region", ""),
        "resource_type": extracted.get("resource_type", "pod"),
        "resource_id": extracted.get("resource_id", ""),
        "summary": _safe_text(extracted.get("summary", ""), 500),
        "key_facts": [_safe_text(f, 500) for f in extracted.get("key_facts", [])[:4]],
        "raw_ref": raw_ref,
    }

    log.info(
        "evidence_extractor ev_id=%s source=%s tool=%s facts=%d raw_ref=%s",
        ev_id,
        mcp_source,
        tool,
        len(ev_entry["key_facts"]),
        raw_ref,
    )

    usage = usage or {}
    current_tokens = state["investigation"].get("tokens_total", 0)
    current_cost = state["investigation"].get("estimated_cost_usd", 0.0)

    return {
        "evidence_ids": [ev_id],
        "evaluation_ids": [eval_id],
        "evidence_store": {ev_id: ev_entry},
        "latest_tool_result": None,
        "investigation": {
            "tokens_input": state["investigation"].get("tokens_input", 0) + usage.get("tokens_input", 0),
            "tokens_output": state["investigation"].get("tokens_output", 0) + usage.get("tokens_output", 0),
            "tokens_total": current_tokens + usage.get("tokens_total", 0),
            "estimated_cost_usd": round(current_cost + usage.get("cost_usd", 0.0), 6),
        },
    }
