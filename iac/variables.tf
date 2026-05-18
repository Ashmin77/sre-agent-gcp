variable "project_id" {
  description = "GCP project ID to create"
  type        = string
}

variable "billing_account" {
  description = "GCP billing account ID"
  type        = string
}

variable "region" {
  description = "Primary GCP region"
  type        = string
  default     = "us-central1"
}

variable "zone" {
  description = "Primary GCP zone"
  type        = string
  default     = "us-central1-a"
}
