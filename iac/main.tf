# ── MODULE COMPOSITION ───────────────────────────────────────────
# This file wires together all infrastructure modules.
# Resources are defined in: project.tf, apis.tf, buckets.tf, monitoring.tf
#
# create_gke_cluster = true  (default) → creates a new demo GKE Autopilot cluster
# create_gke_cluster = false           → reads an existing cluster by project/name/location

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

# ── Demo GKE cluster (Path 1 only) ───────────────────────────────
module "gke" {
  count = var.create_gke_cluster ? 1 : 0

  source             = "./modules/gke"
  project_id         = google_project.sre_agent.project_id
  region             = var.region
  network_id         = module.networking.network_id
  subnetwork_id      = module.networking.subnetwork_id
  sre_agent_sa_email = module.iam.sre_agent_sa_email
  sre_agent_sa_name  = module.iam.sre_agent_sa_name

  depends_on = [module.networking, module.iam]
}

# ── Effective cluster values (works for both modes) ──────────────
locals {
  gke_cluster_name      = var.create_gke_cluster ? module.gke[0].cluster_name : var.existing_gke_cluster
  gke_cluster_project   = var.create_gke_cluster ? google_project.sre_agent.project_id : var.existing_gke_project_id
  gke_cluster_location  = var.create_gke_cluster ? var.region : var.existing_gke_location
  gke_cluster_namespace = var.create_gke_cluster ? "test-incidents" : var.existing_gke_namespace
  # "--region" for regional clusters (default); "--zone" only when existing_gke_location_type = "zone"
  gke_location_flag = (var.create_gke_cluster || var.existing_gke_location_type == "region") ? "--region" : "--zone"
}

# Read back cluster CA cert and endpoint — used by the Cloud Run MCP server.
# For existing clusters, the data source reads from the existing project.
data "google_container_cluster" "sre_test" {
  name     = local.gke_cluster_name
  location = local.gke_cluster_location
  project  = local.gke_cluster_project

  depends_on = [module.gke]
}

module "cloudrun" {
  source             = "./modules/cloudrun"
  project_id         = google_project.sre_agent.project_id
  region             = var.region
  sre_agent_sa_email = module.iam.sre_agent_sa_email
  cluster_endpoint   = data.google_container_cluster.sre_test.endpoint
  ca_cert_base64     = data.google_container_cluster.sre_test.master_auth[0].cluster_ca_certificate

  depends_on = [data.google_container_cluster.sre_test, google_project_service.apis]
}
