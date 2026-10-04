output "db_endpoint" {
  description = "Connection endpoint for the PostgreSQL database"
  value       = aws_db_instance.this.address
}

output "db_port" {
  description = "Port used by the PostgreSQL database"
  value       = aws_db_instance.this.port
}

output "db_identifier" {
  description = "Identifier of the RDS instance"
  value       = aws_db_instance.this.identifier
}
