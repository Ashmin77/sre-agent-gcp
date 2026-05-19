output "network_id" {
  description = "VPC network self-link ID."
  value       = google_compute_network.sre_agent.id
}

output "network_name" {
  description = "VPC network name."
  value       = google_compute_network.sre_agent.name
}

output "subnetwork_id" {
  description = "Primary subnetwork self-link ID."
  value       = google_compute_subnetwork.sre_agent.id
}

output "subnetwork_name" {
  description = "Primary subnetwork name."
  value       = google_compute_subnetwork.sre_agent.name
}

output "subnetwork_cidr" {
  description = "Primary subnetwork CIDR range."
  value       = google_compute_subnetwork.sre_agent.ip_cidr_range
}

output "pods_cidr" {
  description = "GKE pod secondary IP range (CIDR)."
  value       = "10.1.0.0/16"
}

output "services_cidr" {
  description = "GKE services secondary IP range (CIDR)."
  value       = "10.2.0.0/20"
}

output "nat_name" {
  description = "Cloud NAT gateway name."
  value       = google_compute_router_nat.sre_agent.name
}

output "router_name" {
  description = "Cloud Router name."
  value       = google_compute_router.sre_agent.name
}
