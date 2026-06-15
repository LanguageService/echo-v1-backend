# Deployment Flow

This document details the CI/CD pipeline and the AWS Infrastructure as Code (Terraform) setup for the LetEcho project.

## 1. Infrastructure as Code (Terraform)
All infrastructure is divided into two parts: backend services under `echo-v1-backend/terraform/` and frontend hosting under `echo-web-v2/terraform/`, ensuring reproducible, scalable, and tracked AWS environments.

### Core Components
- **Networking (`vpc.tf`)**: Provisions a Virtual Private Cloud (VPC) with public and private subnets. Includes a NAT Gateway, allowing Fargate tasks in private subnets to pull images from ECR and securely reach external APIs (like Gemini and Stripe) without exposing the servers to the internet.
- **Compute (`ecs.tf`)**: Creates an Amazon Elastic Container Service (ECS) Cluster. Uses AWS Fargate to run serverless containers. Defines two distinct Task Definitions:
  - **API Task**: Runs the Django `gunicorn` web server on port 8000.
  - **Celery Task**: Runs the asynchronous background workers listening to Redis.
- **Load Balancing (`alb.tf`)**: An Application Load Balancer sitting in the public subnets routes HTTP/HTTPS requests to the ECS API Task instances.
- **Database (`rds.tf`)**: Deploys an Amazon RDS instance running PostgreSQL 15 securely tucked away in the private subnets.
- **Caching (`elasticache.tf`)**: Deploys a Redis ElastiCache node used as the message broker for Celery.
- **Frontend Hosting (`s3_cloudfront.tf`)**: Provisions a public-facing AWS CloudFront Distribution sitting in front of a private S3 bucket (secured via Origin Access Control).

### How to Apply Terraform
To spin up the entire AWS environment from scratch:
1. Ensure your AWS CLI is configured with Administrator permissions.
2. For the Backend Infrastructure: 
   - Navigate to the directory: `cd echo-v1-backend/terraform`
   - Initialize the directory: `terraform init`
   - Apply the changes: `terraform apply`
3. For the Frontend Infrastructure:
   - Navigate to the directory: `cd echo-web-v2/terraform`
   - Initialize the directory: `terraform init`
   - Apply the changes: `terraform apply`

## 2. CI/CD Pipeline (GitHub Actions)
The repository uses GitHub Actions (`.github/workflows/`) to automate deployments upon merging code into the `main` branch.

### Backend Pipeline (`deploy-backend.yml`)
1. **Trigger**: Executes when changes occur in `echo-v1-backend/`.
2. **Build**: Authenticates with AWS, builds the Django Dockerfile, and tags it with the current commit SHA.
3. **Registry**: Pushes the image to the Amazon Elastic Container Registry (ECR). Both the API and Celery repositories receive the updated image.
4. **Deploy**: Uses the `aws-actions/amazon-ecs-deploy-task-definition` action to gracefully perform a rolling deployment of the new containers on the ECS Fargate cluster without dropping active connections.

### Frontend Pipeline (`deploy-frontend.yml`)
1. **Trigger**: Executes when changes occur in `echo-web-v2/`.
2. **Build**: Runs `npm ci` and `npm run build` using Node.js to generate static Next.js assets.
3. **Deploy**: Syncs the `/out` directory directly to the AWS S3 Bucket.
4. **Invalidate**: Triggers an AWS CloudFront cache invalidation, ensuring global edge locations immediately serve the latest React UI to users.
