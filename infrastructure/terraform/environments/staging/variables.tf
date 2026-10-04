variable "aws_region" {
  description = "AWS region for the staging environment"
  type        = string
  default     = "eu-west-1"
}

variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "crisisconnect"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "staging"
}

variable "db_name" {
  description = "Name of the PostgreSQL database"
  type        = string
  default     = "crisisconnect"
}

variable "db_username" {
  description = "Master username for the PostgreSQL database"
  type        = string
  sensitive   = true
}

variable "db_password" {
  description = "Master password for the PostgreSQL database"
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