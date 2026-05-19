# ── REQUIRED APIs ────────────────────────────────────────────────
# All services used by the SRE Agent infrastructure and runtime.
# Sorted alphabetically for easy auditing.

locals {
  required_apis = toset([
    "agentregistry.googleapis.com",
    "aiplatform.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "cloudtrace.googleapis.com",
    "compute.googleapis.com",
    "container.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "storage.googleapis.com",
  ])
}

resource "google_project_service" "apis" {
  for_each = local.required_apis

  project                    = google_project.sre_agent.project_id
  service                    = each.value
  disable_on_destroy         = false
  disable_dependent_services = false

  depends_on = [google_billing_project_info.sre_agent]
}
