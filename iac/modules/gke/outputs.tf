output "cluster_name" {
  description = "GKE cluster name."
  value       = google_container_cluster.sre_test.name
}

output "cluster_endpoint" {
  description = "GKE cluster API server endpoint IP address."
  value       = google_container_cluster.sre_test.endpoint
  sensitive   = true
}

output "cluster_location" {
  description = "GKE cluster region."
  value       = google_container_cluster.sre_test.location
}
