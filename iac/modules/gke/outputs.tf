output "cluster_name" { value = google_container_cluster.sre_test.name }
output "cluster_endpoint" { value = google_container_cluster.sre_test.endpoint }
output "cluster_location" { value = google_container_cluster.sre_test.location }
