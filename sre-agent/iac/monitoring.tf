# ── LOG-BASED METRICS ────────────────────────────────────────────
# Derived from structured JSON logs emitted by the agent on every run.
# Visible in Cloud Monitoring under Metrics Explorer as logging/user/<name>.

resource "google_logging_metric" "agent_invocations" {
  name    = "sre_agent/invocations"
  project = google_project.sre_agent.project_id
  filter  = "jsonPayload.run_id:*"

  metric_descriptor {
    metric_kind  = "DELTA"
    value_type   = "INT64"
    display_name = "SRE Agent Invocations"
  }

  depends_on = [google_project_service.apis]
}

resource "google_logging_metric" "agent_errors" {
  name    = "sre_agent/errors"
  project = google_project.sre_agent.project_id
  filter  = "jsonPayload.status=\"error\""

  metric_descriptor {
    metric_kind  = "DELTA"
    value_type   = "INT64"
    display_name = "SRE Agent Errors"
  }

  depends_on = [google_project_service.apis]
}

resource "google_logging_metric" "agent_escalations" {
  name    = "sre_agent/escalations"
  project = google_project.sre_agent.project_id
  filter  = "jsonPayload.confidence_band=\"escalate\""

  metric_descriptor {
    metric_kind  = "DELTA"
    value_type   = "INT64"
    display_name = "SRE Agent Escalation Events"
  }

  depends_on = [google_project_service.apis]
}

# ── ALERT POLICIES ───────────────────────────────────────────────
# notification_channels is empty by default.
# Add your team's channel resource IDs after Phase 0:
#   https://console.cloud.google.com/monitoring/alerting/notifications

resource "google_monitoring_alert_policy" "agent_high_error_rate" {
  project      = google_project.sre_agent.project_id
  display_name = "SRE Agent — High Error Rate"
  combiner     = "OR"

  conditions {
    display_name = "Agent errors > 5 in 5 minutes"

    condition_threshold {
      filter          = "metric.type=\"logging.googleapis.com/user/sre_agent/errors\" AND resource.type=\"global\""
      duration        = "300s"
      comparison      = "COMPARISON_GT"
      threshold_value = 5

      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_SUM"
      }
    }
  }

  notification_channels = []

  documentation {
    content   = "SRE Agent error rate is elevated. Query logs: `jsonPayload.status=\"error\"`"
    mime_type = "text/markdown"
  }

  depends_on = [google_logging_metric.agent_errors]
}

resource "google_monitoring_alert_policy" "agent_high_escalation_rate" {
  project      = google_project.sre_agent.project_id
  display_name = "SRE Agent — High Escalation Rate"
  combiner     = "OR"

  conditions {
    display_name = "Escalations > 3 in 5 minutes"

    condition_threshold {
      filter          = "metric.type=\"logging.googleapis.com/user/sre_agent/escalations\" AND resource.type=\"global\""
      duration        = "300s"
      comparison      = "COMPARISON_GT"
      threshold_value = 3

      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_SUM"
      }
    }
  }

  notification_channels = []

  documentation {
    content   = "SRE Agent is escalating incidents at a high rate. Query logs: `jsonPayload.confidence_band=\"escalate\"`"
    mime_type = "text/markdown"
  }

  depends_on = [google_logging_metric.agent_escalations]
}
