# Echo — Product Requirements Document (PRD)

> **Version:** 1.0 · **Date:** March 2026 · **Status:** Living Document

---

## 1. Overview

**Echo** (internally "Speak Africa") is an AI-powered multilingual translation platform specialising in bridging communication gaps across African and world languages. It provides a unified backend service offering speech-to-speech, speech-to-text, text-to-speech, text-to-text, image/OCR, and document translation — all powered by Google Gemini AI models.

### 1.1 Problem Statement

Millions of people in Africa and globally face communication barriers because of language diversity. Existing translation tools either lack African language support, require expensive infrastructure, or deliver poor audio quality. Echo addresses this with a single, scalable API platform that correctly synthesises and understands African languages.

### 1.2 Vision

> *"Any language, any modality, in real time."*

Echo enables developers, businesses, and everyday users to translate spoken and written content across 20+ languages — including Swahili, Kinyarwanda, Amharic, Yoruba, Hausa, Igbo, Zulu, Xhosa, Afrikaans, and Somali — with production-grade accuracy and sub-second performance targets.

---

## 2. Target Users

| Persona | Description | Primary Need |
|---|---|---|
| **Traveller** | Person visiting or relocating to a foreign country | Real-time speech-to-speech translation on mobile |
| **Business User** | Professional communicating across language borders | Text and document translation via API |
| **Developer / Integrator** | Building apps on top of Echo's API | REST/WebSocket API, clear docs, reliable uptime |
| **Administrator** | Platform operator monitoring usage | Usage logs, LLM cost tracking, user management |

---

## 3. Features & Requirements

### 3.1 User Authentication & Account Management

| # | Feature | Description | Priority |
|---|---|---|---|
| U-01 | Registration | Email + password sign-up with email verification OTP | Must Have |
| U-02 | Login | Email + password login; optional OTP 2FA step | Must Have |
| U-03 | Password Reset | OTP-based password reset flow | Must Have |
| U-04 | Account Security | Failed login attempt tracking; account lockout | Must Have |
| U-05 | User Roles | `customer`, `admin`, `super_admin` roles with scoped access | Must Have |
| U-06 | Profile Management | Name, gender, occupation, country, city, visit type, profile picture | Should Have |
| U-07 | JWT Tokens | Access + refresh token pair on login | Must Have |

**OTP Flow:** 6-digit code sent via email → time-limited by `VERIFICATION_OTP_TIMEOUT` setting → single-use, auto-invalidated on use.

---

### 3.2 Translation Core

Echo supports **6 translation modalities**:

#### 3.2.1 Speech-to-Speech (STS)
The flagship pipeline: user speaks → Echo transcribes → translates → synthesises back as audio.

**Flow:**
```
[Audio Upload / WebSocket stream]
        ↓
  Gemini ASR (gemini-2.0-flash)   → transcribed text
        ↓
  Gemini NMT (gemini-2.0-flash)   → translated text
        ↓
  Gemini TTS (gemini-2.5-flash-preview-tts) → WAV audio (24kHz, 16-bit, mono PCM + WAV header)
        ↓
  [Translated audio URL returned]
```

**Requirements:**
- Accept audio: WAV, MP3, MP4, WebM, Opus, OGG (max 10 MB by default)
- Support language auto-detection on input
- Return playable WAV file URL
- Store original + translated audio to cloud storage
- Log ASR, NMT, and TTS latency + token usage separately

#### 3.2.2 Speech-to-Text (STT)
Transcribes audio to text, with optional translation of the transcription.

- Accepts file upload or a public URL pointing to an audio file
- Returns: `original_text`, `confidence_score`, `language`
- Optional: also translate to a different target language

#### 3.2.3 Text-to-Speech (TTS)
Converts text to a natural-sounding WAV audio file.

- Optional translation before synthesis (if `source_language ≠ target_language`)
- Voice selection: `Zephyr`, `Nova`, `Orbit`, `Echo`, `Breeze`, `Aria`, `Phoenix`, `Luna`
- Voice → Gemini native voice mapping (e.g. `Nova` → `Puck`, `Orbit` → `Charon`)
- Returns: audio file URL

#### 3.2.4 Text-to-Text (NMT)
Pure text translation between any two supported languages.

- Auto language detection supported
- SMS mode flag for short-form translations
- Large text via URL (fetches remote content)
- Returns: `translated_text`, usage metadata, processing time

#### 3.2.5 Image / OCR Translation
Uploads an image; Echo extracts and translates all text within it.

- Powered by Gemini Vision (`gemini-2.0-flash`)
- Returns: `ocr_text` (original), `translated_text`
- Original image stored to cloud

#### 3.2.6 Document Translation
Translates entire PDF and DOCX files preserving layout and structure.

- Supported formats: PDF, DOCX (Office 2007+)
- Returns: translated document file URL
- Processing via `document_processors.py` (text chunking, structure preservation)

---

### 3.3 Language Support

| Category | Languages |
|---|---|
| **African** | Swahili, Kinyarwanda, Amharic, Yoruba, Hausa, Igbo, Zulu, Xhosa, Afrikaans, Somali |
| **World** | English, Spanish, French, German, Chinese, Japanese, Korean, Arabic, Hindi, Portuguese, Russian, Italian |

Each language in the `LanguageSupport` model tracks capability flags per modality (ASR, TTS, NMT, Image, Document, STS).

---

### 3.4 Real-Time WebSocket API

Three WebSocket consumers support real-time progress streaming:

| Consumer | URL Group | Purpose |
|---|---|---|
| `VoiceConsumer` | `voice_{user_id}` | Streams STS progress: decode → ASR → translate → TTS → complete |
| `OCRConsumer` | `ocr_{user_id}` | Streams OCR progress: preprocess → extract → detect language → translate |
| `ProcessingConsumer` | `processing_{user_id}` | Generic background task acknowledgements |

**WebSocket Message Protocol:**
```json
// Progress update
{ "type": "progress", "step": "asr", "progress": 50, "message": "Transcribing audio..." }

// Completion
{ "type": "complete", "progress": 100, "result": { "audio_url": "...", "translated_text": "..." } }

// Error
{ "type": "error", "message": "Processing failed: ..." }
```

Authentication: JWT token verified in WebSocket middleware before connection is accepted.

---

### 3.5 Translation History

- All translation records are persisted with UUID primary keys
- Users can retrieve their full translation history (text, speech, image)
- Session-based grouping via `session_id`
- Status lifecycle: `PENDING → PROCESSING → COMPLETED / FAILED`
- Modes: `SHORT` (full pipeline), `LONG` (document / async)

---

### 3.6 User Settings

Persistent per-user preferences:

| Setting | Options |
|---|---|
| AI Model | `gemini-2.5-flash-preview-tts`, `gemini-2.5-pro-preview-tts`, `gemini-2.0-flash`, `gemini-1.5-flash` |
| Voice | Zephyr, Nova, Orbit, Echo, Breeze, Aria, Phoenix, Luna |
| Auto-detect language | Boolean |
| Source / Target language | ISO language code |
| Super fast mode | Boolean (skip intermediate steps) |
| Autoplay audio | Boolean |
| Theme | `african`, …  |
| Audio quality | `high`, … |

---

### 3.7 Wallet & Payments

Echo includes a built-in credit wallet for metered access:

**Wallet:**
- Each user has a one-to-one `Wallet` with a balance (decimal)
- Credits deducted per API call (configurable per modality/tier)
- Transaction history: `TOPUP | DEBIT | CREDIT | REFUND` with `INFLOW / OUTFLOW` flow type

**Payment Gateways:**
- **Paystack** — primary gateway for wallet top-ups in Africa
  - Initialize transaction → redirect to Paystack checkout → verify callback → credit wallet
  - Webhook (`charge.success`) for async confirmation
  - Stripe-style authorization code storage for reusable billing
- **KPay** — secondary gateway via webhook
  - `POST /api/payment/kpay/webhook/` with HMAC signature validation
  - Idempotent event processing via `KPayWebhookEvent`

---

### 3.8 Cloud Storage

Three cloud storage backends supported, configured via `CloudStorageConfig` model:

| Provider | Config |
|---|---|
| AWS S3 | Access key, secret key, bucket, region |
| Google Cloud Storage | Service account JSON, bucket |
| Cloudinary | Cloud name, API key, API secret |

Media stored: original/translated audio, profile pictures, original images.

---

### 3.9 LLM Usage & Cost Tracking

Every call to Gemini is logged to `LLMLog`:
- Provider, model, function (`ASR` / `Translation` / `TTS` / `Image`)
- Input tokens, output tokens, total tokens
- Latency (seconds), cost (decimal)
- Status (`success` / `failure`) and error messages
- Linked to the parent translation record

---

### 3.10 Statistics & Analytics

The `stats_app` exposes aggregated metrics:
- Total translation counts by modality
- User session counts
- Supported language counts
- Health check endpoint at `GET /api/voice/health/`

---

### 3.11 Notifications

The `notification` app handles communication events (registration confirmations, OTP delivery, etc.).

---

## 4. Application Flow

### 4.1 Registration & Onboarding

```
1. User submits: first_name, last_name, email, password, gender, user_type
2. System creates user (is_active=False, is_verified=False)
3. OTP (6-digit) generated and emailed
4. User submits OTP → account activated (is_verified=True)
5. JWT token pair returned
```

### 4.2 Translation Request (REST)

```
1. Client sends: Authorization: Bearer <token>
2. API validates JWT
3. Request routed to appropriate view (STT / TTS / STS / NMT / OCR / Document)
4. TranslationOrchestrator creates DB record (status=PENDING → PROCESSING)
5. ProviderFactory selects Gemini providers
6. Pipeline executes (ASR → NMT → TTS or subset)
7. Outputs saved to cloud storage
8. DB record updated (status=COMPLETED or FAILED)
9. LLM usage logged
10. Response returned: { success, translation_id, audio_url / translated_text }
```

### 4.3 Real-Time Translation (WebSocket)

```
1. Client opens WS: ws://<host>/ws/voice/
2. Server validates JWT from middleware
3. Client sends: { type: "voice_process", audio: "<base64>", target_language: "sw" }
4. Server streams progress messages (progress 0-100%)
5. On completion, sends: { type: "complete", result: { audio_url, translated_text } }
```

### 4.4 Wallet Top-Up

```
1. POST /api/payment/topup/ { amount, callback_url }
2. Paystack transaction initialized → authorization_url returned
3. User completes payment on Paystack
4. Callback hits POST /api/payment/verify/<reference>/
   OR webhook hits POST /api/payment/webhook/
5. Payment verified → Wallet.topup(amount) called → Transaction recorded
```

---

## 5. API Endpoints Summary

### Authentication
| Method | Path | Description |
|---|---|---|
| POST | `/api/auth/register/` | Register new user |
| POST | `/api/auth/login/` | Login, returns JWT |
| POST | `/api/auth/verify-otp/` | Verify registration OTP |
| POST | `/api/auth/reset-password/` | Initiate password reset |

### Translation
| Method | Path | Description |
|---|---|---|
| POST | `/api/voice/translate/` | Speech-to-speech translation |
| POST | `/api/voice/text/` | Text-to-text translation |
| POST | `/api/voice/tts/` | Text-to-speech |
| POST | `/api/voice/stt/` | Speech-to-text |
| POST | `/api/voice/image/` | Image OCR + translation |
| POST | `/api/voice/document/` | Document translation |
| GET | `/api/voice/translations/` | Translation history |
| GET/DELETE | `/api/voice/translations/<id>/` | Translation detail/delete |

### Settings & Infrastructure
| Method | Path | Description |
|---|---|---|
| GET/POST | `/api/voice/settings/` | User settings |
| GET | `/api/voice/languages/` | Supported languages |
| GET | `/api/voice/health/` | Health check |
| GET | `/api/voice/tasks/<task_id>/` | Background task status |

### Payment
| Method | Path | Description |
|---|---|---|
| POST | `/api/payment/topup/` | Initiate wallet top-up |
| PATCH | `/api/payment/verify/<ref>/` | Verify Paystack payment |
| POST | `/api/payment/webhook/` | Paystack webhook |
| POST | `/api/payment/kpay/webhook/` | KPay webhook |

### WebSocket
| URL | Description |
|---|---|
| `ws://<host>/ws/voice/` | Real-time voice translation |
| `ws://<host>/ws/ocr/` | Real-time OCR translation |
| `ws://<host>/ws/processing/` | Background task updates |

---

## 6. Non-Functional Requirements

| Requirement | Target |
|---|---|
| **Availability** | 99.9% uptime |
| **Response Time** | < 5s for short text/TTS; < 15s for STS pipeline |
| **Audio Quality** | 24kHz, 16-bit, mono WAV (Gemini TTS native output) |
| **Max Audio Upload** | 10 MB default |
| **Security** | JWT auth on all protected endpoints; OTP expiry on login/reset |
| **Scalability** | Horizontal scaling via ASGI + Redis channel layer |
| **Observability** | Per-call LLM usage logs with latency and token counts |
| **Storage** | Pluggable cloud storage (S3 / GCS / Cloudinary) |
| **Background Tasks** | Celery for long-running document/large-audio jobs |

---

## 7. Future Roadmap

- [ ] Subscription / credit plans with automatic deduction per translation unit
- [ ] Batch translation API (multiple strings in one call)
- [ ] Real-time streaming ASR (WebSocket audio chunks)
- [ ] Additional provider support (OpenAI Whisper, ElevenLabs TTS)
- [ ] Mobile SDK (iOS, Android)
- [ ] Voice cloning / custom voice training
- [ ] Admin dashboard UI for usage analytics and cost monitoring
- [ ] Rate limiting per user tier
- [ ] Offline/edge model inference for low-connectivity regions
