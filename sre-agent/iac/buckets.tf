# ── GCS EVIDENCE BUCKET ──────────────────────────────────────────
# Stores raw evidence JSON and RCA output written by the agent on every run.

resource "google_storage_bucket" "evidence" {
  name                        = "${var.project_id}-evidence"
  project                     = google_project.sre_agent.project_id
  location                    = var.region
  force_destroy               = true
  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }

  lifecycle_rule {
    action {
      type = "Delete"
    }
    condition {
      age = 90
    }
  }

  depends_on = [google_project_service.apis]
}

resource "google_storage_bucket_iam_member" "evidence_writer" {
  bucket = google_storage_bucket.evidence.name
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${module.iam.sre_agent_sa_email}"
}

resource "google_storage_bucket_iam_member" "evidence_reader" {
  bucket = google_storage_bucket.evidence.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${module.iam.sre_agent_sa_email}"
}

# ── GCS STAGING BUCKET ───────────────────────────────────────────
# Used by Vertex AI Agent Engine to stage LangGraph deployment artifacts.

resource "google_storage_bucket" "staging" {
  name                        = "${var.project_id}-staging"
  project                     = google_project.sre_agent.project_id
  location                    = var.region
  force_destroy               = true
  uniform_bucket_level_access = true

  depends_on = [google_project_service.apis]
}

resource "google_storage_bucket_iam_member" "staging_admin" {
  bucket = google_storage_bucket.staging.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${module.iam.sre_agent_sa_email}"
}
