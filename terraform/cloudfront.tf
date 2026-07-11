# 1. Provide your variables here
variable "api_domain_name" {
  description = "The domain name for your API (e.g. api.yourdomain.com)"
  type        = string
}

variable "ec2_origin_dns" {
  description = "The Elastic IP or Public DNS of your backend EC2 instance"
  type        = string
}

# 2. REQUIRED: A separate provider for us-east-1 for the CloudFront Certificate
provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"
}

# 3. Request the Certificate (in us-east-1)
resource "aws_acm_certificate" "api_cert" {
  provider          = aws.us_east_1
  domain_name       = var.api_domain_name
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

# Output the DNS records you need to add to your DNS provider (e.g., GoDaddy, Namecheap)
output "certificate_dns_validation_records" {
  value = {
    for dvo in aws_acm_certificate.api_cert.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      type   = dvo.resource_record_type
      record = dvo.resource_record_value
    }
  }
  description = "Add these CNAME records to your DNS provider to validate the certificate."
}

# 4. Create the CloudFront Distribution for the API
resource "aws_cloudfront_distribution" "api_cdn" {
  enabled = true
  aliases = [var.api_domain_name]

  origin {
    domain_name = var.ec2_origin_dns
    origin_id   = "EC2Backend"

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "http-only" # CloudFront talks to EC2 via HTTP
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  default_cache_behavior {
    target_origin_id = "EC2Backend"
    
    # Allow all methods for an API (POST, PUT, DELETE, etc.)
    allowed_methods = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods  = ["GET", "HEAD"]
    viewer_protocol_policy = "redirect-to-https"

    # AWS Managed Policy: CachingDisabled (Critical for dynamic APIs)
    cache_policy_id = "4135ea2d-6df8-44a3-9df3-4b5a84be39ad"

    # AWS Managed Policy: AllViewer (Passes Authorization, Host, and all headers to EC2)
    origin_request_policy_id = "216adef6-5c7f-47e4-b989-5492eafa07d3" 
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    acm_certificate_arn      = aws_acm_certificate.api_cert.arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }
}

# Output the CloudFront domain name so you know what to point your domain to
output "cloudfront_domain_name" {
  value       = aws_cloudfront_distribution.api_cdn.domain_name
  description = "Once CloudFront is deployed, point your domain (CNAME) to this address."
}
