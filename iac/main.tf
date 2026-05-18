# ── MODULE COMPOSITION ───────────────────────────────────────────
# This file wires together all infrastructure modules.
# Resources are defined in: project.tf, apis.tf, buckets.tf, monitoring.tf

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
  sre_agent_sa_name  = module.iam.sre_agent_sa_name

  depends_on = [module.networking, module.iam]
}

# Read back cluster attributes needed by the MCP server (CA cert, endpoint).
data "google_container_cluster" "sre_test" {
  name     = module.gke.cluster_name
  location = var.region
  project  = google_project.sre_agent.project_id

  depends_on = [module.gke]
}

module "cloudrun" {
  source             = "./modules/cloudrun"
  project_id         = google_project.sre_agent.project_id
  region             = var.region
  sre_agent_sa_email = module.iam.sre_agent_sa_email
  cluster_endpoint   = data.google_container_cluster.sre_test.endpoint
  ca_cert_base64     = data.google_container_cluster.sre_test.master_auth[0].cluster_ca_certificate

  depends_on = [module.gke, google_project_service.apis]
}
