locals {
  image = "us-docker.pkg.dev/${var.project_id}/sre-agent-repo/sre-k8s-mcp:${var.image_tag}"
}

# ── Artifact Registry — stores MCP container image ───────────────
resource "google_artifact_registry_repository" "sre_agent" {
  repository_id = "sre-agent-repo"
  project       = var.project_id
  location      = "us"
  format        = "DOCKER"
  description   = "SRE Agent container images"
}

# ── GCS — store CA cert for MCP server to read ───────────────────
resource "google_storage_bucket_object" "ca_cert" {
  name    = "config/ca.crt"
  bucket  = "${var.project_id}-evidence"
  content = base64decode(var.ca_cert_base64)
}

# ── Cloud Run — MCP server ────────────────────────────────────────
resource "google_cloud_run_v2_service" "mcp" {
  name     = "sre-k8s-mcp"
  project  = var.project_id
  location = var.region

  ingress = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = var.sre_agent_sa_email

    scaling {
      min_instance_count = 0
      max_instance_count = 3
    }

    containers {
      image = local.image

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          memory = "512Mi"
          cpu    = "1"
        }
      }

      env {
        name  = "GKE_CLUSTER_ENDPOINT"
        value = "https://${var.cluster_endpoint}"
      }

      env {
        name  = "GKE_CA_CERT_GCS_PATH"
        value = "gs://${var.project_id}-evidence/config/ca.crt"
      }

      env {
        name  = "PROJECT_ID"
        value = var.project_id
      }
    }
  }
}
