# ── GCP PROJECT ──────────────────────────────────────────────────

resource "google_project" "sre_agent" {
  name       = var.project_id
  project_id = var.project_id

  lifecycle {
    prevent_destroy = false
    # Billing account is managed separately via google_billing_project_info.
    ignore_changes = [billing_account]
  }
}

# ── BILLING ──────────────────────────────────────────────────────

resource "google_billing_project_info" "sre_agent" {
  project         = google_project.sre_agent.project_id
  billing_account = var.billing_account
}
