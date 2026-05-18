"""
GCS evidence store.
Writes sanitized raw MCP responses by evidence_id.
Raw MCP output never enters LLM context — only compressed facts do.
"""
import json
import logging
import os

from google.cloud import storage

log = logging.getLogger("sre-agent.gcs")

BUCKET = os.environ.get("EVIDENCE_BUCKET", "sreagent-demo-evidence")

_client: storage.Client | None = None


def _get_client() -> storage.Client:
    global _client
    if _client is None:
        _client = storage.Client()
    return _client


def write_evidence(
    run_id: str,
    evidence_id: str,
    sanitized_data: dict,
) -> str:
    """
    Write sanitized MCP response to GCS.
    Returns raw_ref (gs:// path) for audit trail.
    Never stores unredacted data.
    """
    path = f"{run_id}/{evidence_id}.json"
    try:
        client = _get_client()
        bucket = client.bucket(BUCKET)
        blob   = bucket.blob(path)
        blob.upload_from_string(
            json.dumps(sanitized_data, indent=2),
            content_type="application/json",
        )
        raw_ref = f"gs://{BUCKET}/{path}"
        log.info(f"Evidence written: {raw_ref}")
        return raw_ref
    except Exception as e:
        log.error(f"GCS write failed for {evidence_id}: {e}")
        return f"gcs_write_failed:{path}"


def redact(raw: dict) -> dict:
    """
    PII redaction before GCS write and before LLM context.
    Redacts: email addresses, IP addresses, tokens, passwords.
    Called at evidence_extractor — before any other processing.
    """
    import re, copy
    data = copy.deepcopy(raw)
    data_str = json.dumps(data)

    # Redact email addresses
    data_str = re.sub(
        r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        "[REDACTED_EMAIL]", data_str
    )
    # Redact IPv4 addresses (keep structure, redact value)
    data_str = re.sub(
        r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
        "[REDACTED_IP]", data_str
    )
    # Redact bearer tokens
    data_str = re.sub(
        r"Bearer\s+[A-Za-z0-9\-._~+/]+=*",
        "Bearer [REDACTED_TOKEN]", data_str
    )
    # Redact password-like fields
    data_str = re.sub(
        r'"(password|token|secret|key|credential)"\s*:\s*"[^"]*"',
        r'"\1": "[REDACTED]"', data_str,
        flags=re.IGNORECASE
    )
    try:
        return json.loads(data_str)
    except Exception:
        return {"redacted": True, "error": "redaction_parse_failed"}
