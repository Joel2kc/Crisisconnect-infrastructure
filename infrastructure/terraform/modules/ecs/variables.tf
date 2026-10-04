variable "project_name" {
  description = "Name of the project"
  type        = string
}

variable "environment" {
  description = "Deployment environment"
  type        = string
}

variable "ecr_repository_url" {
  description = "ECR repository URL"
  type        = string
}

variable "database_url" {
  description = "PostgreSQL database connection URL"
  type        = string
  sensitive   = true
}

variable "smtp_host" {
  description = "SMTP server host"
  type        = string
}

variable "smtp_port" {
  description = "SMTP server port"
  type        = string
}

variable "smtp_username" {
  description = "SMTP username"
  type        = string
  sensitive   = true
}

variable "smtp_password" {
  description = "SMTP password"
  type        = string
  sensitive   = true
}

variable "smtp_from" {
  description = "Email sender address"
  type        = string
}

variable "smtp_from_name" {
  description = "Email sender name"
  type        = string
}

variable "auth_secret" {
  description = "Secret key used for authentication"
  type        = string
  sensitive   = true
}

variable "aws_region" {
  description = "AWS region"
  type        = string
}

variable "private_subnet_ids" {
  description = "Private subnet IDs for ECS tasks"
  type        = list(string)
}

variable "ecs_security_group_id" {
  description = "Security group ID for ECS tasks"
  type        = string
}

variable "target_group_arn" {
  description = "ARN of the ALB target group"
  type        = string
}

variable "s3_bucket_name" {
  description = "S3 bucket name used for document storage"
  type        = string
}

variable "s3_bucket_arn" {
  description = "S3 bucket ARN used for document storage permissions"
  type        = string
}

variable "gemini_api_key_secret_arn" {
  description = "ARN of the AWS Secrets Manager secret containing the Gemini API key"
  type        = string
}
