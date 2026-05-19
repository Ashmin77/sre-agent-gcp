resource "google_service_account" "sre_agent" {
  account_id   = "sre-agent-sa"
  display_name = "SRE Agent Service Account"
  project      = var.project_id
}

locals {
  sre_agent_roles = [
    "roles/aiplatform.user",
    "roles/container.clusterViewer",
    "roles/logging.viewer",
    "roles/container.viewer",
    "roles/logging.logWriter",
    "roles/cloudtrace.agent",
    "roles/monitoring.viewer",
    "roles/monitoring.metricWriter",
    "roles/run.invoker",
    # Required for Google-managed GKE Remote MCP read-only tool calls.
    "roles/mcp.toolUser",
  ]
}

resource "google_project_iam_member" "sre_agent_roles" {
  for_each = toset(local.sre_agent_roles)
  project  = var.project_id
  role     = each.value
  member   = "serviceAccount:${google_service_account.sre_agent.email}"
}
