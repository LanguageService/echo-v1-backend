# 🚀🚀 Echo API Project Overview

Echo is a comprehensive backend system specializing in **Text Translation**, **OCR Translation** and **Voice Translation** with a unique focus on **African languages** (Swahili, Kinyarwanda, Yoruba, Igbo, Hausa, etc.). It provides a robust, scalable infrastructure for real-time and background translation services.

## 🚀 Technology Stack

- **Backend Framework**: Django & Django REST Framework (DRF)
- **Database**: SQLite (Development) / PostgreSQL (Production)
- **Asynchronous Processing**: Celery & Redis (Task queue for LARGE mode processing)
- **Security**: JWT Authentication (SimpleJWT)
- **Documentation**: drf-spectacular (OpenAPI / Swagger)
- **AI Engine**: Google Gemini AI (ASR, TTS, LLM Translation)


## 🏗 System Architecture

The project follows a modular Django architecture, separating concerns into specialized apps for authentication, translation services, statistics, and performance monitoring.

### Core Modules

1. **`users`**:
   - Handles multi-role user management (Customer, Admin, SuperAdmin).
   - Manages JWT-based authentication, OTP verification, and password resets.
   - Categorized under the "Auth" Swagger tag.

2. **`translation`**:
   - The heart of the system.
   - **Orchestrator**: Central logic that coordinates transcribers, translators, and synthesizers.
   - **Providers**: Pluggable adapters for different AI services (currently Gemini-first).
   - **Views**: Structured endpoints for Text, Speech, and Image translation.
   - **Models**: Tracks full translation lifecycle, including original and result media.

3. **`stats_app`**:
   - Tracks detailed usage metrics for LLM calls and user activity.
   - Provides analytics for system optimization and cost monitoring.

4. **`performance`**:
   - Specialized logic for optimizing resource-heavy translation tasks.

## 🔄 Key Translation Workflows

### 1. Speech Translation (STS, STT, TTS)

- **SHORT Mode**: Synchronous processing for immediate results (speech-to-text, text-to-speech).
- **LARGE Mode**: Asynchronous processing via Celery for larger audio files or documents, with status tracking and background notifications.
- **Multilingual Support**: Explicit `source_language` and `target_language` control. Automated translation occurs if languages differ.

### 2. Text Translation

- **SHORT Mode**: Real-time translation of plain text or short messages (SMS). Supports automated language detection.
- **LARGE Mode**: Background processing for structured documents (Ebooks, PDFs, DOCX). Maintains formatting and layout during the translation process.
- **Multilingual Support**: Advanced control over source and target languages via the `TranslationOrchestrator`.

### 3. Image OCR Translation

- Extracts text from images and translates it to the target language.
- Ideal for digital signage, menus, and documents captured via camera.


## 📊 Data Models & Logging

- **`BaseTranslation`**: Abstract model sharing common metadata (user, languages, status, timing).

- **`SpeechTranslation`**: Stores audio inputs/outputs and transcriptions.

- **`LLMLog`**: Captures provider, model, tokens (input/output), latency, and cost for every AI interaction.


## 🛠 Management Commands

- `populate_languages`: Seeds the database with supported languages and regional priority settings.

- `populate_cloud_configs`: Sets up necessary cloud storage and API credentials.
- **Celery Worker**: Run `celery -A core worker -l info` to start processing background tasks.

## 📍 API Categories

| Category               | Description                                          |
| ---------------------- | ---------------------------------------------------- |
| **Auth**               | Login, Token Refresh, Registration, OTP Verification |
| **Text Translation**   | Individual text and document-based translations      |
| **Speech Translation** | STS, STT, and TTS (Synchronous and Background)       |
| **Image Translation**  | OCR and visual text translation                      |
| **Statistics**         | Personal and system-wide usage analytics             |


> [!NOTE]
> This project is designed for extensibility. New AI providers can be added by implementing the base classes in `translation/providers/base.py`.
