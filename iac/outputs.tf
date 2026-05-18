# ── PROJECT ──────────────────────────────────────────────────────
output "project_id" {
  description = "GCP project ID"
  value       = google_project.sre_agent.project_id
}

output "project_number" {
  description = "GCP project number"
  value       = google_project.sre_agent.number
}

output "region" {
  description = "Primary region"
  value       = var.region
}

# ── NETWORKING ───────────────────────────────────────────────────
output "vpc_name" {
  description = "VPC network name"
  value       = module.networking.network_name
}

output "subnet_name" {
  description = "Primary subnet name"
  value       = module.networking.subnetwork_name
}

output "subnet_cidr" {
  description = "Primary subnet CIDR"
  value       = module.networking.subnetwork_cidr
}

output "pods_cidr" {
  description = "GKE pod IP range"
  value       = module.networking.pods_cidr
}

output "services_cidr" {
  description = "GKE service IP range"
  value       = module.networking.services_cidr
}

output "cloud_nat_name" {
  description = "Cloud NAT name"
  value       = module.networking.nat_name
}

# ── IDENTITY ─────────────────────────────────────────────────────
output "sre_agent_sa_email" {
  description = "Service account email — agent identity"
  value       = module.iam.sre_agent_sa_email
}

output "workload_identity_pool" {
  description = "Workload Identity pool"
  value       = "${var.project_id}.svc.id.goog"
}

# ── GKE ──────────────────────────────────────────────────────────
output "gke_cluster_name" {
  description = "GKE cluster name"
  value       = module.gke.cluster_name
}

output "gke_cluster_location" {
  description = "GKE cluster region"
  value       = module.gke.cluster_location
}

output "gke_cluster_endpoint" {
  description = "GKE API server endpoint"
  value       = module.gke.cluster_endpoint
  sensitive   = true
}

output "gke_connect_command" {
  description = "Connect kubectl to cluster"
  value       = "gcloud container clusters get-credentials ${module.gke.cluster_name} --region ${var.region} --project ${var.project_id}"
}

# ── MCP SERVER ───────────────────────────────────────────────────
output "mcp_server_url" {
  description = "Cloud Run MCP server URL"
  value       = module.cloudrun.mcp_url
}

output "mcp_image_repo" {
  description = "Artifact Registry repo for MCP container"
  value       = module.cloudrun.mcp_image_repo
}

output "mcp_build_command" {
  description = "Rebuild and push MCP container"
  value       = "gcloud builds submit ./mcp --tag=${module.cloudrun.mcp_image_repo}/sre-k8s-mcp:v1 --project=${var.project_id}"
}

output "gke_remote_mcp_url" {
  description = "Google-managed GKE Remote MCP read-only endpoint"
  value       = "https://container.googleapis.com/mcp/read-only"
}

# ── GCS EVIDENCE ─────────────────────────────────────────────────
output "evidence_bucket" {
  description = "GCS evidence bucket name"
  value       = google_storage_bucket.evidence.name
}

output "evidence_bucket_url" {
  description = "GCS evidence bucket URL"
  value       = "gs://${google_storage_bucket.evidence.name}"
}

# ── GCS STAGING ──────────────────────────────────────────────────
output "staging_bucket" {
  description = "GCS staging bucket name (Agent Engine artifacts)"
  value       = google_storage_bucket.staging.name
}

output "staging_bucket_url" {
  description = "GCS staging bucket URL"
  value       = "gs://${google_storage_bucket.staging.name}"
}

# ── OUTPUT ALIASES — names used in the operations guide ──────────
# These match the `terraform output -raw <name>` commands in the guide.
output "agent_service_account_email" {
  description = "Service account email (guide alias for sre_agent_sa_email)"
  value       = module.iam.sre_agent_sa_email
}

output "evidence_bucket_name" {
  description = "Evidence bucket name (guide alias for evidence_bucket)"
  value       = google_storage_bucket.evidence.name
}

output "staging_bucket_name" {
  description = "Staging bucket name (guide alias for staging_bucket)"
  value       = google_storage_bucket.staging.name
}

output "custom_mcp_url" {
  description = "Custom MCP Cloud Run URL (guide alias for mcp_server_url)"
  value       = module.cloudrun.mcp_url
}

# ── SUMMARY ──────────────────────────────────────────────────────
output "summary" {
  description = "Infrastructure summary"
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
      Roles   : container.viewer + clusterViewer + logging + monitoring
                + aiplatform + cloudtrace + storage (evidence bucket only)

    GKE CLUSTER
      Name    : sre-test-cluster (Autopilot, us-central1)
      kubectl : gcloud container clusters get-credentials \
                sre-test-cluster --region ${var.region} \
                --project ${var.project_id}

    MCP SERVER
      URL     : ${module.cloudrun.mcp_url}
      Image   : ${module.cloudrun.mcp_image_repo}/sre-k8s-mcp:v1
      Auth    : IAM identity token (roles/run.invoker)

    EVIDENCE STORE
      Bucket  : gs://${google_storage_bucket.evidence.name}
      TTL     : 90 days
      CA Cert : gs://${google_storage_bucket.evidence.name}/config/ca.crt

    NEXT STEPS
      1. kubectl apply -f k8s/namespace.yaml
      2. kubectl apply -f k8s/imagepull-pod.yaml
      3. python run.py "pod imagepull-pod is in ImagePullBackOff" \
             --namespace test-incidents --pod imagepull-pod
      4. python deploy_agent.py  (after local validation)
  EOT
}
