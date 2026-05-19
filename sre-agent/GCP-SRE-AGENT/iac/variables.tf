# ── ROOT VARIABLES ───────────────────────────────────────────────

variable "project_id" {
  description = "GCP project ID. Must be globally unique. Used as the project to create and as a prefix for resource names."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.project_id))
    error_message = "project_id must be 6–30 characters, start with a lowercase letter, and contain only lowercase letters, digits, and hyphens."
  }
}

variable "billing_account" {
  description = "GCP billing account ID to attach to the project. Format: XXXXXX-XXXXXX-XXXXXX. Find yours with: gcloud billing accounts list"
  type        = string

  validation {
    condition     = can(regex("^[0-9A-F]{6}-[0-9A-F]{6}-[0-9A-F]{6}$", var.billing_account))
    error_message = "billing_account must be in XXXXXX-XXXXXX-XXXXXX format (uppercase hex digits)."
  }
}

variable "region" {
  description = "Primary GCP region for all regional resources (GKE, Cloud Run, GCS, Cloud NAT)."
  type        = string
  default     = "us-central1"

  validation {
    condition     = can(regex("^[a-z]+-[a-z]+[0-9]+$", var.region))
    error_message = "region must be a valid GCP region name, e.g. us-central1 or europe-west1."
  }
}

variable "zone" {
  description = "Primary GCP zone. Must be within var.region (e.g. us-central1-a when region is us-central1)."
  type        = string
  default     = "us-central1-a"

  validation {
    condition     = can(regex("^[a-z]+-[a-z]+[0-9]+-[a-z]$", var.zone))
    error_message = "zone must be a valid GCP zone name, e.g. us-central1-a."
  }
}

# ── EXISTING CLUSTER MODE ─────────────────────────────────────────
# Set create_gke_cluster = false and supply the values below to point
# the agent at a GKE cluster you already operate instead of creating
# a new demo cluster. See README Path 2 and Appendix A for full steps.

variable "create_gke_cluster" {
  description = "When true, Terraform creates a new GKE Autopilot demo cluster. Set to false to use an existing cluster (supply existing_gke_* variables below)."
  type        = bool
  default     = true
}

variable "existing_gke_project_id" {
  description = "Project ID of the existing GKE cluster. Only used when create_gke_cluster = false."
  type        = string
  default     = null
}

variable "existing_gke_cluster" {
  description = "Name of the existing GKE cluster. Only used when create_gke_cluster = false."
  type        = string
  default     = null
}

variable "existing_gke_location" {
  description = "Region or zone of the existing GKE cluster. Only used when create_gke_cluster = false."
  type        = string
  default     = null
}

variable "existing_gke_location_type" {
  description = "Whether existing_gke_location is a region or zone. Must be 'region' or 'zone'."
  type        = string
  default     = "region"

  validation {
    condition     = contains(["region", "zone"], var.existing_gke_location_type)
    error_message = "existing_gke_location_type must be 'region' or 'zone'."
  }
}

variable "existing_gke_namespace" {
  description = "Kubernetes namespace to investigate on the existing cluster. Only used when create_gke_cluster = false."
  type        = string
  default     = "default"
}
