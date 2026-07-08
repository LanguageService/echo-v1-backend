resource "aws_s3_bucket" "backend_media" {
  bucket        = "${var.project_name}-${var.environment}-media"
  force_destroy = true # Be careful with this in production!

  tags = {
    Name        = "${var.project_name}-${var.environment}-media"
    Environment = var.environment
  }
}

resource "aws_s3_bucket_public_access_block" "backend_media_block" {
  bucket = aws_s3_bucket.backend_media.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_cors_configuration" "backend_media_cors" {
  bucket = aws_s3_bucket.backend_media.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["PUT", "POST", "GET"]
    allowed_origins = ["*"] # Consider restricting to var.domain_name in strict production
    expose_headers  = ["ETag"]
    max_age_seconds = 3000
  }
}

output "s3_bucket_name" {
  description = "Name of the backend S3 bucket for media"
  value       = aws_s3_bucket.backend_media.id
}
