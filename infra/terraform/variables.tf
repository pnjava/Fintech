variable "aws_region" {
  type        = string
  description = "AWS region for resources"
  default     = "us-east-1"
}

variable "audit_log_bucket" {
  type        = string
  description = "S3 bucket name for audit logs"
  default     = "fintech-audit-logs"
}

variable "upload_bucket" {
  type        = string
  description = "S3 bucket for shareholder uploads"
  default     = "fintech-uploads"
}

variable "upload_retention_days" {
  type        = number
  description = "Retention window for uploads and audit logs"
  default     = 180
}

variable "release_name" {
  type        = string
  description = "Helm release name"
  default     = "fintech"
}

variable "namespace" {
  type        = string
  description = "Kubernetes namespace"
  default     = "fintech"
}

variable "image_repository" {
  type        = string
  description = "Container image repository"
  default     = "ghcr.io/example/fintech"
}

variable "image_tag" {
  type        = string
  description = "Container image tag"
  default     = "latest"
}
