🚀 Project Overview
Crisis Connect is an emergency reporting, incident management, and agency coordination platform. During my internship at KodeCamp, I focused on the DevOps and cloud infrastructure side of the project, building scalable cloud architectures, setting up reliable CI/CD pipelines, containerizing services, and ensuring robust monitoring and troubleshooting workflows.

🏗️ AWS Infrastructure & Architecture
The infrastructure is provisioned and managed using Terraform, with application services deployed as Docker containers on AWS ECS Fargate.

VPC & Networking
I established a secure and isolated networking foundation within AWS:

VPC spanning public and private subnets across availability zones.

Internet Gateway & NAT Gateway to allow outbound internet access for private resources while shielding them from inbound threats.

Route Tables & Security Groups enforcing strict least-privilege traffic flow, keeping database instances securely inside private subnets.

Compute & Load Balancing
Amazon ECS Fargate: The backend API and informational frontend run as serverless container services, removing the operational overhead of managing underlying servers while enabling seamless deployments via CI/CD.

Application Load Balancer (ALB): Sits in front of ECS services to handle incoming traffic, intelligently routing API traffic to the backend and web traffic to the frontend, backed by automated health checks.

Amazon ECR: Stores version-controlled Docker images used by the ECS services.

Data, Storage & Secrets
Amazon RDS PostgreSQL: Manages core application data, with schema migrations handled reliably via Alembic.

Amazon S3: Used for secure application file and document storage, integrated via fine-grained IAM permissions.

AWS CloudWatch: Centralizes application and container logs for deep inspection during deployment troubleshooting and runtime error analysis.

AWS Secrets Manager: Secures sensitive runtime configurations (such as the Gemini API key used for AI-assisted incident triage) and injects them securely into ECS tasks at runtime.

🔄 CI/CD & Automation
To eliminate manual deployment errors, I built automated CI/CD pipelines using GitHub Actions.

Backend & Frontend Deployment Flow
Plaintext
GitHub ---> GitHub Actions ---> Docker Build ---> Amazon ECR ---> Amazon ECS ---> Health Check
The pipeline automates building container images, publishing them to ECR, updating the ECS task definitions, and verifying service health post-deployment.

Mobile Delivery Workflow
For the Crisis Connect Android mobile application, I configured an automated distribution pipeline to streamline testing:

Plaintext
Mobile Code ---> GitHub Actions ---> Android APK Build ---> Firebase App Distribution ---> Testers & Team Members
This integration eliminated manual APK builds and ad-hoc file transfers, instantly delivering fresh builds to QA and team members upon code pushes.

🛠️ Technology Stack
Cloud & Infrastructure: AWS (ECS Fargate, ECR, ALB, VPC, RDS PostgreSQL, S3, CloudWatch, Secrets Manager, NAT Gateway), Terraform

Containerization & CI/CD: Docker, GitHub Actions, Firebase App Distribution

Application & Database: Python, FastAPI, PostgreSQL, Alembic, Gemini API

Mobile Delivery: Android APK Build Pipelines

📂 Repository Structure
The infrastructure code is modularized for maintainability across environments:

Plaintext
infrastructure/
└── terraform/
    ├── modules/
    │   ├── ecr/
    │   ├── ecr-frontend/
    │   ├── ecs/
    │   ├── ecs-frontend/
    │   ├── network/
    │   └── s3/
    │
    └── environments/
        └── staging/
🔍 Key Engineering Challenges & Solutions
Working through production hurdles provided hands-on experience in end-to-end debugging:

Container Port Mismatches: Traced discrepancies between the application's exposed port, Dockerfile directives, and ECS service definitions to restore successful load balancer communication.

Database Migration Drift: Resolved synchronization issues where the staging database lagged behind advanced Alembic migration revisions by inspecting the migration chain and applying targeted updates.

Observability: Leveraged CloudWatch log insights to diagnose container startup failures, IAM permission gaps, and internal network connectivity issues.