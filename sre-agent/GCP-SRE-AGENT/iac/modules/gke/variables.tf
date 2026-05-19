variable "project_id" {
  description = "GCP project ID."
  type        = string
}

variable "region" {
  description = "GCP region for the GKE Autopilot cluster."
  type        = string
}

variable "network_id" {
  description = "VPC network self-link ID. Must already exist (passed from networking module)."
  type        = string
}

variable "subnetwork_id" {
  description = "Subnetwork self-link ID. Must already exist (passed from networking module)."
  type        = string
}

variable "sre_agent_sa_email" {
  description = "SRE agent service account email. Used for the Workload Identity pool binding."
  type        = string
}

variable "sre_agent_sa_name" {
  description = "SRE agent service account full resource name. Used for the IAM member binding."
  type        = string
}
