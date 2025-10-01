# Terraform Stubs

This module provisions S3 buckets with lifecycle policies that match the `DataRetentionService` defaults and deploys the Helm chart.

## Usage
```hcl
module "fintech" {
  source = "./infra/terraform"

  aws_region          = "us-east-1"
  audit_log_bucket    = "fintech-audit-logs"
  upload_bucket       = "fintech-uploads"
  image_repository    = "ghcr.io/your-org/fintech"
  image_tag           = "v0.1.0"
  upload_retention_days = 365
}
```

Run:
```bash
terraform init
terraform plan
```
