output "sre_agent_sa_email" {
  description = "SRE agent service account email address."
  value       = google_service_account.sre_agent.email
}

output "sre_agent_sa_name" {
  description = "SRE agent service account full resource name (projects/PROJECT/serviceAccounts/EMAIL). Used for IAM member bindings."
  value       = google_service_account.sre_agent.name
}
