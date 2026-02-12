variable "project_id" {
  description = "GCP project id (e.g., pokeprof-dev)."
  type        = string
  nullable    = false
}

variable "region" {
  description = "GCP region for Cloud Run and Artifact Registry."
  type        = string
  default     = "us-central1"
  nullable    = false
}

variable "service_name" {
  description = "Cloud Run service name."
  type        = string
  default     = "pokeprof"
  nullable    = false
}

variable "image" {
  description = "Container image URI to deploy."
  type        = string
  nullable    = false
}

variable "artifact_repo_id" {
  description = "Artifact Registry repository id for Docker images."
  type        = string
  default     = "pokeprof"
  nullable    = false
}

variable "concurrency" {
  description = "Max concurrent requests per instance (SSE holds connections open)."
  type        = number
  default     = 20
  nullable    = false
}

variable "timeout_seconds" {
  description = "Request timeout in seconds."
  type        = number
  default     = 900
  nullable    = false
}

variable "min_instances" {
  description = "Minimum instances (0 for scale-to-zero; set to 1 during events to reduce cold starts)."
  type        = number
  default     = 0
  nullable    = false
}

variable "max_instances" {
  description = "Maximum instances."
  type        = number
  default     = 100
  nullable    = false
}

variable "invoker_iam_disabled" {
  description = "Disable IAM invoker checks (requires org policy exception)."
  type        = bool
  default     = true
  nullable    = false
}

variable "firestore_location_id" {
  description = "Firestore database location id (e.g., nam5)."
  type        = string
  default     = "nam5"
  nullable    = false
}

variable "enable_deletion_protection" {
  description = "Prevent accidental destroy of Cloud Run service."
  type        = bool
  default     = false
  nullable    = false
}
