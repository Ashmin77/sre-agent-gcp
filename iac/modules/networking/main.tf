# This module sets up the VPC, subnet, and Cloud NAT for the SRE Agent.

resource "google_compute_network" "sre_agent" {
  name                    = "sre-agent-vpc"
  project                 = var.project_id
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "sre_agent" {
  name                     = "sre-agent-subnet"
  project                  = var.project_id
  region                   = var.region
  network                  = google_compute_network.sre_agent.id
  ip_cidr_range            = "10.0.0.0/24"
  private_ip_google_access = true

  secondary_ip_range {
    range_name    = "pods"
    ip_cidr_range = "10.1.0.0/16"
  }

  secondary_ip_range {
    range_name    = "services"
    ip_cidr_range = "10.2.0.0/20"
  }
}

resource "google_compute_router" "sre_agent" {
  name    = "sre-agent-router"
  project = var.project_id
  region  = var.region
  network = google_compute_network.sre_agent.id
}

resource "google_compute_router_nat" "sre_agent" {
  name                               = "sre-agent-nat"
  project                            = var.project_id
  router                             = google_compute_router.sre_agent.name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"
}
