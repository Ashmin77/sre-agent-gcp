# ── PROJECT ──────────────────────────────────────────────────────

output "project_id" {
  description = "GCP project ID."
  value       = google_project.sre_agent.project_id
}

output "project_number" {
  description = "GCP project number."
  value       = google_project.sre_agent.number
}

output "region" {
  description = "Primary GCP region."
  value       = var.region
}

# ── NETWORKING ───────────────────────────────────────────────────

output "vpc_name" {
  description = "VPC network name."
  value       = module.networking.network_name
}

output "subnet_name" {
  description = "Primary subnet name."
  value       = module.networking.subnetwork_name
}

output "subnet_cidr" {
  description = "Primary subnet CIDR."
  value       = module.networking.subnetwork_cidr
}

output "pods_cidr" {
  description = "GKE pod IP range."
  value       = module.networking.pods_cidr
}

output "services_cidr" {
  description = "GKE service IP range."
  value       = module.networking.services_cidr
}

output "cloud_nat_name" {
  description = "Cloud NAT gateway name."
  value       = module.networking.nat_name
}

# ── IDENTITY ─────────────────────────────────────────────────────

output "sre_agent_sa_email" {
  description = "SRE agent service account email address."
  value       = module.iam.sre_agent_sa_email
}

output "workload_identity_pool" {
  description = "Workload Identity pool ID."
  value       = "${var.project_id}.svc.id.goog"
}

# ── GKE ──────────────────────────────────────────────────────────

output "gke_cluster_name" {
  description = "Target GKE cluster name (demo or existing)."
  value       = local.gke_cluster_name
}

output "gke_cluster_location" {
  description = "Target GKE cluster region or zone."
  value       = local.gke_cluster_location
}

output "gke_cluster_endpoint" {
  description = "GKE API server endpoint IP address."
  value       = data.google_container_cluster.sre_test.endpoint
  sensitive   = true
}

output "gke_namespace" {
  description = "Target investigation namespace."
  value       = local.gke_cluster_namespace
}

output "gke_connect_command" {
  description = "Run this command to configure kubectl for the cluster."
  value = (var.create_gke_cluster || var.existing_gke_location_type == "region") ?
    "gcloud container clusters get-credentials ${local.gke_cluster_name} --region ${local.gke_cluster_location} --project ${local.gke_cluster_project}" :
    "gcloud container clusters get-credentials ${local.gke_cluster_name} --zone ${local.gke_cluster_location} --project ${local.gke_cluster_project}"
}

# ── MCP SERVER ───────────────────────────────────────────────────

output "mcp_server_url" {
  description = "HTTPS URL of the custom MCP Cloud Run service."
  value       = module.cloudrun.mcp_url
}

output "mcp_image_repo" {
  description = "Artifact Registry repository path for MCP container images."
  value       = module.cloudrun.mcp_image_repo
}

output "mcp_build_command" {
  description = "Run this command to build and push the MCP container image."
  value       = "gcloud builds submit ./mcp --tag=${module.cloudrun.mcp_image_repo}/sre-k8s-mcp:v1 --project=${var.project_id}"
}

output "gke_remote_mcp_url" {
  description = "Google-managed GKE Remote MCP read-only endpoint. This URL is fixed — do not change it."
  value       = "https://container.googleapis.com/mcp/read-only"
}

# ── GCS BUCKETS ──────────────────────────────────────────────────

output "evidence_bucket" {
  description = "GCS evidence bucket name."
  value       = google_storage_bucket.evidence.name
}

output "evidence_bucket_url" {
  description = "GCS evidence bucket URL (gs:// prefix)."
  value       = "gs://${google_storage_bucket.evidence.name}"
}

output "staging_bucket" {
  description = "GCS staging bucket name (Agent Engine deployment artifacts)."
  value       = google_storage_bucket.staging.name
}

output "staging_bucket_url" {
  description = "GCS staging bucket URL (gs:// prefix)."
  value       = "gs://${google_storage_bucket.staging.name}"
}

# ── ALIASES — names used in the operations guide ─────────────────
# These match the `terraform output -raw <name>` commands in the README and guide.

output "agent_service_account_email" {
  description = "Alias for sre_agent_sa_email. Used in README and operations guide commands."
  value       = module.iam.sre_agent_sa_email
}

output "evidence_bucket_name" {
  description = "Alias for evidence_bucket. Used in README and operations guide commands."
  value       = google_storage_bucket.evidence.name
}

output "staging_bucket_name" {
  description = "Alias for staging_bucket. Used in README and operations guide commands."
  value       = google_storage_bucket.staging.name
}

output "custom_mcp_url" {
  description = "Alias for mcp_server_url. Used in README and operations guide commands."
  value       = module.cloudrun.mcp_url
}

# ── SUMMARY ──────────────────────────────────────────────────────

output "summary" {
  description = "Human-readable infrastructure summary. Printed after every apply."
  value       = <<-EOT

    ┌─────────────────────────────────────────────────────┐
    │         SRE Agent GCP Infrastructure                │
    │         Phase 0 Validation Environment              │
    └─────────────────────────────────────────────────────┘

    PROJECT
      ID      : ${var.project_id}
      Number  : ${google_project.sre_agent.number}
      Region  : ${var.region}

    NETWORKING
      VPC     : sre-agent-vpc (10.0.0.0/24)
      Pods    : 10.1.0.0/16
      Services: 10.2.0.0/20
      NAT     : sre-agent-nat (outbound only)

    IDENTITY
      SA      : sre-agent-sa@${var.project_id}.iam.gserviceaccount.com
      WI Pool : ${var.project_id}.svc.id.goog

    GKE CLUSTER
      Name    : sre-test-cluster (Autopilot, ${var.region})
      kubectl : gcloud container clusters get-credentials \
                sre-test-cluster --region ${var.region} \
                --project ${var.project_id}

    MCP SERVER
      URL     : ${module.cloudrun.mcp_url}
      Image   : ${module.cloudrun.mcp_image_repo}/sre-k8s-mcp:v1
      Auth    : IAM identity token (roles/run.invoker)

    GCS BUCKETS
      Evidence: gs://${google_storage_bucket.evidence.name}  (90-day TTL, versioned)
      Staging : gs://${google_storage_bucket.staging.name}   (Agent Engine artifacts)

    NEXT STEPS
      1. Build and push MCP image — run: terraform output -raw mcp_build_command
      2. kubectl apply -f k8s/namespace.yaml
      3. kubectl apply -f k8s/oomkilled-pod.yaml (and other incident pods)
      4. Copy agent/.env.example → agent/.env and fill in values
      5. python run.py "oomkilled-pod keeps getting OOMKilled" --namespace test-incidents
      6. python deploy_agent.py  (after local validation passes)
  EOT
}
