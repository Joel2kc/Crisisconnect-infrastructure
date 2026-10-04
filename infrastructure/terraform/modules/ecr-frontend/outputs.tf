output "repository_url" {
  description = "URL of the frontend ECR repository"
  value       = aws_ecr_repository.this.repository_url
}

output "repository_name" {
  description = "Name of the frontend ECR repository"
  value       = aws_ecr_repository.this.name
}
