# ── IAM — only sre-agent-sa can invoke MCP server ────────────────
resource "google_cloud_run_v2_service_iam_member" "invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.mcp.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${var.sre_agent_sa_email}"
}
