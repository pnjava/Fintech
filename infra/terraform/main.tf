terraform {
  required_version = ">= 1.4.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.21"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.11"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

resource "aws_s3_bucket" "audit_logs" {
  bucket = var.audit_log_bucket
}

resource "aws_s3_bucket_lifecycle_configuration" "audit_logs" {
  bucket = aws_s3_bucket.audit_logs.id

  rule {
    id     = "expire-audit-logs"
    status = "Enabled"

    expiration {
      days = var.upload_retention_days
    }
  }
}

resource "aws_s3_bucket" "uploads" {
  bucket = var.upload_bucket
}

resource "aws_s3_bucket_lifecycle_configuration" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  rule {
    id     = "expire-shareholder-uploads"
    status = "Enabled"

    expiration {
      days = var.upload_retention_days
    }
  }
}

resource "helm_release" "fintech" {
  name       = var.release_name
  chart      = "../helm/fintech"
  namespace  = var.namespace
  create_namespace = true

  set {
    name  = "image.repository"
    value = var.image_repository
  }

  set {
    name  = "image.tag"
    value = var.image_tag
  }
}
