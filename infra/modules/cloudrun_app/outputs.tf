output "artifact_repository" {
  description = "Artifact Registry repository name."
  value       = google_artifact_registry_repository.images.name
}

output "cloud_run_service_name" {
  description = "Cloud Run service name."
  value       = google_cloud_run_v2_service.this.name
}

output "cloud_run_uri" {
  description = "Cloud Run service URI."
  value       = google_cloud_run_v2_service.this.uri
}

output "runtime_service_account" {
  description = "Runtime service account email."
  value       = google_service_account.runtime.email
}
