variable "aws_region" {
  description = "The AWS region to deploy resources into"
  type        = string
  default     = "eu-west-1"
}

variable "project_name" {
  description = "Project name used as a prefix for resources"
  type        = string
  default     = "letecho"
}

variable "environment" {
  description = "Environment name (e.g. prod, staging, dev)"
  type        = string
  default     = "prod"
}

variable "domain_name" {
  description = "Domain name for the frontend and API (e.g., letecho.com)"
  type        = string
  default     = "letecho.com"
}

variable "db_username" {
  description = "PostgreSQL admin username"
  type        = string
  sensitive   = true
  default = "echouser"
}

variable "db_password" {
  description = "PostgreSQL admin password"
  type        = string
  sensitive   = true
  default = "letThemECHO2026"
}



variable "ec2_instance_type" {
  description = "The instance type for the EC2 server"
  type        = string
  default     = "t3.medium"
}

variable "ec2_key_name" {
  description = "The name of the SSH key pair to use for EC2 access"
  type        = string
  default     = "letecho-key"
}
