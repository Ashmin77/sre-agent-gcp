"""
main.py — Gemini Enterprise Agent Runtime entrypoint.

CRITICAL for Agent Runtime:
- No module-level code that can fail (no graph compile at import)
- All initialization happens in set_up() which Agent Runtime calls after deps install
- query() is called for each investigation request

Mirrors AWS src/main.py pattern:
  AWS:  @app.entrypoint on BedrockAgentCoreApp
  GCP:  query() method on ReasoningEngine / SREAgent class

Payload schema:
  {
    "query":      "Pod imagepull-pod is in ImagePullBackOff",
    "namespace":  "test-incidents",
    "pod":        "imagepull-pod",
    "cluster":    "sre-test-cluster",
    "severity":   "high"
  }
"""
import json
import logging
import os
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("sre-agent.server")

PROJECT_ID = os.environ.get("PROJECT_ID", "sreagent-demo")

# Graph is compiled lazily — not at import time
# This prevents Agent Runtime container startup failures
_graph = None


def _get_graph():
    """Lazy graph initialization — safe for Agent Runtime."""
    global _graph
    if _graph is None:
        # Load env only when needed
        from dotenv import load_dotenv
        _env_path = os.path.join(os.path.dirname(__file__), ".env")
        if os.path.exists(_env_path):
            load_dotenv(_env_path)

        from agent.graph import compile_graph
        _graph = compile_graph()
        log.info("LangGraph compiled and ready")
    return _graph


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(value or default)
    except Exception:
        return default


def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value or default)
    except Exception:
        return default


def investigate(payload: dict) -> dict:
    """
    Core investigation function.
    Called by Agent Runtime query() and by run.py locally.
    """
    started_at = time.time()

    query      = payload.get("query", "")
    namespace  = payload.get("namespace", "test-incidents")
    pod        = payload.get("pod", "")
    cluster    = payload.get("cluster", "sre-test-cluster")
    deployment = payload.get("deployment", "")
    severity   = payload.get("severity", "unknown")

    if not query:
        return {"error": "query is required", "status": "failed"}

    try:
        from agent.state import get_initial_state
        from agent.otel import get_tracer, set_span_attributes, flush_traces

        envelope = {
            "source_type":     payload.get("source_type", "manual"),
            "source_event_id": payload.get("source_event_id", ""),
            "user_query":      query,
            "resource_hints": {
                "cluster":    cluster,
                "namespace":  namespace,
                "pod":        pod,
                "deployment": deployment,
            },
            "incident": {
                "severity": severity,
                "title":    payload.get("title", query[:80]),
                "service":  payload.get("service", ""),
            },
        }

        tracer = get_tracer()
        if tracer is not None:
            with tracer.start_as_current_span("sre_agent.investigation") as span:
                set_span_attributes(span, {
                    "sre.query": query[:250],
                    "sre.cluster.requested": cluster,
                    "sre.namespace.requested": namespace,
                    "sre.pod.requested": pod,
                    "sre.deployment.requested": deployment,
                    "sre.severity": severity,
                    "sre.source_type": envelope.get("source_type", "manual"),
                })
                graph  = _get_graph()
                state  = get_initial_state(envelope)
                result = graph.invoke(state)
                inv_for_span = result.get("investigation", {}) or {}
                ctx_for_span = result.get("resolved_context", {}) or {}
                set_span_attributes(span, {
                    "sre.run_id": result.get("run_id", ""),
                    "sre.cluster": ctx_for_span.get("cluster_name", cluster),
                    "sre.namespace": ctx_for_span.get("namespace", namespace),
                    "sre.pod": ctx_for_span.get("pod", pod),
                    "sre.incident_type": ctx_for_span.get("incident_type", ""),
                    "sre.status": inv_for_span.get("status", ""),
                    "sre.confidence": _safe_float(inv_for_span.get("confidence", 0.0)),
                    "sre.confidence_band": inv_for_span.get("confidence_band", ""),
                    "sre.tool_calls": len(result.get("tool_history", []) or []),
                    "sre.evidence_count": len(result.get("evidence_ids", []) or []),
                    "sre.tokens_total": _safe_int(inv_for_span.get("tokens_total", 0)),
                    "sre.estimated_cost_usd": _safe_float(inv_for_span.get("estimated_cost_usd", 0.0)),
                })
        else:
            graph  = _get_graph()
            state  = get_initial_state(envelope)
            result = graph.invoke(state)

        summary = result.get("final_summary", {}) or {}
        inv     = result["investigation"]
        ctx     = result.get("resolved_context", {}) or {}
        errors  = result.get("errors", []) or []
        evidence_ids = result.get("evidence_ids", []) or []
        tool_history = result.get("tool_history", []) or []
        latency_ms = int((time.time() - started_at) * 1000)

        # Try several possible places because token fields may live in different
        # state keys depending on which node produced them.
        usage = result.get("usage", {}) or result.get("token_usage", {}) or {}
        tokens_input = _safe_int(
            inv.get("tokens_input")
            or summary.get("tokens_input")
            or usage.get("tokens_input")
            or usage.get("input_tokens")
            or result.get("tokens_input")
        )
        tokens_output = _safe_int(
            inv.get("tokens_output")
            or summary.get("tokens_output")
            or usage.get("tokens_output")
            or usage.get("output_tokens")
            or result.get("tokens_output")
        )
        tokens_total = _safe_int(
            inv.get("tokens_total")
            or summary.get("tokens_total")
            or usage.get("tokens_total")
            or usage.get("total_tokens")
            or result.get("tokens_total")
        )

        # If only node-level totals exist in logs/state, use that if present.
        if tokens_total == 0:
            tokens_total = _safe_int(result.get("total_tokens") or inv.get("tokens") or summary.get("tokens"))

        estimated_cost_usd = _safe_float(
            inv.get("estimated_cost_usd")
            or summary.get("estimated_cost_usd")
            or usage.get("estimated_cost_usd")
            or result.get("estimated_cost_usd")
        )

        confidence = _safe_float(inv.get("confidence", summary.get("confidence_score", 0.0)))
        confidence_band = inv.get("confidence_band", summary.get("confidence_band", "escalate"))

        # ============================================================
        # Structured observability log — one JSON event per agent run
        # Cloud Logging can parse this as jsonPayload when emitted to stdout.
        # Use this later for log-based metrics and Cloud Monitoring charts.
        # ============================================================
        obs_event = {
            "event_type": "sre_agent_run",
            "run_id": result.get("run_id", ""),
            "incident_type": ctx.get("incident_type", summary.get("incident_type", "")),
            "project_id": ctx.get("project_id", PROJECT_ID),
            "cluster": ctx.get("cluster_name", ctx.get("cluster", cluster)),
            "cluster_region": ctx.get("cluster_region", ctx.get("region", "")),
            "namespace": ctx.get("namespace", namespace),
            "pod": ctx.get("pod", pod),
            "deployment": ctx.get("deployment", deployment),
            "primary_mcp_source": ctx.get("primary_mcp_source", ctx.get("mcp_source", "")),
            "selected_mcp": result.get("selected_mcp", ""),
            "tools_called": len(tool_history),
            "evidence_count": len(evidence_ids),
            "evidence_ids": evidence_ids,
            "confidence": confidence,
            "confidence_band": confidence_band,
            "status": inv.get("status", "unknown"),
            "loop_exit_reason": inv.get("loop_exit_reason", result.get("loop_exit_reason")),
            "human_review": bool(summary.get("requires_human_review", True)),
            "latency_ms": latency_ms,
            "tokens_input": tokens_input,
            "tokens_output": tokens_output,
            "tokens_total": tokens_total,
            "estimated_cost_usd": estimated_cost_usd,
            "error_count": len(errors),
        }

        # stdout JSON line for Cloud Logging jsonPayload parsing.
        print(json.dumps(obs_event, separators=(",", ":")), flush=True)

        # Human-readable fallback log line.
        log.info(
            "observability event written run_id=%s cluster=%s tokens=%s cost=$%.6f latency_ms=%s",
            obs_event["run_id"],
            obs_event["cluster"],
            obs_event["tokens_total"],
            obs_event["estimated_cost_usd"],
            obs_event["latency_ms"],
        )

        flush_traces(timeout_millis=5000)

        return {
            "status":            inv["status"],
            "confidence":        inv.get("confidence", 0.0),
            "confidence_band":   inv.get("confidence_band",
                                 summary.get("confidence_band", "escalate")),
            "tool_calls":        len(tool_history),
            "evidence_ids":      evidence_ids,
            "run_id":            result.get("run_id", ""),
            "summary":           summary,
            "working_theory":    result.get("working_theory", ""),
            "errors":            errors,
            "requires_human_review": summary.get("requires_human_review", True),
            "observability":     obs_event,
        }

    except Exception as exc:
        log.exception("investigation failed: %s", exc)
        return {"error": str(exc), "status": "failed"}


class SREAgent:
    """
    Agent Runtime compatible class.
    Deployed via Vertex AI Agent Engine.

    Agent Runtime lifecycle:
    1. Container starts
    2. set_up() called once — compile graph, load env
    3. query() called for each investigation request
    """

    def set_up(self) -> None:
        """
        Called once when Agent Runtime container starts.
        Pre-compiles the graph so first query() is fast.
        """
        log.info("SREAgent.set_up() called — initializing...")
        _get_graph()
        log.info("SREAgent ready to handle investigations")

    def query(self, **kwargs) -> dict:
        """Called by Agent Runtime for each invocation.

        Agent Engine's client wrapper calls custom methods with keyword
        arguments, for example:

            remote_agent.query(query="...", namespace="...", cluster="...")

        Keep this signature keyword-based so fields like cluster, namespace,
        pod, deployment, and severity are accepted directly.
        """
        payload = dict(kwargs or {})

        log.info(
            "SREAgent.query() called cluster=%s query=%s",
            payload.get("cluster", "?"),
            str(payload.get("query", ""))[:80],
        )
        return investigate(payload)


# ── Local entrypoint — use run.py for full CLI experience ─────────
if __name__ == "__main__":
    payload = {
        "query":     "Pod imagepull-pod in namespace test-incidents is in ImagePullBackOff state.",
        "namespace": "test-incidents",
        "pod":       "imagepull-pod",
        "cluster":   "sre-test-cluster",
        "severity":  "high",
    }
    result = investigate(payload)
    print(json.dumps(result, indent=2))
