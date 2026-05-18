output "mcp_url" { value = google_cloud_run_v2_service.mcp.uri }
output "mcp_image_repo" { value = "us-docker.pkg.dev/${var.project_id}/sre-agent-repo" }
