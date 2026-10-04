provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

module "network" {
  source = "../../modules/network"

  project_name = var.project_name
  environment  = var.environment

  vpc_cidr = "10.0.0.0/16"

  availability_zones = [
    "${var.aws_region}a",
    "${var.aws_region}b"
  ]

  public_subnet_cidrs = [
    "10.0.1.0/24",
    "10.0.2.0/24"
  ]

  private_subnet_cidrs = [
    "10.0.11.0/24",
    "10.0.12.0/24"
  ]
}

module "security" {
  source = "../../modules/security"

  project_name = var.project_name
  environment  = var.environment

  vpc_id = module.network.vpc_id

  backend_port = 8000
}

module "rds" {
  source = "../../modules/rds"

  project_name = var.project_name
  environment  = var.environment

  private_subnet_ids = module.network.private_subnet_ids
  security_group_id  = module.security.rds_security_group_id

  db_name     = var.db_name
  db_username = var.db_username
  db_password = var.db_password
}

module "ecr" {
  source = "../../modules/ecr"

  project_name = var.project_name
  environment  = var.environment
}

module "ecr_frontend" {
  source = "../../modules/ecr-frontend"

  project_name = var.project_name
  environment  = var.environment
}

module "s3" {
  source = "../../modules/s3"

  project_name = var.project_name
  environment  = var.environment
}

module "ecs" {
  source = "../../modules/ecs"

  project_name = var.project_name
  environment  = var.environment

  ecr_repository_url        = module.ecr.repository_url
  gemini_api_key_secret_arn = "arn:aws:secretsmanager:eu-west-1:133789123849:secret:crisisconnect/staging/gemini-api-key-GYSxW5"

  s3_bucket_name = module.s3.bucket_name
  s3_bucket_arn  = module.s3.bucket_arn

  database_url = "postgresql+psycopg2://${var.db_username}:${var.db_password}@${module.rds.db_endpoint}:${module.rds.db_port}/${var.db_name}"

  smtp_host      = var.smtp_host
  smtp_port      = var.smtp_port
  smtp_username  = var.smtp_username
  smtp_password  = var.smtp_password
  smtp_from      = var.smtp_from
  smtp_from_name = var.smtp_from_name
  auth_secret    = var.auth_secret

  aws_region = var.aws_region

  private_subnet_ids    = module.network.private_subnet_ids
  ecs_security_group_id = module.security.ecs_security_group_id

  target_group_arn = module.alb.target_group_arn
}

module "alb" {
  source = "../../modules/alb"

  project_name = var.project_name
  environment  = var.environment

  vpc_id                = module.network.vpc_id
  public_subnet_ids     = module.network.public_subnet_ids
  alb_security_group_id = module.security.alb_security_group_id

  backend_port = 8000
}

module "ecs_frontend" {
  source = "../../modules/ecs-frontend"

  project_name       = var.project_name
  environment        = var.environment
  ecr_repository_url = module.ecr_frontend.repository_url
  aws_region         = var.aws_region

  private_subnet_ids    = module.network.private_subnet_ids
  ecs_security_group_id = module.security.ecs_security_group_id
  target_group_arn      = module.alb.frontend_target_group_arn
  cluster_arn           = module.ecs.cluster_arn
}
