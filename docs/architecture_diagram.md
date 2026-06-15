# Full Architecture Diagram

```mermaid
flowchart TD
    %% Define Styles
    classDef client fill:#3b82f6,stroke:#1d4ed8,stroke-width:2px,color:#fff
    classDef external fill:#f59e0b,stroke:#d97706,stroke-width:2px,color:#fff
    classDef backend fill:#10b981,stroke:#047857,stroke-width:2px,color:#fff
    classDef database fill:#8b5cf6,stroke:#6d28d9,stroke-width:2px,color:#fff
    classDef infrastructure fill:#64748b,stroke:#475569,stroke-width:2px,color:#fff

    %% -------------------
    %% Clients & Frontends
    %% -------------------
    subgraph Clients["User Frontends & Third-Party"]
        Web["Next.js Web App - Dashboard & Pricing"]:::client
        Mobile["Flutter Mobile App - Wallet & Translate"]:::client
        DevAPI["Third-Party Developers - REST API Clients"]:::client
    end

    %% -------------------
    %% External Gateways
    %% -------------------
    subgraph PaymentGateway["Payment & Notifications"]
        Paystack["Paystack Payment Gateway"]:::external
        SMTP["SMTP Email Server"]:::external
        DevServer["Developer Webhook Server"]:::external
    end

    %% -------------------
    %% Backend & API
    %% -------------------
    subgraph LetEchoBackend["LetEcho Backend (Django REST)"]
        ALB["AWS Application Load Balancer"]:::infrastructure
        
        subgraph DjangoAPI["ECS Fargate: Django API Containers"]
            Auth["Authentication & JWT"]:::backend
            APIGateway["API Key Manager & Auth"]:::backend
            Wallet["Universal Wallet & Billing"]:::backend
            Presigned["S3 Presigned URL Gen"]:::backend
            Orchestrator["Translation Orchestrator"]:::backend
            WebhookHandler["Paystack Webhook Handler"]:::backend
        end
        
        subgraph AsyncWorkers["ECS Fargate: Celery Workers"]
            CeleryQueue["Celery Worker (Document & Audio Processing)"]:::backend
            AIProvider["Gemini / Google Translate API"]:::external
            WebhookDispatcher["Webhook Push Dispatcher"]:::backend
        end
    end

    %% -------------------
    %% Infrastructure & Data
    %% -------------------
    subgraph AWSData["AWS Infrastructure & Databases"]
        S3["AWS S3 Bucket (Raw & Translated Files)"]:::infrastructure
        Redis[("Redis / ElastiCache (Task Queue & Message Broker)")]:::database
        RDS[("PostgreSQL RDS (Wallets, Users, Ledgers, History)")]:::database
    end

    %% ===================
    %% Connections & Flow
    %% ===================

    %% Client Interactions
    Web -->|HTTP Requests / Top-Up| ALB
    Mobile -->|HTTP Requests / Translate| ALB
    DevAPI -->|X-Client-ID / Secret| ALB
    Web -.->|Direct File Upload/Download| S3
    Mobile -.->|Direct File Upload/Download| S3

    %% Load Balancer to Django
    ALB --> Auth
    ALB --> APIGateway
    ALB --> Wallet
    ALB --> Presigned
    ALB --> Orchestrator
    ALB --> WebhookHandler

    %% Internal API Logic
    Auth <--> RDS
    APIGateway <--> RDS
    Wallet <--> RDS
    Orchestrator -->|Checks Funds| Wallet
    Presigned -->|Generates Signed URL| S3

    %% Billing & Paystack Flow
    Wallet -->|Generates Checkout URL| Paystack
    Paystack -->|POST Webhook Event| WebhookHandler
    WebhookHandler -->|Validates HMAC & Credits Wallet| RDS

    %% Orchestration to Celery
    Orchestrator -->|Push Task (Status: PENDING)| Redis
    Orchestrator -->|Save Translation Record| RDS
    Redis -->|Consume Task| CeleryQueue

    %% Celery Worker Operations
    CeleryQueue <-->|Fetch Raw / Upload Finished| S3
    CeleryQueue <-->|External AI Request| AIProvider
    CeleryQueue -->|Update Status (COMPLETED)| RDS
    
    %% Notifications
    CeleryQueue -->|Trigger Completion Email| SMTP
    CeleryQueue -->|Push Payload| WebhookDispatcher
    WebhookDispatcher -->|POST X-LetEcho-Signature| DevServer
```

## Flow Description Summary
1. **File Uploads**: Users/Clients bypass the Django API by fetching a secure URL from `S3 Presigned URL Gen` and uploading large files directly to **AWS S3**.
2. **Translation Execution**: The client triggers the `Translation Orchestrator` via the API. The Orchestrator deducts credits from the `Universal Wallet`, logs to **PostgreSQL**, and pushes a background task to **Redis**.
3. **Background Compute**: The **Celery Worker** picks up the task from Redis, downloads the file from S3, processes it against external AI models, and saves the output back to S3.
4. **Billing via Paystack**: Clients execute top-ups which redirect to **Paystack**. Paystack fires an async webhook to the `Webhook Handler`, which verifies the signature and increments the Wallet in PostgreSQL.
5. **Developer Webhooks**: For API Users, instead of an email from **SMTP**, the Celery worker triggers the `Webhook Dispatcher` to securely ping the third-party **Developer's Webhook Server** with the translation results.
