output "mcp_url" {
  description = "HTTPS URL of the deployed MCP Cloud Run service."
  value       = google_cloud_run_v2_service.mcp.uri
}

output "mcp_image_repo" {
  description = "Artifact Registry repository path for MCP container images (without the image name)."
  value       = "us-docker.pkg.dev/${var.project_id}/sre-agent-repo"
}
