# Echo API - Advanced OCR & Voice Translation

Echo is a high-performance translation backend tailored for **African languages** and multimodal translation (Text, Speech, Image).

## 📖 Documentation

For a deep dive into the architecture, core modules, and workflows, please see:
- [PROJECT_OVERVIEW.md](./PROJECT_OVERVIEW.md)
- [API Walkthrough](file:///Users/sunday/.gemini/antigravity/brain/c12dacec-6266-4a51-b700-a2b79b6c2bae/walkthrough.md)

## ⚡️ Quick Start

### 1. Requirements
- Python 3.10+
- Redis (for Celery tasks)

### 2. Installation
```bash
# Clone the repository
git clone <repository-url>
cd echo-v1-backend

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Setup
Copy the `.env_example` to `.env` and fill in your credentials:
```bash
GEMINI_API_KEY=your_gemini_key
REDIS_HOST=localhost
...
```

### 4. Database & Population
```bash
python manage.py migrate
python manage.py populate_languages
```

### 5. Running the System
```bash
# Start Django server
python manage.py runserver

# Start Celery worker (in a separate terminal)
celery -A core worker -l info
```

## 📍 Key Endpoints
- **Swagger UI**: `/api/v1/doc/`
- **Redoc**: `/api/v1/redoc/`
- **Admin**: `/admin/`

---
© 2026 Echo Translation Systems
