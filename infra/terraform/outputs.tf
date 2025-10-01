output "audit_log_bucket" {
  description = "Audit log S3 bucket"
  value       = aws_s3_bucket.audit_logs.bucket
}

output "upload_bucket" {
  description = "Upload S3 bucket"
  value       = aws_s3_bucket.uploads.bucket
}
