provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}

module "app" {
  source = "../../modules/cloudrun_app"

  project_id   = var.project_id
  region       = var.region
  service_name = var.service_name
  image        = var.image

  artifact_repo_id           = var.artifact_repo_id
  concurrency                = var.concurrency
  timeout_seconds            = var.timeout_seconds
  min_instances              = var.min_instances
  max_instances              = var.max_instances
  invoker_iam_disabled       = var.invoker_iam_disabled
  enable_deletion_protection = var.enable_deletion_protection
}
