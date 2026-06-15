# Implementation Flow

This document details the software-level implementation logic implemented within the LetEcho backend ecosystem.

## 1. Cloud Storage Abstraction
The system utilizes a `CloudStorageService` abstraction (`cloud_storage.py`) that conditionally handles files based on the active environment (`ENV_MODE`).
- **Production (`prod`)**: All file operations interact directly with AWS S3 using `boto3`.
- **Local/Development (`local`, `dev`)**: File operations bypass AWS and fall back to local disk storage (`MEDIA_ROOT`) and HTTP generation, ensuring developers can test end-to-end without incurring cloud costs.

## 2. Secure Presigned URLs
To reduce the load on the API, large file uploads (such as MP3s, WAVs, and PDFs) are passed off to AWS S3 directly from the client.
- The client requests a presigned URL by hitting `POST /presigned-url` with `file_name` and `file_type`.
- `generate_presigned_url` safely validates the user and requests a signed PUT URL from AWS S3, valid for a limited duration.
- The client uploads directly to S3 and then submits the `s3_key` to the Django API.

## 3. Background Processing & Orchestration
Heavy computational tasks, such as translating PDFs and long audio files, are handed off to **Celery**.
1. **API View**: Receives the translation request and immediately returns a `202 Accepted` alongside a Task ID, preventing HTTP timeouts.
2. **Orchestrator**: Dispatches the task to the Redis broker.
3. **Celery Worker**: Picks up the task.
   - It securely downloads the file from S3 to temporary local storage.
   - It runs the translation pipeline (via `GeminiASRProvider` or `DocumentTranslationService`).
   - It uploads the final result back to S3.
4. **Notification**: The worker triggers `send_translation_ready_email` via `EmailService`.

## 4. Role-Based Access Control (RBAC)
User permissions are strictly controlled using Django REST Framework decorators:
- `IsAuthenticated`: Validates standard users.
- `IsOperatorOrSuperAdmin`: Allows `OPERATOR` and `SUPER_ADMIN` types to access standard metrics (`/statistics/admin/`).
- `IsSuperAdmin`: Strictly limits sensitive actions, such as generating revenue reports (`/statistics/revenue/`) and inviting new internal users (`/users/invite/`).

## 5. Universal Wallet & Billing
All financial transactions run through a centralized `Universal Wallet`.
- **Top-Ups**: Users top up their wallet using a custom amount (min $5). The Next.js/Flutter UI initiates a request to the backend, which returns a secure **Paystack Authorization URL**. 
- **Webhook Source of Truth**: The wallet is strictly updated via the `payment.webhook` async listener. When Paystack successfully charges the card, the webhook verifies the HMAC signature and executes an atomic increment to the user's micro-cent wallet balance, recording the transaction in the ledger.
- **Dynamic Deduction**: Depending on the channel (`UI` vs `API`), the `TranslationOrchestrator` uses the `BillingService` to calculate the cost-per-unit based on the `PricingConfig` table, securely deducting the funds before allowing the Celery task to execute.

## 6. Developer API & Webhooks
The system acts as a multi-tenant Translation Provider for external developers.
- **API Keys**: Developers generate `DeveloperApp` credentials (`client_id` and `client_secret`) securely stored using hashing.
- **Token Authentication**: API requests hitting `api.letecho.com` are intercepted by the custom `DeveloperTokenAuthentication` backend class.
- **Webhooks Dispatcher**: Long-running translations requested via the API do not block HTTP. Instead, the backend registers the client's Webhook URL. Once Celery finishes the translation, the `WebhookDispatcher` securely pushes a JSON payload signed with an HMAC `X-LetEcho-Signature` to the client's server, notifying them of completion.
