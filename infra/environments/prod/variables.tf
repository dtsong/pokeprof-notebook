variable "project_id" {
  description = "Target project id."
  type        = string
  default     = "pokeprof-prod"
  nullable    = false
}

variable "region" {
  description = "Deployment region."
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
  description = "Artifact Registry repository id."
  type        = string
  default     = "pokeprof"
  nullable    = false
}

variable "concurrency" {
  description = "Max concurrent requests per instance."
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
  description = "Minimum instances."
  type        = number
  default     = 0
  nullable    = false
}

variable "max_instances" {
  description = "Maximum instances."
  type        = number
  default     = 200
  nullable    = false
}

variable "invoker_iam_disabled" {
  description = "Disable invoker IAM checks for Cloud Run."
  type        = bool
  default     = true
  nullable    = false
}

variable "enable_deletion_protection" {
  description = "Prevent accidental destroy of Cloud Run service."
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

variable "deploy_cloud_run" {
  description = "Whether to deploy the Cloud Run service (set false for first apply to create APIs/secrets before adding secret versions)."
  type        = bool
  default     = true
  nullable    = false
}
