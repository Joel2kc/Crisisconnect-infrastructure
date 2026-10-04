output "aws_region" {
  description = "AWS region used for the staging environment"
  value       = var.aws_region
}

output "vpc_id" {
  description = "ID of the staging VPC"
  value       = module.network.vpc_id
}

output "public_subnet_ids" {
  description = "IDs of the staging public subnets"
  value       = module.network.public_subnet_ids
}

output "private_subnet_ids" {
  description = "IDs of the staging private subnets"
  value       = module.network.private_subnet_ids
}

output "alb_security_group_id" {
  description = "ID of the ALB security group"
  value       = module.security.alb_security_group_id
}

output "ecs_security_group_id" {
  description = "ID of the ECS security group"
  value       = module.security.ecs_security_group_id
}

output "rds_security_group_id" {
  description = "ID of the RDS security group"
  value       = module.security.rds_security_group_id
}

output "db_endpoint" {
  description = "PostgreSQL database endpoint"
  value       = module.rds.db_endpoint
}

output "db_port" {
  description = "PostgreSQL database port"
  value       = module.rds.db_port
}

output "ecr_repository_url" {
  description = "ECR repository URL"
  value       = module.ecr.repository_url
}

output "ecs_cluster_name" {
  description = "Name of the ECS cluster"
  value       = module.ecs.cluster_name
}

output "ecs_cluster_id" {
  description = "ID of the ECS cluster"
  value       = module.ecs.cluster_id
}

output "ecs_task_execution_role_arn" {
  description = "ARN of the ECS task execution role"
  value       = module.ecs.task_execution_role_arn
}

output "ecs_task_role_arn" {
  description = "ARN of the ECS task role"
  value       = module.ecs.task_role_arn
}
