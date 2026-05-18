variable "project_id" {
  description = "GCP project ID."
  type        = string
}

variable "region" {
  description = "GCP region for the Cloud Run service."
  type        = string
}

variable "sre_agent_sa_email" {
  description = "SRE agent service account email. Used as the Cloud Run runtime identity."
  type        = string
}

variable "cluster_endpoint" {
  description = "GKE cluster API server endpoint IP. Injected as GKE_CLUSTER_ENDPOINT into the MCP container."
  type        = string
  sensitive   = true
}

variable "ca_cert_base64" {
  description = "GKE cluster CA certificate (base64-encoded). Written to GCS so the MCP server can authenticate to the cluster."
  type        = string
  sensitive   = true
}

variable "image_tag" {
  description = "Container image tag for the sre-k8s-mcp image in Artifact Registry."
  type        = string
  default     = "v1"
}
