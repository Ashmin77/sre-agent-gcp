"""
MCP Client — multi-cluster, dual-source routing.

Primary:  GKE Remote MCP (Google-managed, Preview/Pre-GA)
          URL: https://container.googleapis.com/mcp/read-only
          Auth: Bearer access token (NOT identity token)
          ALL tools require: parent = projects/{project}/locations/{location}/clusters/{cluster}

Fallback: Custom FastMCP on Cloud Run
          URL: from env K8S_MCP_URL
          Auth: Bearer identity token

Source: https://cloud.google.com/kubernetes-engine/docs/reference/mcp
"""
import json
import logging
import os
import subprocess
import time
from typing import Any, Dict, Optional

import httpx

log = logging.getLogger("sre-agent.mcp")

# ── Tool Allowlist ────────────────────────────────────────────────
# GKE Remote MCP — confirmed tools from official docs
GKE_REMOTE_TOOLS = frozenset({
    "list_k8s_events",       # kubectl events equivalent
    "describe_k8s_resource", # kubectl describe equivalent
    "get_k8s_resource",      # kubectl get -o yaml equivalent
    "get_k8s_logs",          # kubectl logs equivalent
    "list_k8s_api_resources", # kubectl api-resources equivalent
    "get_k8s_cluster_info",  # cluster info
})

# Custom K8s MCP tools (Cloud Run fallback)
CUSTOM_K8S_TOOLS = frozenset({
    "list_pods",
    "describe_pod_detail",
    "get_current_logs",
    "get_previous_logs",
    "list_events",
    "list_deployments",
})

ALLOWED_TOOLS = GKE_REMOTE_TOOLS | CUSTOM_K8S_TOOLS

# Write-style actions — always blocked
BLOCKED_ACTIONS = frozenset({
    "delete", "create", "patch", "update", "apply",
    "exec", "port-forward", "scale", "rollout",
})

# ── MCP Source Registry ───────────────────────────────────────────
MCP_REGISTRY = {
    "gke_remote_mcp": {
        "url":         "https://container.googleapis.com/mcp/read-only",
        "auth":        "access_token",
        "description": "Google-managed GKE Remote MCP — read-only K8s investigation",
        "tools":       list(GKE_REMOTE_TOOLS),
        "incident_types": ["ImagePullBackOff", "OOMKilled", "CrashLoopBackOff"],
        "ga_status":   "Preview/Pre-GA",
    },
    "k8s_mcp": {
        "url":         os.environ.get("K8S_MCP_URL", ""),
        "auth":        "identity_token",
        "description": "Custom read-only K8s MCP — pod logs, events, describe",
        "tools":       list(CUSTOM_K8S_TOOLS),
        "incident_types": ["ImagePullBackOff", "OOMKilled", "CrashLoopBackOff"],
        "ga_status":   "GA",
    },
}

# ── Cluster Registry ──────────────────────────────────────────────
CLUSTER_REGISTRY = {
    os.environ.get("CLUSTER_1_NAME", "sre-test-cluster"): {
        "project":        os.environ.get("PROJECT_ID",       "sreagent-demo"),
        "region":         os.environ.get("CLUSTER_1_REGION", "us-central1"),
        "mcp_primary":    "gke_remote_mcp",
        "mcp_fallback":   "k8s_mcp",
        "mcp_url":        os.environ.get("K8S_MCP_URL",      ""),
        "incident_types": ["ImagePullBackOff"],
    },
    os.environ.get("CLUSTER_2_NAME", "sre-test-cluster-2"): {
        "project":        os.environ.get("PROJECT_ID_2",      "sreagent-demo-2"),
        "region":         os.environ.get("CLUSTER_2_REGION",  "us-east1"),
        "mcp_primary":    "gke_remote_mcp",
        "mcp_fallback":   "k8s_mcp",
        "mcp_url":        os.environ.get("K8S_MCP_URL_2",     ""),
        "incident_types": ["CrashLoopBackOff"],
    },
}


def _build_parent(project: str, region: str, cluster: str) -> str:
    """Build GKE Remote MCP parent resource path."""
    return f"projects/{project}/locations/{region}/clusters/{cluster}"


def _get_access_token() -> str:
    """Get GCP access token for GKE Remote MCP (requires cloud-platform scope)."""
    try:
        result = subprocess.run(
            ["gcloud", "auth", "print-access-token"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    # Fallback — ADC
    import google.auth
    import google.auth.transport.requests
    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    credentials.refresh(google.auth.transport.requests.Request())
    return credentials.token


def _get_identity_token(url: str) -> str:
    """Get identity token for Cloud Run MCP."""
    try:
        result = subprocess.run(
            ["gcloud", "auth", "print-identity-token"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    import google.oauth2.id_token
    import google.auth.transport.requests as ga_transport
    return google.oauth2.id_token.fetch_id_token(ga_transport.Request(), url)


def _validate_tool(tool_name: str, arguments: Dict[str, Any]) -> Optional[str]:
    """Returns error string if blocked, None if allowed."""
    if tool_name not in ALLOWED_TOOLS:
        return f"Tool '{tool_name}' not in allowlist"
    for blocked in BLOCKED_ACTIONS:
        if blocked in tool_name.lower():
            return f"Tool '{tool_name}' contains blocked action '{blocked}'"
    return None


def _build_gke_args(
    tool_name: str,
    arguments: Dict[str, Any],
    parent: str,
    namespace: str,
    pod_name: str,
) -> Dict[str, Any]:
    """
    Build correct args for GKE Remote MCP tools.
    ALL tools require 'parent'. Other args vary per tool.
    Based on: https://cloud.google.com/kubernetes-engine/docs/reference/mcp
    """
    base = {"parent": parent}

    if tool_name == "list_k8s_events":
        # ListK8SEventsRequest: parent(req), name(opt), namespace(opt),
        #                       resourceType(opt), allNamespaces(opt), limit(opt)
        if namespace:
            base["namespace"] = namespace
        if pod_name:
            base["name"] = pod_name
            base["resourceType"] = "pod"
        return base

    elif tool_name == "describe_k8s_resource":
        # DescribeK8SResourceRequest: parent(req), resourceType(req), name(req),
        #                             namespace(opt)
        base["resourceType"] = arguments.get("resourceType", "pod")
        base["name"]         = arguments.get("name", pod_name)
        if namespace:
            base["namespace"] = namespace
        return base

    elif tool_name == "get_k8s_resource":
        # GetK8SResourceRequest: parent(req), resourceType(req), name(req),
        #                        namespace(opt), outputFormat(opt)
        base["resourceType"] = arguments.get("resourceType", "pod")
        base["name"]         = arguments.get("name", pod_name)
        if namespace:
            base["namespace"] = namespace
        return base

    elif tool_name == "get_k8s_logs":
        # GetK8SLogsRequest: parent(req), namespace(opt), podName(opt),
        #                    container(opt), previous(opt), tailLines(opt)
        if namespace:
            base["namespace"] = namespace
        if pod_name:
            base["podName"] = pod_name
        if arguments.get("previous"):
            base["previous"] = True
        base["tailLines"] = arguments.get("tailLines", 100)
        return base

    elif tool_name == "list_k8s_api_resources":
        # ListK8SAPIResourcesRequest: parent(req)
        return base  # only parent needed

    elif tool_name == "get_k8s_cluster_info":
        # GetK8SClusterInfoRequest: parent(req)
        return base

    # Default — pass parent + any extra args
    return {**base, **{k: v for k, v in arguments.items()
                       if k not in ("namespace", "pod_name", "name", "resourceType")}}


def _map_to_custom_tool(gke_tool: str) -> Optional[str]:
    """Map GKE Remote MCP tool → equivalent custom K8s MCP tool."""
    mapping = {
        "list_k8s_events":       "list_events",
        "describe_k8s_resource": "describe_pod_detail",
        "get_k8s_resource":      "describe_pod_detail",
        "get_k8s_logs":          "get_current_logs",
        "list_k8s_api_resources": "list_pods",
        "get_k8s_cluster_info":  "list_pods",
    }
    return mapping.get(gke_tool)


def call_tool(
    mcp_source: str,
    tool_name: str,
    arguments: Dict[str, Any],
    run_id: str = "",
    cluster_name: str = "",
) -> Dict[str, Any]:
    """
    Call one tool on one MCP source.
    Validates allowlist before any network call.
    Builds correct args for GKE Remote MCP (parent field required).
    Auto-falls-back to custom K8s MCP if GKE Remote fails.
    """
    validation_error = _validate_tool(tool_name, arguments)
    if validation_error:
        log.warning("call_tool BLOCKED: %s", validation_error)
        return {
            "ok": False, "error": f"BLOCKED: {validation_error}",
            "tool": tool_name, "mcp_source": mcp_source,
            "duration_s": 0, "blocked": True,
        }

    cluster_info  = CLUSTER_REGISTRY.get(cluster_name, {})
    source_config = MCP_REGISTRY.get(mcp_source, {})
    is_gke_remote = (mcp_source == "gke_remote_mcp")

    if is_gke_remote:
        url     = source_config.get("url", "https://container.googleapis.com/mcp/read-only")
        project = cluster_info.get("project", os.environ.get("PROJECT_ID", "sreagent-demo"))
        region  = cluster_info.get("region",  os.environ.get("CLUSTER_1_REGION", "us-central1"))
        parent  = _build_parent(project, region, cluster_name)

        # Extract namespace and pod from arguments
        namespace = (arguments.get("namespace") or
                     cluster_info.get("namespace", ""))
        pod_name  = (arguments.get("name") or
                     arguments.get("pod_name") or
                     arguments.get("pod") or "")

        # Build correct args with parent field
        args  = _build_gke_args(tool_name, arguments, parent, namespace, pod_name)
        token = _get_access_token()

        log.info(
            "call_tool gke_remote source=%s tool=%s parent=%s args=%s",
            mcp_source, tool_name, parent, args,
        )

    else:
        # Custom K8s MCP
        url = cluster_info.get("mcp_url") or source_config.get("url", "")
        if not url:
            fallback = cluster_info.get("mcp_fallback", "k8s_mcp")
            if fallback and fallback != mcp_source:
                log.warning("call_tool: no URL for %s, trying %s", mcp_source, fallback)
                return call_tool(fallback, tool_name, arguments, run_id, cluster_name)
            return {
                "ok": False, "error": f"No URL for {mcp_source}",
                "tool": tool_name, "mcp_source": mcp_source, "duration_s": 0,
            }
        args  = dict(arguments)
        token = _get_identity_token(url)

        log.info(
            "call_tool custom source=%s tool=%s args=%s",
            mcp_source, tool_name, args,
        )

    payload = {
        "jsonrpc": "2.0", "id": 1,
        "method":  "tools/call",
        "params":  {"name": tool_name, "arguments": args},
    }

    # GKE Remote MCP endpoint (no /mcp suffix — it IS the endpoint)
    endpoint = url if is_gke_remote else f"{url}/mcp"

    start = time.time()
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                endpoint,
                json=payload,
                headers={
                    "Content-Type":  "application/json",
                    "Accept":        "application/json, text/event-stream",
                    "Authorization": f"Bearer {token}",
                },
            )
        duration = round(time.time() - start, 2)

        if resp.status_code != 200:
            error_msg = f"HTTP {resp.status_code}: {resp.text[:300]}"
            log.warning(
                "call_tool FAILED source=%s tool=%s: %s",
                mcp_source, tool_name, error_msg[:120],
            )

            # Auto-fallback to custom MCP on GKE Remote errors
            if is_gke_remote:
                fallback      = cluster_info.get("mcp_fallback", "k8s_mcp")
                fallback_tool = _map_to_custom_tool(tool_name)
                if fallback and fallback_tool and fallback_tool in CUSTOM_K8S_TOOLS:
                    log.info(
                        "call_tool: GKE Remote failed → fallback %s.%s",
                        fallback, fallback_tool,
                    )
                    # Pass original namespace/pod as custom MCP args
                    fallback_args = {
                        "namespace": namespace,
                        "pod_name":  pod_name,
                    }
                    return call_tool(fallback, fallback_tool, fallback_args, run_id, cluster_name)

            return {
                "ok": False, "error": error_msg,
                "tool": tool_name, "mcp_source": mcp_source, "duration_s": duration,
            }

        # Parse SSE or direct JSON response
        content = _parse_response(resp.text)
        if content is not None:
            return {
                "ok": True, "result": content,
                "tool": tool_name, "mcp_source": mcp_source, "duration_s": duration,
            }

        return {
            "ok": False, "error": "Empty response",
            "tool": tool_name, "mcp_source": mcp_source, "duration_s": duration,
        }

    except Exception as e:
        return {
            "ok": False, "error": str(e),
            "tool": tool_name, "mcp_source": mcp_source,
            "duration_s": round(time.time() - start, 2),
        }


def _parse_response(body: str) -> Optional[Any]:
    """Parse SSE or direct JSON response from MCP server."""
    # Try SSE first
    for line in body.splitlines():
        if line.startswith("data:"):
            try:
                data    = json.loads(line[5:].strip())
                result  = data.get("result", {})
                content = result.get("structuredContent") or result.get("content", [])
                if isinstance(content, list) and content:
                    first = content[0]
                    if isinstance(first, dict) and first.get("type") == "text":
                        try:
                            return json.loads(first["text"])
                        except Exception:
                            return first["text"]
                return content or result
            except Exception:
                pass

    # Try direct JSON
    try:
        data    = json.loads(body)
        result  = data.get("result", {})
        content = result.get("structuredContent") or result.get("content", [])
        if isinstance(content, list) and content:
            first = content[0]
            if isinstance(first, dict) and first.get("type") == "text":
                try:
                    return json.loads(first["text"])
                except Exception:
                    return first["text"]
        return content or result or None
    except Exception:
        pass

    return None


def get_registry_prompt() -> str:
    """Returns MCP registry description for mcp_router prompt."""
    lines = [
        "Available MCP sources (call ONE at a time):",
        "Preferred: gke_remote_mcp (Google-managed, try first)",
        "Fallback:  k8s_mcp (custom Cloud Run, used if gke_remote fails)",
        "",
        "gke_remote_mcp tools — LLM provides: namespace, name(pod), resourceType",
        "  (parent field is built automatically — do NOT include it in arguments)",
        "  list_k8s_events(namespace, name, resourceType='pod')",
        "  describe_k8s_resource(resourceType='pod', name, namespace)",
        "  get_k8s_resource(resourceType='pod', name, namespace)",
        "  get_k8s_logs(namespace, podName, previous=false, tailLines=100)",
        "  list_k8s_api_resources()   ← no args needed",
        "  get_k8s_cluster_info()     ← no args needed",
        "",
        "k8s_mcp tools (fallback — use if gke_remote_mcp fails):",
        "  list_pods(namespace)",
        "  describe_pod_detail(namespace, pod_name)",
        "  get_current_logs(namespace, pod_name)",
        "  get_previous_logs(namespace, pod_name)",
        "  list_events(namespace, pod_name)",
        "  list_deployments(namespace)",
    ]
    return "\n".join(lines)


def resolve_cluster(cluster_name: str) -> Dict[str, Any]:
    """Resolve cluster info from registry."""
    if cluster_name in CLUSTER_REGISTRY:
        return {**CLUSTER_REGISTRY[cluster_name], "cluster_name": cluster_name}
    default_name = list(CLUSTER_REGISTRY.keys())[0]
    log.warning(
        "resolve_cluster: '%s' not in registry, defaulting to '%s'",
        cluster_name, default_name,
    )
    return {**CLUSTER_REGISTRY[default_name], "cluster_name": default_name}
