# Healthcare Symptom Checker (AI-Powered)

![Build Status](https://img.shields.io/badge/build-passing-brightgreen)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat&logo=fastapi)
![React](https://img.shields.io/badge/React-20232A?style=flat&logo=react&logoColor=61DAFB)
![Gemini AI](https://img.shields.io/badge/Google%20Gemini-8E75B2?style=flat&logo=google&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat&logo=docker&logoColor=white)

**Live Demo: [https://health-symptom-checker-1.vercel.app/](https://health-symptom-checker-1.vercel.app/)**

> ⚠️ **Note for Users:** The backend API is hosted on Render's free tier. If the application has been inactive for 15+ minutes, the first API request (e.g., your first time logging in or registering) may take **30-50 seconds** to complete while the backend instance cold-starts. Subsequent requests will be instant.

## 📹 Demo Video

- Add your placement demo video link here: [Watch Demo Video](https://your-video-link-here)
- Example: YouTube unlisted link, Loom link, or Google Drive share link.

## 🚀 Recent Updates

- Added **provider failover** in backend: tries **Gemini** first and falls back to **Groq** automatically if Gemini is unavailable.
- Added **retry handling** for intermittent Gemini failures (e.g., `503 UNAVAILABLE`) before using fallback.
- Improved API error behavior to return a clearer **service unavailable** response when both providers fail.
- Updated backend dependencies with `groq` SDK support.

## ✨ Key Features & Architecture

## ✨ Features

- **Advanced AI Integration**: Powered by Google's `google-genai` SDK and the ultra-fast `gemini-2.5-flash` model. Enforces strict JSON schema generation to ensure deterministic frontend parsing and reliable, formatted health insights without raw text unpredictable outputs.
- **LLM Fallback Reliability**: Automatically falls back to Groq (`llama-3.1-8b-instant`) when Gemini is rate-limited or temporarily unavailable, improving demo and production stability.
- **Context-Aware Medical Profiles**: Users can save Age, Gender, and Pre-existing Conditions, which are invisibly injected into the AI context to provide highly personalized and accurate medical insights. This heavily reduces AI hallucinations and ensures condition likelihoods are safely tailored to the patient's individual demographics.
- **Emergency Triage Engine**: Automatically flags critical or life-threatening symptoms and overrides the UI with a pulsing emergency banner. It actively prevents patients from mistaking serious acute symptoms for minor illnesses by directing them immediately to emergency services.
- **User Authentication**: Secure JSON Web Token (JWT) identity system utilizing `passlib` and `bcrypt` password hashing. Data is strictly scoped to the logged-in user, guaranteeing absolute database-level data isolation and privacy protection for sensitive condition history.
- **Dynamic Frontend**: A beautiful responsive UI built with React, TailwindCSS, and Framer Motion micro-animations. Implements clean, component-based rendering alongside protected `react-router-dom` layers to cleanly handle auth-gated dashboards.
- **Robust Async Backend**: Powered by FastAPI and `motor` (asyncio MongoDB driver), ensuring lightning-fast non-blocking API endpoints. Completely eliminates traditional backend synchronous bottlenecks, allowing the API to handle high-throughput scaling natively.
- **Universal Deployment**: Fully Dockerized. Includes `docker-compose.yml` for instant zero-configuration deployment on any machine. Neatly separates the frontend and backend into distinct build containers for clean DevOps pipelines.
- **Mac-Native Fixes**: Bypasses strict macOS python SSL certificate limitations automatically using `certifi`. Prevents classic localized database timeout crashes and pip installation failures right out-of-the-box for Apple hardware environments.

## 📂 Project Structure

```
Healthcare-Symptom-Checker-main/
├── docker-compose.yml          # Master orchestrator for the stack
├── backend/
│   ├── Dockerfile              # Backend container definition
│   ├── main.py / server.py     # FastAPI application entrypoint
│   ├── requirements.txt        # Python dependencies
│   └── tests/                  # Pytest automated test suite
└── frontend/
    ├── Dockerfile              # Frontend container definition
    ├── public/                 # Static assets
    ├── src/                    # React frontend source code
    │   ├── context/            # AuthContext and state providers
    │   ├── pages/              # Routes (Login, Profile, Checker, History)
    │   ├── App.js              # Application router guards
    │   └── index.css           # Tailwind configuration
    ├── package.json            # Node dependencies
    └── tailwind.config.js      # Utility styling configuration
```

## 🐳 Instant Setup (Using Docker - Recommended)

The application is containerized. To instantly start it without installing any local Python or Node environments:

1. Guarantee Docker Desktop is running.
2. In the root directory, create a `.env` file for the backend containers.
   ```bash
   GEMINI_API_KEY="your_actual_key_here"
   GROQ_API_KEY="your_groq_key_here"
   MONGO_URL="mongodb+srv://..."
   DB_NAME="healthcare"
   JWT_SECRET_KEY="any_long_random_string_here"
   ```
3. Boot the stack:
   ```bash
   docker-compose up --build
   ```
4. Access the application at **http://localhost:3000**

---

## 🛠️ Step-by-Step Manual Setup Instructions

If you prefer to run it locally for development, ensure you have **Node.js (v18+)** and **Python (v3.10+)** installed.

### 1. Database & Cloud Services
You will need these credentials to run this application:
1. **Google Gemini API Key**: Get a free key from [Google AI Studio](https://aistudio.google.com/app/apikey).
2. **Groq API Key (optional but recommended)**: Used as automatic fallback if Gemini is unavailable.
3. **MongoDB Atlas Connection**: Get your connection string from MongoDB Atlas. Be sure to whitelist your IP (`0.0.0.0/0`) in the Atlas **Network Access** tab.

### 2. Start the Backend Server (Terminal 1)

Navigate to the backend directory and activate an isolated Python environment:
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Export your required environment variables:
```bash
export GEMINI_API_KEY="your_actual_key_here"
export GROQ_API_KEY="your_groq_key_here"
export MONGO_URL="mongodb+srv://..."
export DB_NAME="healthcare"
export JWT_SECRET_KEY="any_long_random_string_here"
```

Start the FastAPI application:
```bash
python -m uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

### 3. Start the Frontend Application (Terminal 2)

Open a new terminal window, navigate to the frontend directory, and run the React app:
```bash
cd frontend
npm install --legacy-peer-deps
npm start
```
*Note: We recommend tracking `--legacy-peer-deps` due to the strict dependency resolutions required by some older libraries.*

Navigate to **[http://localhost:3000](http://localhost:3000)** in your browser!

---

## 🛑 Common Troubleshooting

- **500 Internal Server Error (SSL Certificate Failed):** If you are running Python natively on a Mac, you may see a MongoDB timeout due to SSL certificates. This app utilizes `tlsCAFile=certifi.where()` to bypass this.
- **Frontend Appears Blank or Fails to Fetch:** If `npm start` succeeds but no requests reach the backend, verify your frontend environment variables. The app automatically falls back to `http://localhost:8000/api` if a `.env` file does not set `REACT_APP_BACKEND_URL`.

## 📜 Disclaimer
*This tool is for educational purposes only and is not a substitute for professional medical advice, diagnosis, or treatment. Always consult a qualified healthcare professional.*
