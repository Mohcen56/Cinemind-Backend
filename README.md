<div align="center">
  <br />
  
  # 🎬 CineMind AI - Backend
  
  <div>
    <img src="https://img.shields.io/badge/-Django_5.1-black?style=for-the-badge&logoColor=white&logo=django&color=092E20" alt="django" />
    <img src="https://img.shields.io/badge/-Django_REST-black?style=for-the-badge&logoColor=white&logo=django&color=A30000" alt="drf" />
    <img src="https://img.shields.io/badge/-PostgreSQL-black?style=for-the-badge&logoColor=white&logo=postgresql&color=4169E1" alt="postgresql" />
    <img src="https://img.shields.io/badge/-Python_3.11-black?style=for-the-badge&logoColor=white&logo=python&color=3776AB" alt="python" />
    <img src="https://img.shields.io/badge/-Groq_AI-black?style=for-the-badge&logoColor=white&logo=openai&color=412991" alt="groq" />
  </div>

  <h3 align="center">🤖 Intelligent Movie Discovery API with RAG-Powered Recommendations</h3>

</div>

---

## 📋 Table of Contents

- [🎯 Overview](#-overview)
- [🏗️ Architecture](#️-architecture)
- [🧠 AI Engine (RAG Pipeline)](#-ai-engine-rag-pipeline)
- [🔌 API Endpoints](#-api-endpoints)
- [📦 Tech Stack](#-tech-stack)
- [⚡ Getting Started](#-getting-started)
- [🔐 Environment Variables](#-environment-variables)
- [🚀 Deployment](#-deployment)
- [📂 Project Structure](#-project-structure)

---

## 🎯 Overview

The **CineMind Backend** is a robust Django REST API that powers the CineMind AI movie discovery platform. It integrates multiple AI providers (Groq, GitHub Models) with the TMDB API to deliver intelligent, personalized movie recommendations using a sophisticated RAG (Retrieval-Augmented Generation) pipeline.

### ✨ Key Highlights

- 🤖 **Multi-LLM Support** - Smart routing between Groq (speed) and GPT-4o (intelligence)
- 🎯 **RAG Architecture** - Context-aware recommendations using user preferences
- 🔒 **Token-Based Auth** - Secure authentication with Django REST Token Auth
- 📊 **User Profiling** - Weighted preference system (LOVED > SAVED > LIKED > HATED)
- 🎬 **TMDB Integration** - Real-time movie data, cast, and recommendations

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           🎬 CineMind Backend                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐         │
│  │   🌐 REST API   │    │   🔐 Auth       │    │   📊 Models     │         │
│  │   (Django RF)   │◄──►│   (Token Auth)  │◄──►│   (ORM)         │         │
│  └────────┬────────┘    └─────────────────┘    └────────┬────────┘         │
│           │                                              │                  │
│           ▼                                              ▼                  │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │                        🔧 Services Layer                         │       │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────┐ │       │
│  │  │  🧠 AI      │  │  🎭 LLM     │  │  🎬 TMDB    │  │ 🔍      │ │       │
│  │  │  Engine     │  │  Providers  │  │  Service    │  │ Search  │ │       │
│  │  │  (RAG)      │  │  Router     │  │  Wrapper    │  │ Service │ │       │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └─────────┘ │       │
│  └─────────┼────────────────┼────────────────┼─────────────────────┘       │
│            │                │                │                              │
└────────────┼────────────────┼────────────────┼──────────────────────────────┘
             │                │                │
             ▼                ▼                ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   🗄️ Database   │  │   🤖 AI APIs    │  │   🎬 TMDB API   │
│   PostgreSQL/   │  │  ┌───────────┐  │  │                 │
│   SQLite        │  │  │ ⚡ Groq   │  │  │  Movie Data     │
│                 │  │  │ (Llama)   │  │  │  Cast Info      │
│  • Users        │  │  └───────────┘  │  │  Trending       │
│  • Interactions │  │  ┌───────────┐  │  │  Recommendations│
│  • Trending     │  │  │ 🧠 GitHub │  │  │                 │
│                 │  │  │ (GPT-4o)  │  │  │                 │
│                 │  │  └───────────┘  │  │                 │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

---

## 🧠 AI Engine (RAG Pipeline)

CineMind implements a sophisticated **Retrieval-Augmented Generation** architecture for personalized movie recommendations.

### 🔄 RAG Flow

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        🔄 RAG Pipeline Flow                              │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  📥 USER QUERY                                                           │
│       │                                                                  │
│       ▼                                                                  │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  1️⃣  RETRIEVAL PHASE                                            │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │    │
│  │  │ 👤 User     │  │ 🎬 TMDB     │  │ 💾 Rated    │              │    │
│  │  │ Interactions│  │ Top Movies  │  │ & Saved    │               │    │
│  │  │ (DB Query)  │  │ (API Call)  │  │ Movies     │               │    │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘              │    │
│  │         └────────────────┼────────────────┘                      │    │
│  │                          ▼                                       │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                             │                                            │
│                             ▼                                            │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  2️⃣  AUGMENTATION PHASE                                         │    │
│  │                                                                  │    │
│  │  📊 Weighted User Profile:                                       │    │
│  │  ┌─────────────────────────────────────────────────────┐        │    │
│  │  │  ❌ HATED (1-2★)  → Avoid similar patterns          │        │    │
│  │  │  ❤️  LOVED (5★)    → Strongest positive signal      │        │    │
│  │  │  📌 SAVED         → High interest (watchlist)       │        │    │
│  │  │  👍 LIKED (3-4★)  → General interest               │        │    │
│  │  └─────────────────────────────────────────────────────┘        │    │
│  │                                                                  │    │
│  │  🎯 Intent Classification:                                       │    │
│  │  • Personalization needed?  • Genre detection                    │    │
│  │  • "Best/Top" queries       • Complexity analysis                │    │
│  │                                                                  │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                             │                                            │
│                             ▼                                            │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  3️⃣  GENERATION PHASE (Smart LLM Routing)                       │    │
│  │                                                                  │    │
│  │  ┌──────────────────┐         ┌──────────────────┐              │    │
│  │  │  ⚡ GROQ          │         │  🧠 GITHUB       │              │    │
│  │  │  (Llama 3.1 8B)  │         │  (GPT-4o)        │              │    │
│  │  │                  │         │                  │              │    │
│  │  │ • Simple queries │         │ • Complex queries│              │    │
│  │  │ • < 220 chars    │         │ • Personalization│              │    │
│  │  │ • Fast response  │         │ • Deep reasoning │              │    │
│  │  └──────────────────┘         └──────────────────┘              │    │
│  │                                                                  │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                             │                                            │
│                             ▼                                            │
│                     📤 AI RESPONSE                                       │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

### 🎯 LLM Routing Logic

| Condition | Provider | Model | Reason |
|-----------|----------|-------|--------|
| Personalization needed | GitHub | GPT-4o | Nuanced understanding |
| Complex keywords (why, explain, analyze) | GitHub | GPT-4o | Deep reasoning |
| Query > 220 characters | GitHub | GPT-4o | Complex context |
| Simple, short queries | Groq | Llama 3.1 8B | Fast inference |

---

## 🔌 API Endpoints

### 🎬 Core API (`/api/`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/movies/` | Search/discover movies (with pagination) |
| `GET` | `/movies/<id>/` | Get movie details with cast & recommendations |
| `GET` | `/movies/trending/` | Get TMDB weekly trending movies |
| `POST` | `/chat/` | AI-powered chat for recommendations |
| `GET` | `/search/trending/` | Get trending searches on platform |
| `POST` | `/search/update/` | Update search trending analytics |

### 👤 User API (`/api/user/`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/register/` | Create new user account |
| `POST` | `/login/` | Authenticate and get token |
| `POST` | `/logout/` | Invalidate auth token |
| `GET` | `/profile/` | Get current user profile |
| `PUT/PATCH` | `/profile/update/` | Update user profile |
| `POST` | `/password/change/` | Change user password |
| `POST` | `/movies/<id>/rate/` | Rate a movie (1-5 stars) |
| `POST` | `/movies/<id>/save/` | Toggle movie save/watchlist |
| `GET` | `/movies/<id>/interaction/` | Get user's interaction with movie |
| `GET` | `/movies/saved/` | Get all saved movies |

---

## 📦 Tech Stack

### 🔧 Core Framework
| Technology | Purpose |
|------------|---------|
| **Django 5.1** | Web framework |
| **Django REST Framework** | RESTful API |
| **Python 3.11+** | Runtime |

### 🗄️ Database
| Technology | Purpose |
|------------|---------|
| **SQLite** | Development database |
| **PostgreSQL (Neon)** | Production database |
| **dj-database-url** | Database URL parsing |

### 🤖 AI/ML Providers
| Provider | Model | Use Case |
|----------|-------|----------|
| **Groq** | Llama 3.1 8B Instant | Fast inference |
| **GitHub Models** | GPT-4o | Complex reasoning |
| **Google GenAI** | Gemini | Alternative provider |

### 🔌 External APIs
| API | Purpose |
|-----|---------|
| **TMDB API** | Movie data, cast, trending, recommendations |

### 🚀 Production
| Technology | Purpose |
|------------|---------|
| **Gunicorn** | WSGI HTTP Server |
| **WhiteNoise** | Static file serving |
| **CORS Headers** | Cross-origin requests |

---

## ⚡ Getting Started

### 📋 Prerequisites

- Python 3.11+
- pip (Python package manager)
- Virtual environment (recommended)

### 🛠️ Installation

```bash
# 1. Navigate to backend directory
cd Backend

# 2. Create virtual environment
python -m venv venv

# 3. Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Create .env file (see Environment Variables section)
cp .env.example .env

# 6. Run migrations
python manage.py migrate

# 7. Create superuser (optional)
python manage.py createsuperuser

# 8. Start development server
python manage.py runserver
```

The API will be available at `http://127.0.0.1:8000/api/`

---

## 🔐 Environment Variables

Create a `.env` file in the `Backend` directory:

```env
# 🔒 Django Core
SECRET_KEY=your-super-secret-django-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# 🌐 CORS Configuration
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
CSRF_TRUSTED_ORIGINS=http://localhost:3000

# 🗄️ Database (optional - defaults to SQLite)
DATABASE_URL=postgres://user:pass@host/dbname?sslmode=require

# 🎬 TMDB API
TMDB_API_KEY=your-tmdb-bearer-token

# 🤖 AI Providers
GROQ_API_KEY=your-groq-api-key
GITHUB_API_KEY=your-github-models-api-key
```

---

## 🚀 Deployment

### ☁️ Azure App Service

1. **Create App Service** (Python 3.11, Linux)
2. **Configure Environment Variables** in Azure Portal
3. **Deploy via Git** or Azure CLI

```bash
# Azure CLI deployment
az webapp up --name cinemind-backend --runtime "PYTHON:3.11"
```

### 📁 Files for Deployment

| File | Purpose |
|------|---------|
| `Procfile` | Gunicorn startup command |
| `startup.sh` | Custom startup script |
| `requirements.txt` | Python dependencies |

For detailed deployment instructions, see [DEPLOYMENT.md](./DEPLOYMENT.md).

---

## 📂 Project Structure

```
Backend/
├── 📄 manage.py                 # Django management script
├── 📄 requirements.txt          # Python dependencies
├── 📄 Procfile                  # Gunicorn startup
├── 📄 startup.sh                # Azure startup script
├── 🗄️ db.sqlite3                # Development database
│
├── ⚙️ config/                   # Django project settings
│   ├── settings.py              # Main configuration
│   ├── urls.py                  # Root URL routing
│   ├── wsgi.py                  # WSGI application
│   └── asgi.py                  # ASGI application
│
├── 🎬 core/                     # Core movie functionality
│   ├── models.py                # TrendingSearch model
│   ├── views.py                 # Movie & chat endpoints
│   ├── urls.py                  # Core URL patterns
│   ├── admin.py                 # Admin configuration
│   │
│   └── 🔧 services/             # Business logic layer
│       ├── ai_engine.py         # 🧠 RAG pipeline & user profiling
│       ├── llm_providers.py     # 🤖 Multi-LLM routing
│       ├── tmdb.py              # 🎬 TMDB API wrapper
│       └── search.py            # 🔍 Search aggregation
│
├── 👤 user/                     # User management
│   ├── models.py                # User & MovieInteraction models
│   ├── views.py                 # Auth & profile endpoints
│   ├── serializers.py           # DRF serializers
│   ├── urls.py                  # User URL patterns
│   └── migrations/              # Database migrations
│
└── 📁 media/                    # User uploads
    └── avatars/                 # Profile pictures
```

---

## 🛡️ Security Features

- 🔐 **Token-based Authentication** - Secure API access
- 🔒 **Password Validation** - Django's built-in validators
- 🌐 **CORS Configuration** - Whitelist allowed origins
- 🛡️ **CSRF Protection** - Trusted origins only
- 📝 **Environment Variables** - Secrets via python-decouple

---

## 🧪 API Testing

Use the provided endpoints with tools like:

- **Postman** or **Insomnia**
- **cURL**
- **Django REST Framework Browsable API** (`/api/`)

### Example Request

```bash
# Get trending movies
curl http://localhost:8000/api/movies/trending/

# Search movies
curl "http://localhost:8000/api/movies/?q=inception&page=1"

# Login
curl -X POST http://localhost:8000/api/user/login/ \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "yourpassword"}'
```

---

<div align="center">
  
  **Built with ❤️ using Django & AI**
  
  [🎬 Frontend](../Frontend) • [📖 Deployment Guide](./DEPLOYMENT.md)
  
</div>
