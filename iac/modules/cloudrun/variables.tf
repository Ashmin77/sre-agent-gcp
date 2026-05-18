variable "project_id" { description = "GCP project ID" }
variable "region" { description = "GCP region" }
variable "sre_agent_sa_email" { description = "Service account email" }
variable "cluster_endpoint" { description = "GKE cluster endpoint IP" }
variable "ca_cert_base64" { description = "GKE CA cert base64 encoded" }
variable "image_tag" {
  description = "Container image tag"
  default     = "v1"
}
