

resource "google_container_cluster" "sre_test" {
  name     = "sre-test-cluster"
  project  = var.project_id
  location = var.region

  enable_autopilot = true

  network    = var.network_id
  subnetwork = var.subnetwork_id

  ip_allocation_policy {
    cluster_secondary_range_name  = "pods"
    services_secondary_range_name = "services"
  }

  private_cluster_config {
    enable_private_nodes    = true
    enable_private_endpoint = false
    master_ipv4_cidr_block  = "172.16.0.0/28"
  }

  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  release_channel {
    channel = "REGULAR"
  }

  deletion_protection = false
}

# Workload Identity binding — must come AFTER cluster creates the pool
resource "google_service_account_iam_member" "workload_identity" {
  service_account_id = var.sre_agent_sa_name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[sre-agent/sre-agent-sa]"

  depends_on = [google_container_cluster.sre_test]
}
