# ── PROJECT ──────────────────────────────────────────────────────
resource "google_project" "sre_agent" {
  name       = "sreagent-demo"
  project_id = var.project_id
  # billing_account = var.billing_account

  lifecycle {
    prevent_destroy = false
    ignore_changes  = [billing_account]
  }
}

# ── LINK BILLING ─────────────────────────────────────────────────
resource "google_billing_project_info" "sre_agent" {
  project         = google_project.sre_agent.project_id
  billing_account = var.billing_account
}

# ── ENABLE APIS ──────────────────────────────────────────────────
locals {
  required_apis = [
    "container.googleapis.com",
    "aiplatform.googleapis.com",
    "run.googleapis.com",
    "cloudbuild.googleapis.com",
    "artifactregistry.googleapis.com",
    "storage.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "cloudtrace.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "compute.googleapis.com",
    "secretmanager.googleapis.com",
    "agentregistry.googleapis.com",
  ]
}

resource "google_project_service" "apis" {
  for_each                   = toset(local.required_apis)
  project                    = google_project.sre_agent.project_id
  service                    = each.value
  disable_on_destroy         = false
  disable_dependent_services = false

  depends_on = [google_billing_project_info.sre_agent]
}

# ── MODULES ──────────────────────────────────────────────────────
module "networking" {
  source     = "./modules/networking"
  project_id = google_project.sre_agent.project_id
  region     = var.region

  depends_on = [google_project_service.apis]
}

module "iam" {
  source     = "./modules/iam"
  project_id = google_project.sre_agent.project_id
  region     = var.region

  depends_on = [google_project_service.apis]
}

module "gke" {
  source             = "./modules/gke"
  project_id         = google_project.sre_agent.project_id
  region             = var.region
  network_id         = module.networking.network_id
  subnetwork_id      = module.networking.subnetwork_id
  sre_agent_sa_email = module.iam.sre_agent_sa_email
  sre_agent_sa_name  = module.iam.sre_agent_sa_name # ← this was missing

  depends_on = [module.networking, module.iam]
}

# ── GET GKE CLUSTER VALUES FOR MCP ───────────────────────────────
data "google_container_cluster" "sre_test" {
  name     = module.gke.cluster_name
  location = var.region
  project  = google_project.sre_agent.project_id

  depends_on = [module.gke]
}

# ── CLOUD RUN MCP MODULE ─────────────────────────────────────────
module "cloudrun" {
  source             = "./modules/cloudrun"
  project_id         = google_project.sre_agent.project_id
  region             = var.region
  sre_agent_sa_email = module.iam.sre_agent_sa_email
  cluster_endpoint   = data.google_container_cluster.sre_test.endpoint
  ca_cert_base64     = data.google_container_cluster.sre_test.master_auth[0].cluster_ca_certificate

  depends_on = [module.gke, google_project_service.apis]
}

# ── GCS STAGING BUCKET — Agent Engine deployment artifacts ───────
resource "google_storage_bucket" "staging" {
  name          = "${var.project_id}-staging"
  project       = google_project.sre_agent.project_id
  location      = var.region
  force_destroy = true

  uniform_bucket_level_access = true

  depends_on = [google_project_service.apis]
}

resource "google_storage_bucket_iam_member" "staging_admin" {
  bucket = google_storage_bucket.staging.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${module.iam.sre_agent_sa_email}"
}

# ── GCS EVIDENCE BUCKET ──────────────────────────────────────────
resource "google_storage_bucket" "evidence" {
  name          = "${var.project_id}-evidence"
  project       = google_project.sre_agent.project_id
  location      = var.region
  force_destroy = true

  uniform_bucket_level_access = true

  lifecycle_rule {
    action { type = "Delete" }
    condition { age = 90 }
  }

  versioning {
    enabled = true
  }

  depends_on = [google_project_service.apis]
}

# ── GCS BUCKET IAM — scoped to bucket only ───────────────────────
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
