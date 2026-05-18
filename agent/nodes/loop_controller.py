"""
loop_controller.py
Decides continue or exit using multi-signal production rules.
Key fix: tool_signaled_done only exits AFTER min_steps are complete.
enough_evidence=True ALWAYS exits immediately.
"""
import logging
from agent.state import AgentState
from agent.otel import trace_node

log = logging.getLogger("sre-agent.loop_controller")


def _is_stuck(state: AgentState) -> bool:
    """Stuck = same tool + same args called successfully twice in a row."""
    history = state.get("tool_history", [])
    if len(history) < 2:
        return False
    last     = history[-1]
    previous = history[-2]
    return (
        last.get("tool") == previous.get("tool") and
        last.get("args") == previous.get("args") and
        last.get("ok") and previous.get("ok")
    )


def _zero_new_facts(state: AgentState) -> bool:
    """Zero new facts = latest successful tool produced empty key_facts."""
    ev_ids  = state.get("evidence_ids", [])
    history = state.get("tool_history", [])
    if not ev_ids or not history:
        return False
    if not history[-1].get("ok"):
        return False
    last_ev = state.get("evidence_store", {}).get(ev_ids[-1], {})
    return len(last_ev.get("key_facts", [])) == 0


@trace_node("langgraph.loop_controller")
def loop_controller(state: AgentState) -> dict:
    log.info("node=loop_controller run_id=%s", state["run_id"])

    step      = state["investigation"]["current_step"] + 1
    max_steps = state["investigation"]["max_steps"]
    min_steps = state["investigation"].get("min_steps", 2)
    enough    = state["investigation"]["enough_evidence"]
    tool_done = state.get("current_action", {}).get("tool") == "done"
    stuck     = _is_stuck(state)
    zero_facts = _zero_new_facts(state)

    # ── Exit decision — order matters ─────────────────────────────
    exit_reason = None

    if enough:
        # Evaluator confirmed sufficient evidence — always exit
        exit_reason = "confidence_sufficient"

    elif step >= max_steps:
        # Hard cap — always exit
        exit_reason = "max_iterations"

    elif tool_done and step >= min_steps:
        # Router said done AND minimum steps are complete — exit
        exit_reason = "tool_signaled_done"

    elif tool_done and step < min_steps:
        # Router said done BUT min_steps not met — CONTINUE
        # This prevents premature exit after 1 tool call
        log.info(
            "loop_controller: router said done but min_steps not met (%d/%d) — continuing",
            step, min_steps,
        )
        exit_reason = None  # keep running

    elif stuck:
        exit_reason = "stuck_detected"

    elif zero_facts and step > 1:
        exit_reason = "zero_new_facts"

    done   = exit_reason is not None
    status = "done" if done else "running"

    log.info(
        "loop_controller step=%d/%d status=%s exit_reason=%s enough=%s",
        step, max_steps, status, exit_reason, enough,
    )

    updates: dict = {
        "investigation": {
            "current_step":     step,
            "status":           status,
            "loop_exit_reason": exit_reason,
        },
    }

    if exit_reason in ("stuck_detected", "zero_new_facts"):
        updates["errors"] = [f"loop exited early: {exit_reason} at step {step}"]

    if step >= max_steps and not enough:
        updates["errors"] = updates.get("errors", []) + [
            f"max_steps={max_steps} reached without conclusive evidence"
        ]

    return updates
