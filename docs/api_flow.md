# ECHO V1 Backend - Email Notification & User API Flow

## Overview
This document outlines the flows for user onboarding, email verification, password reset, and document notification.

## Notification Services

A dedicated app (`notification`) was built and integrated into the `users.services` logic via `EmailDispatcher`.

The email service provides the following flows:
- **Onboarding/Welcome Email**: Triggered immediately upon user signup if the user is successfully created.
- **Email Verification**: Triggered via `EmailDispatcher.send_verification(user, otp)` where `otp` is an auto-generated token.
- **Password Reset**: Triggered via `EmailDispatcher.send_password_reset(user, otp)` upon request.
- **Password Changed Notification**: Triggered upon a successful password change.
- **Document Processing Complete**: Triggered via `EmailDispatcher.send_document_ready(user, doc_name)`.

## API Documentation

### 1. User Registration
**Endpoint:** `POST /api/v1/user/auth/register/`
**Flow:**
1. Client sends `email`, `password`, `first_name`, `last_name`, `user_type`.
2. Backend validates data and creates an inactive/unverified `User`.
3. Backend generates a Verification Token (OTP).
4. `EmailDispatcher` sends the Verification Email and the Onboarding/Welcome Email.
5. Returns `201 Created` with a success message.

### 2. Email Verification
**Endpoint:** `POST /api/v1/user/auth/verify-email/`
**Flow:**
1. Client sends `email` and `token` (OTP).
2. Backend validates the OTP using `verify_token('VERIFICATION')`.
3. If successful, user's `is_verified` becomes `True` and `is_active` becomes `True`.
4. Returns `200 OK`.

### 3. Resend Verification Email
**Endpoint:** `POST /api/v1/user/auth/resend-verification/`
**Flow:**
1. Client sends `email`.
2. Backend creates a new Verification OTP.
3. `EmailDispatcher` sends the new OTP.
4. Returns `200 OK`.

### 4. Password Reset Request
**Endpoint:** `POST /api/v1/user/auth/reset-password/`
**Flow:**
1. Client sends `email`.
2. Backend verifies user exists.
3. Backend generates a `RESET PASSWORD` token.
4. `EmailDispatcher.send_password_reset(user, otp)` sends the email.
5. Returns `200 OK`.

### 5. Confirm Password Reset
**Endpoint:** `POST /api/v1/user/auth/reset-password-confirm/`
**Flow:**
1. Client sends `email`, `token` (OTP), and `new_password`.
2. Backend checks OTP via `verify_token('RESET PASSWORD')`.
3. If valid, password is updated.
4. `EmailDispatcher.send_password_changed(user)` sends a confirmation email.
5. Returns `200 OK`.

### 6. Document Notification Flow (Internal Call)
**Method:** `EmailDispatcher.send_document_ready(user: User, document_name: str)`
**Flow:**
1. Upon a successful heavy background processing job (OCR, extraction, etc.), the processing worker calls `EmailDispatcher.send_document_ready()`.
2. Uses the standard email backend to dispatch `document_ready.html`.
3. No dedicated API endpoint exists for this since it is an internal service trigger.
