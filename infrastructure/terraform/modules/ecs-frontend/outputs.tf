output "service_name" {
  description = "Name of the frontend ECS service"
  value       = aws_ecs_service.this.name
}

output "task_definition_arn" {
  description = "ARN of the frontend ECS task definition"
  value       = aws_ecs_task_definition.this.arn
}
