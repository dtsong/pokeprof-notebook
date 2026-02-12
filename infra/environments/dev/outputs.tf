output "cloud_run_uri" {
  description = "Service URI."
  value       = module.app.cloud_run_uri
}

output "runtime_service_account" {
  description = "Runtime service account email."
  value       = module.app.runtime_service_account
}
