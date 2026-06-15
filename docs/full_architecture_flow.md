# Full Architecture End-to-End Flow

This document walks through the complete end-to-end lifecycle of a LetEcho request—tracing how a user's action on their browser translates into cloud networking, background compute, API triggers, and final notification delivery.

## 1. The Client Upload (Frontend to S3)
1. **User Action**: The user visits `letecho.com` via their browser or mobile app. The UI is delivered blazing-fast globally via **AWS CloudFront**, which fetches static Next.js/Flutter assets from the underlying **AWS S3 Frontend Bucket**.
2. **Presigned URL Request**: The user selects a 50MB PDF document for translation. The frontend sends a lightweight `POST` request to the backend `api.letecho.com/api/translation/presigned-url/`.
3. **Backend Authorization**: 
   - The request hits the **AWS Application Load Balancer (ALB)**, which forwards it to an **ECS Fargate API container**.
   - The Django API authenticates the JWT token.
   - Using `boto3`, Django securely requests a time-limited presigned upload URL from AWS S3.
4. **Direct S3 Upload**: The frontend receives the presigned URL and uploads the massive 50MB PDF directly to the **AWS S3 Document Storage Bucket**. This bypasses the API completely, saving massive amounts of compute bandwidth.

## 2. Orchestration (API to Redis)
5. **Trigger Translation**: Once the direct S3 upload finishes, the frontend submits a translation request to the Django API containing the resulting `s3_key` (e.g., `user123/document/file.pdf`).
6. **Database Persistence**: The API validates the request, records a pending `BaseTranslation` model entry in the **Amazon RDS PostgreSQL Database**, and commits it.
7. **Task Queueing**: The `TranslationOrchestrator` generates a Celery Task. It pushes this task payload into the **Amazon ElastiCache (Redis)** message broker.
8. **Immediate Return**: The API immediately responds to the frontend with `202 Accepted` and the Task ID. The frontend can now render a loading spinner or allow the user to leave the page.

## 3. Background Compute (Celery to AI)
9. **Task Pickup**: An **ECS Fargate Celery Worker container**, silently listening to the Redis queue, picks up the background task.
10. **Secure Download**: The Celery worker uses the provided `s3_key` to securely download the 50MB PDF from the AWS S3 bucket directly into its ephemeral container storage.
11. **AI Processing**: 
    - The worker executes the `DocumentTranslationService` or `GeminiASRProvider`.
    - It chunks the file if necessary and sends it outwards to external LLMs (e.g., Google Gemini APIs) for heavy translation.
    - All external traffic routes securely through the **AWS NAT Gateway** configured in the VPC.
12. **Result Generation**: The worker receives the translated payload back from the AI model, reconstructs the translated PDF/Audio, and uploads the final output back to the **AWS S3 Document Storage Bucket**.

## 4. Finalization & Notification
13. **Updating Database**: The Celery worker updates the `BaseTranslation` row in the **RDS Database**, marking the status as `COMPLETED` and logging the precise timestamps into the `processing_steps` JSON field.
14. **Email Dispatch**: The worker invokes the `EmailService`.
    - It generates a beautiful HTML email using Django's template engine containing the LetEcho logo.
    - It dispatches the email via SMTP to the user's inbox containing a secure download link to their translated document.
15. **End of Lifecycle**: The user receives the email, clicks the link, and views their translated document on the frontend dashboard. The Celery worker safely destroys its local temporary files and picks up the next task from Redis.

## 5. Billing & API Sub-Flows
16. **Paystack Top-Ups**: When a user needs funds, the Next.js or Flutter app initiates a top-up request. The backend returns a checkout URL. Once paid, Paystack sends a secure server-to-server webhook. The Django backend verifies the signature, atomically increments the user's wallet balance, and writes a ledger entry.
17. **Developer API Webhooks**: When a third-party developer triggers a heavy translation via `POST /api/v1/translations/text/base/` using their API Key, they provide a `webhook_url`. Once the Celery worker (Step 13) completes the translation, instead of sending an email, it pushes a signed JSON payload containing the translation directly to the Developer's server endpoint.
