# Crisis Connect — AWS Infrastructure and DevOps

## Project Overview

Crisis Connect is an emergency-response platform built around a mobile application that allows users to report emergencies and supports coordination between agencies, responders, and volunteers. The platform includes functionality for incident management, location tracking, geofencing, AI-assisted incident triage, and file storage.

My contribution focused on the DevOps and cloud infrastructure side of the project. I worked on provisioning AWS infrastructure with Terraform, containerizing the backend and informational web frontend, automating deployments with GitHub Actions, and troubleshooting issues across the application and its supporting services.

The goal was to make deployments repeatable, keep the infrastructure organized as code, and provide a reliable environment for running and testing the application.

## Key Contributions

- Provisioned AWS infrastructure using Terraform.
- Organized infrastructure code into reusable modules and environment-specific configuration.
- Containerized the backend and informational web frontend using Docker.
- Deployed application containers to Amazon ECS Fargate.
- Configured Amazon ECR to store application container images.
- Configured an Application Load Balancer to route requests to the appropriate ECS service.
- Set up VPC networking, public and private subnets, route tables, security groups, and NAT connectivity.
- Used Amazon RDS PostgreSQL for application data storage.
- Configured Amazon S3 for application files and documents.
- Used AWS Secrets Manager to manage sensitive application configuration.
- Implemented GitHub Actions workflows for building, publishing, and deploying application images.
- Set up CI/CD for the mobile repository to build Android APKs and distribute them through Firebase App Distribution.
- Used Amazon CloudWatch logs to investigate deployment failures and application runtime issues.
- Troubleshot container port mismatches, load balancer health checks, service connectivity, application configuration, and database migration issues.

## Architecture Overview

The infrastructure runs the backend and informational web frontend as separate containerized services on Amazon ECS Fargate.

The Application Load Balancer provides the application entry point and routes incoming traffic to the appropriate service.

```text
                         Users
                           |
                           v
                Application Load Balancer
                           |
              +------------+------------+
              |                         |
              v                         v
       Frontend ECS              Backend ECS
       Fargate Service           Fargate Service
                                      |
                    +-----------------+-----------------+
                    |                 |                 |
                    v                 v                 v
               RDS PostgreSQL        S3             Gemini API
                 Database       File Storage       AI Services
```

The main infrastructure components have the following responsibilities:

- **Amazon VPC:** Provides the network boundary for the application resources.
- **Public and private subnets:** Separate network placement for application entry points and internal resources.
- **Internet Gateway and NAT Gateway:** Provide the required network connectivity for public entry points and outbound traffic from private resources.
- **Security groups:** Control traffic between the load balancer, application services, and database.
- **Application Load Balancer:** Routes incoming requests to the frontend or backend service.
- **Amazon ECS Fargate:** Runs the application containers without requiring management of individual EC2 hosts.
- **Amazon ECR:** Stores Docker images used by the ECS services.
- **Amazon RDS PostgreSQL:** Stores application data.
- **Amazon S3:** Stores application files and documents.
- **AWS Secrets Manager:** Stores sensitive application configuration used at runtime.
- **Amazon CloudWatch:** Collects container logs for troubleshooting.

The infrastructure was defined using Terraform, while GitHub Actions automated the application build and deployment workflow.

## AWS Infrastructure

### 1. Infrastructure as Code with Terraform

Terraform was used to provision and manage the AWS resources required by the application.

The configuration was organized into reusable modules rather than placing every resource in one large configuration file.

The main modules included:

- `network` — VPC and networking resources.
- `ecr` — backend container registry.
- `ecr-frontend` — frontend container registry.
- `ecs` — backend ECS resources.
- `ecs-frontend` — frontend ECS resources.
- `s3` — application file storage.

Environment-specific configuration was maintained under the staging environment directory.

This structure made the infrastructure easier to understand and allowed individual components to be managed independently.

### 2. Networking

The networking configuration included:

- VPC.
- Public subnets.
- Private subnets.
- Internet Gateway.
- NAT Gateway.
- Route tables.
- Security groups.

The network configuration supported communication between the load balancer, ECS services, and database while restricting access to internal resources.

The Application Load Balancer served as the external entry point for application traffic. The backend and database communicated through their configured network paths and security group rules.

### 3. Amazon ECS Fargate

The backend and informational web frontend were deployed as separate ECS Fargate services.

Separating the services allowed each application component to have its own container image, task configuration, and deployment workflow.

ECS handled the scheduling and execution of the containers without requiring direct management of the underlying compute hosts.

### 4. Amazon ECR

Amazon Elastic Container Registry was used to store the Docker images built by the CI/CD workflows.

The deployment process followed this sequence:

```text
Application Code
       |
       v
GitHub Actions
       |
       v
Docker Image Build
       |
       v
Amazon ECR
       |
       v
Amazon ECS Deployment
       |
       v
Application Health Check
```

This separated the image build and publishing process from the infrastructure that ran the containers.

### 5. Application Load Balancer

The Application Load Balancer received incoming application traffic and routed requests according to the configured listener rules.

API requests were routed to the backend target group, while other web requests were routed to the frontend target group.

Health checks were configured to determine whether application targets were responding correctly.

During troubleshooting, I traced issues across the container port, ECS service configuration, target group, and load balancer health check to identify and correct connectivity mismatches.

### 6. Amazon RDS PostgreSQL

Amazon RDS PostgreSQL provided the database service used by the backend.

Database schema changes were managed with Alembic migrations.

One issue encountered during deployment was a mismatch between the migration revision expected by the application and the revision recorded by the staging database.

I investigated the migration history, identified the missing migrations, and applied the required migrations to bring the database schema up to date with the application code.

This reinforced the importance of treating database migrations as part of the deployment process rather than assuming that deploying a new container automatically updates the database schema.

### 7. Amazon S3

Amazon S3 was used for application file and document storage.

The backend was configured with the IAM permissions required to access the bucket.

Separating document storage from the application containers meant that uploaded files did not need to be stored inside the container filesystem.

### 8. AWS Secrets Manager

AWS Secrets Manager was used to store sensitive application configuration.

The backend required configuration for external services, including the Gemini API used by the AI-assisted incident triage functionality.

Sensitive values were managed through Secrets Manager and supplied to the application at runtime instead of being committed to source control.

Secret values, AWS credentials, and other sensitive configuration are not included in this repository.

### 9. Amazon CloudWatch

CloudWatch was used to collect application and container logs.

I used the logs to investigate startup failures, API errors, and other runtime problems.

This helped distinguish between infrastructure deployment issues and failures occurring inside the application itself.

## CI/CD with GitHub Actions

GitHub Actions was used to automate application build and deployment tasks.

The backend and frontend deployment process followed this general flow:

```text
       GitHub Repository
              |
              v
       GitHub Actions
              |
              v
       Build Docker Image
              |
              v
       Publish Image to ECR
              |
              v
       Update ECS Service
              |
              v
       Verify Application Health
```

The workflow automated the repetitive steps required to build application images, publish them to ECR, and deploy updated images to ECS.

The intended outcome was a repeatable deployment process with fewer manual steps.

The exact workflow triggers, test commands, AWS authentication method, and deployment configuration are defined in the repository's workflow files.

## Mobile CI/CD

The mobile application is the primary product behind Crisis Connect. I also worked on automating the mobile build and distribution process.

The workflow followed this sequence:

```text
       Mobile Source Code
              |
              v
       GitHub Actions
              |
              v
       Build Android APK
              |
              v
       Firebase App Distribution
              |
              v
       Testers and Team Members
```

The workflow built Android APKs and distributed the generated builds through Firebase App Distribution to the configured testers and team members.

This reduced the need to build APKs manually and send them to testers each time a new build was available.

Firebase credentials and other sensitive values should be configured through GitHub Actions secrets rather than committed to the repository.

## Containerization with Docker

Docker was used to package the backend and informational frontend into container images.

Containerization provided a consistent packaging format for the application and made it possible to deploy the same image through the CI/CD process.

The general workflow was:

1. Build the application image.
2. Tag the image for the appropriate ECR repository.
3. Push the image to Amazon ECR.
4. Deploy the updated image through ECS.
5. Check the application through the configured health endpoint and load balancer.

One issue I resolved during the project involved a mismatch between the port exposed by the application and the port expected by the container hosting configuration.

I traced the settings through the Dockerfile, container startup configuration, and ECS service, corrected the port mapping, and verified that the application was reachable through the load balancer.

This demonstrated why container port configuration and load balancer health checks must agree with the application listening port.

## Application Features Supported

The infrastructure supported backend functionality for:

- Emergency reporting.
- Incident management.
- Agency coordination.
- Responder workflows.
- Volunteer workflows.
- Location tracking.
- Geofencing.
- AI-assisted incident triage.
- File and document storage.

The application itself was developed separately from the infrastructure configuration. My work focused on providing the cloud environment and deployment workflows needed to run its services.

## Troubleshooting and Lessons Learned

A significant part of the project involved diagnosing issues across the application and its AWS environment.

### Container port mismatch

The application was not responding as expected because the container port and hosting configuration did not match.

I traced the configuration through the Dockerfile, container startup command, ECS service, and load balancer target group. After correcting the port configuration, I verified application access through the load balancer.

### Database migration mismatch

The application code contained newer database migrations than the staging database had applied.

I checked the Alembic migration history, identified the missing revisions, and applied the required migrations to align the database with the deployed application.

### ECS and load balancer troubleshooting

I investigated ECS task deployment problems and target health failures by checking the service configuration, application listening port, target group settings, and container logs.

This helped identify whether a problem came from container startup, network connectivity, or the load balancer configuration.

### Application configuration and API failures

I used CloudWatch logs and application responses to investigate configuration problems and API failures.

This reinforced the importance of validating runtime configuration and checking application logs instead of relying solely on a successful infrastructure deployment.

### Lessons learned

The project reinforced several practical lessons:

- A successful Terraform apply does not guarantee that the application is healthy.
- Container ports, ECS configuration, and load balancer health checks must agree.
- Database migrations must be applied in step with application changes.
- Logs are essential for understanding failures that are not visible in deployment status alone.
- Secrets should be managed separately from application source code.
- Repeatable deployments require consistent image tagging, configuration, and verification steps.

## Repository Structure

The Terraform configuration is organized into reusable modules and staging environment configuration.

```text
infrastructure/
└── terraform/
    ├── modules/
    │   ├── ecr/
    │   ├── ecr-frontend/
    │   ├── ecs/
    │   ├── ecs-frontend/
    │   ├── network/
    │   └── s3/
    └── environments/
        └── staging/
```

The application repository also contains the application code, Docker configuration, and CI/CD workflow files used by the deployment process.

Refer to the actual repository contents for the complete file structure and implementation details.

## Deployment and Reproduction

The infrastructure was originally provisioned in AWS using Terraform and the application was deployed through ECS Fargate.

The following steps describe the general process for reviewing and reproducing the setup. They assume access to an AWS account, the required permissions, the application source code, and the configuration used by the Terraform environment.

### Prerequisites

Install and configure:

- Terraform.
- AWS CLI.
- Docker.
- Git.
- Access to the application repository.
- An AWS account with the required resource quotas and permissions.

The AWS region used for the staging deployment was `eu-west-1`.

### Configure AWS access

Configure AWS credentials using an approved authentication method, such as an AWS CLI profile or GitHub Actions role-based authentication.

Do not commit AWS access keys or secret credentials to the repository.

### Review the Terraform configuration

Navigate to the Terraform environment directory:

```bash
cd infrastructure/terraform/environments/staging
```

Initialize Terraform:

```bash
terraform init
```

Format and validate the configuration:

```bash
terraform fmt -recursive
terraform validate
```

Review the proposed infrastructure changes:

```bash
terraform plan
```

Review the plan carefully before applying any changes.

The existing environment, Terraform state, and AWS resources must be checked before running `terraform apply`. Do not recreate or destroy resources blindly if the environment has already been provisioned or partially removed.

### Build and publish application images

Build the appropriate Docker image using the repository's Dockerfile.

Tag the image for the corresponding ECR repository and push it using an authenticated AWS CLI session.

The exact build commands depend on the Dockerfile location, build context, repository name, and image tagging strategy in the project.

### Deploy through CI/CD

Configure the required GitHub Actions variables, secrets, and AWS permissions.

Trigger the workflow using the branch or event configured in the repository.

The workflow should build and publish the image, update the ECS service, and perform the health checks defined in the pipeline.

Consult the actual workflow files for the precise commands and required configuration.

### Verify the deployment

After deployment, verify:

- ECS tasks reach the expected running state.
- The load balancer reports healthy targets.
- The application health endpoint responds as expected.
- Backend API requests reach the backend service.
- The frontend is reachable through the load balancer.
- CloudWatch contains the expected application logs.
- The backend can connect to PostgreSQL and required external services.

A successful deployment should be verified from the application's response, not solely from the pipeline status.

## Design Decisions

### ECS Fargate instead of managing EC2 hosts

ECS Fargate allowed the application to run as containers without requiring direct management of the underlying container hosts.

This kept the deployment focused on the application and its task configuration.

### Terraform modules

The infrastructure was divided into reusable modules to keep networking, registries, container services, and storage logically separated.

This structure improved readability and made the configuration easier to maintain.

### Separate frontend and backend services

Running the frontend and backend as separate ECS services kept their container images and deployments independent while allowing the load balancer to route traffic to the appropriate service.

### RDS for database management

Amazon RDS PostgreSQL provided a managed database service rather than requiring the team to operate a database server inside an application container.

### S3 for document storage

S3 provided a separate storage location for application files and documents instead of relying on the lifecycle of application containers.

### Secrets Manager for sensitive configuration

Secrets Manager separated sensitive runtime configuration from the source code and Terraform configuration.

### GitHub Actions for automation

GitHub Actions was already integrated into the development workflow and provided a practical way to automate image builds, publishing, and deployments.

### CloudWatch for troubleshooting

CloudWatch provided access to container logs needed to diagnose startup problems, API failures, and runtime issues.

## Security Considerations

The repository should not contain:

- AWS access keys or secret keys.
- API keys or passwords.
- Firebase service account credentials.
- Private SSH keys.
- Environment files containing secret values.
- Terraform state files.
- Terraform plan files containing sensitive values.
- Real database connection strings containing credentials.

Sensitive configuration should be supplied through appropriate secret-management mechanisms.

Before making the repository public, review the entire Git history as well as the current files. Removing a secret from the latest commit does not remove it from earlier commits.

If a credential has already been exposed, revoke or rotate it.

Terraform state and plan files should be stored and shared securely because they can contain sensitive resource attributes.

## Assumptions and Limitations

- The infrastructure was implemented for a staging environment rather than a formally certified production environment.
- The application relies on external services, including the Gemini API, for AI-assisted incident triage.
- Database schema updates require the appropriate Alembic migrations to be applied.
- Application health depends on correct container configuration, network connectivity, database availability, and external service configuration.
- The actual workflow triggers, tests, deployment commands, and authentication method depend on the committed GitHub Actions configuration.
- The README describes the infrastructure and workflows implemented during the project. The current availability of the AWS resources must be verified separately.
- The original staging environment was subject to teardown attempts. A fresh deployment should not be assumed to be running until the AWS resources and application endpoints have been checked.
- A successful fresh deployment depends on AWS account permissions, service quotas, configuration values, and the availability of the required external services.

## Potential Improvements

The following are possible future improvements rather than features claimed as completed:

- Use GitHub Actions with AWS OIDC to avoid long-lived AWS credentials.
- Add automated application tests and integration tests to the deployment pipeline.
- Add deployment rollback procedures and stronger post-deployment verification.
- Introduce separate staging and production configurations where required.
- Add CloudWatch alarms for service health, CPU, memory, and HTTP errors.
- Add automated database backup and recovery testing.
- Introduce stricter IAM policies and regular secret rotation.
- Add security scanning for Docker images and Terraform configuration.
- Review NAT Gateway and load balancer costs and optimize the environment for the intended workload.

## Monitoring and Logging with Amazon CloudWatch

Amazon CloudWatch was used to collect and inspect application and container logs from the ECS services running the Crisis Connect backend and informational frontend.

Monitoring was an important part of validating deployments and troubleshooting issues that were not immediately obvious from the CI/CD pipeline or AWS resource status.

### CloudWatch Logs

The ECS services were configured to send container logs to CloudWatch Logs. This provided visibility into application startup, runtime behavior, and errors generated by the containers.

I used CloudWatch logs to investigate:

- ECS container startup failures.
- Backend API errors and failed requests.
- Application configuration problems.
- Database connectivity issues.
- Failures that occurred after a deployment.
- Runtime behavior that was not explained by the ECS service status alone.

### Troubleshooting with Logs

During deployment troubleshooting, I used CloudWatch logs alongside ECS task status, container configuration, and Application Load Balancer health checks to narrow down the cause of failures.

For example, when an application was not responding through the load balancer, I checked the container logs and traced the configuration across the application port, ECS task, and target group. This helped distinguish container startup or application issues from load balancer connectivity problems.

CloudWatch was also useful when investigating backend API failures and checking whether the application was reaching its dependencies successfully.

### Health Verification

CloudWatch logs were used alongside other AWS service checks to validate deployments.

The verification process included:

1. Checking the ECS task and service status.
2. Reviewing container logs for startup errors.
3. Checking Application Load Balancer target health.
4. Testing the application health endpoint.
5. Investigating backend errors and dependency connectivity when requests failed.

The backend health endpoint used for verification was `/api/v1/health`.

### Monitoring Scope and Future Improvements

The monitoring work focused on container logs and troubleshooting application behavior. Logs were complemented by ECS service status, load balancer health checks, and direct application health verification.

Potential improvements include adding CloudWatch alarms for CPU and memory utilization, HTTP 4xx and 5xx responses, unhealthy load balancer targets, and ECS task failures. These alerts would help identify service degradation earlier and reduce the need to rely on manual log inspection.

These additional alarms are future improvements unless they are present in the current infrastructure configuration.

## Technology Stack

### Cloud Infrastructure

- Amazon Web Services (AWS).
- Amazon VPC.
- Amazon ECS Fargate.
- Amazon ECR.
- Application Load Balancer.
- Amazon RDS PostgreSQL.
- Amazon S3.
- AWS Secrets Manager.
- Amazon CloudWatch.
- Internet Gateway and NAT Gateway.

### DevOps and Automation

- Terraform.
- Docker.
- GitHub Actions.
- Infrastructure as Code.
- CI/CD.
- Linux.
- Git.

### Application and Database

- Python.
- FastAPI.
- PostgreSQL.
- SQLAlchemy / SQLModel.
- Alembic.
- Gemini API.

### Mobile Delivery

- GitHub Actions.
- Android APK builds.
- Firebase App Distribution.

## Project Context

Crisis Connect was one of the projects I worked on during my internship at KodeCamp.

My role focused on cloud infrastructure, containerization, CI/CD, deployment automation, monitoring, and troubleshooting.

The project gave me hands-on experience with the practical side of DevOps, from provisioning AWS resources and building container images to diagnosing runtime failures, keeping database migrations aligned with application code, and verifying deployments through a load balancer.

It also reinforced an important lesson: infrastructure is only one part of a successful deployment. The application, network, database, runtime configuration, and deployment pipeline all need to work together.

## Repository Note

This repository documents the DevOps and cloud infrastructure work for Crisis Connect. It is intended to help reviewers understand the architecture, inspect the Terraform configuration, follow the deployment process, and see how the infrastructure was organized.

For reproducibility, use the actual configuration and workflow files in the repository as the source of truth for commands, variables, and deployment behavior.
