# API Email Workflows Documentation

The backend incorporates an automated email notification system integrated directly into the core workflows. Emails are dispatched via SMTP to notify users about critical account and document events.

## Notification Workflows

### 1. Account Onboarding & Verification Flow
**Endpoints Involved:** 
- `POST /api/users/auth/customer/user/` (Registration)
- `POST /api/users/auth/verify-otp/` (OTP Verification)
- `POST /api/users/auth/resend-otp/` (Resend OTP)

**Flow:**
1. A new user registers using the `customer/user` endpoint.
2. The system generates a 6-digit OTP and dispatches an **Email Verification** template (`send_verification`).
3. The user submits the OTP to the `verify-otp` endpoint.
4. Upon successful validation, the system marks the user as verified and automatically dispatches the **Welcome / Onboarding** email template (`send_onboarding`), providing them with next steps and links to the dashboard.
5. If the user loses their OTP, they can hit `resend-otp`, which will dispatch a new verification email.

### 2. Password Reset Flow
**Endpoints Involved:**
- `POST /api/users/auth/reset-password/initiate/` (Initiate Reset)
- `POST /api/users/auth/reset-password/` (Confirm Reset)

**Flow:**
1. A user requests a password reset by providing their email to the `reset-password/initiate/` endpoint.
2. The system looks up the user and dispatches a **Password Reset** template (`send_password_reset`) containing a new OTP code.
3. The user inputs the code and their new password into the `reset-password/` endpoint to finalize the change.

### 3. Document Processing Flow
**Endpoints Involved:**
- `POST /api/ocr/` (Process Image)

**Flow:**
1. An authenticated user uploads a document or image to the OCR endpoint.
2. The system synchronously processes the image, extracts text, detects the language, and translates the text.
3. Upon successful completion and saving of the results to the database, the system triggers the **Document Ready** notification template (`send_document_done`), emailing the user the document name, the page/word count processed, and the total processing time.

## Underlying Service

All of these notifications are managed centrally by the `EmailDispatcher` service located at `notification/services/email/__init__.py`. 

**Email Dispatcher Public API:**
```python
from notification.services.email import EmailDispatcher

# Send Welcome Email
EmailDispatcher.send_onboarding(user)

# Send OTP Verification
EmailDispatcher.send_verification(user, otp_code="123456")

# Send Password Reset
EmailDispatcher.send_password_reset(user, otp_code="654321")

# Send Document Completion
EmailDispatcher.send_document_done(
    user=user, 
    doc_name="invoice.pdf", 
    result_url="https://frontend...", 
    page_count=5, 
    processing_time=12.5
)
```

The service utilizes Django's native `EmailMultiAlternatives` routing over standard SMTP (currently configured for Resend via the `.env` configuration).
