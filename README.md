# SmartCare AI

SmartCare AI is a patient appointment scheduling system that helps patients find and book doctor appointments using either a normal booking form or a natural-language AI assistant.

The project combines a **Next.js frontend**, **FastAPI backend**, **MySQL database**, **NVIDIA-hosted AI model**, machine-learning predictions, and a scheduling system that checks real doctor availability before allowing an appointment to be booked.

The main goal of the project is to make appointment booking easier while keeping the actual scheduling logic reliable and database-driven.

---

## What the project can do

### Patient

* Register and log in
* View available doctors
* Search doctors by specialization
* Book appointments
* Reschedule or cancel appointments
* Use the AI appointment assistant
* Receive appointment notifications
* View upcoming and previous appointments

### Doctor

* Log in through the doctor account
* View scheduled appointments
* Manage availability
* Manage leave periods
* View relevant appointment information

### Admin

* Log in through the admin account
* View system information
* Manage doctors and specializations
* Access the admin dashboard

### AI booking

Instead of filling out several fields manually, a patient can type something like:

> I need a cardiologist tomorrow evening, someone experienced.

The system understands the request and extracts information such as:

* Specialization
* Date
* Time preference
* Experience preference

It then checks the actual database for matching doctors and available slots.

The patient chooses a suggested slot, and the appointment is finally created through the same scheduling system used by normal bookings.

---

## Technology used

### Frontend

* Next.js
* React
* TypeScript
* Tailwind CSS

### Backend

* Python
* FastAPI
* Pydantic
* SQLAlchemy
* Alembic
* JWT authentication

### Database

* MySQL

### AI

* NVIDIA API
* `z-ai/glm-5.3-flash`
* OpenAI-compatible API interface

### Machine Learning

* scikit-learn
* Random Forest models
* Appointment duration prediction
* No-show probability prediction

---

## Project structure

```text
smartcare-ai/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── auth.py
│   │   │   ├── appointments.py
│   │   │   ├── ai.py
│   │   │   ├── doctors.py
│   │   │   └── ...
│   │   │
│   │   ├── ai/
│   │   │   ├── service.py
│   │   │   └── grounding.py
│   │   │
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── database.py
│   │   │   └── security.py
│   │   │
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── scheduling/
│   │   └── ml/
│   │       ├── service.py
│   │       ├── train_models.py
│   │       ├── categorical_maps.py
│   │       └── models/
│   │
│   ├── alembic/
│   ├── tests/
│   ├── seed.py
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── docker-entrypoint.sh
│   └── .env.example
│
├── frontend/
│   ├── app/
│   │   ├── ai-book/
│   │   ├── book/
│   │   ├── patient/
│   │   └── ...
│   ├── components/
│   ├── services/
│   └── types/
│
├── docker-compose.yml
├── .gitignore
├── README.md
└── STATUS.md
```

---

# Running the project locally

The current development setup uses a local MySQL installation.

You do **not** need to start a Docker MySQL container if MySQL is already running on your machine.

## 1. Database

The project currently uses:

```text
Host: localhost
Port: 3306
Database: smartcare_ai
User: smartcare
```

Make sure your MySQL service is running.

On the current Windows development setup, the MySQL service is:

```text
MySQL94
```

The database and user should be created before running the backend.

---

# 2. Backend

Open a terminal and go to the backend:

```powershell
cd C:\Users\justi\mini_prj-t1\backend
```

Activate the project's virtual environment:

```powershell
..\venv\Scripts\Activate.ps1
```

Install the dependencies:

```powershell
pip install -r requirements.txt
```

Create your environment file from the example:

```powershell
Copy-Item .env.example .env
```

Then edit `backend/.env`.

Your local configuration should contain values similar to:

```env
APP_NAME=SmartCare AI
ENV=development
DEBUG=true

DB_HOST=localhost
DB_PORT=3306
DB_NAME=smartcare_ai
DB_USER=smartcare
DB_PASSWORD=your_database_password

JWT_SECRET_KEY=your_development_secret

CORS_ALLOWED_ORIGINS=["http://localhost:3000"]

AI_PROVIDER=nvidia
NVIDIA_API_KEY=your_nvidia_api_key
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
AI_MODEL=z-ai/glm-5.3-flash
```

**Do not commit `.env` to GitHub.**

Run the database migrations:

```powershell
alembic upgrade head
```

Seed the database:

```powershell
python seed.py
```

Then start FastAPI:

```powershell
uvicorn app.main:app --reload --port 8000
```

The backend will be available at:

```text
http://localhost:8000
```

API documentation:

```text
http://localhost:8000/docs
```

Health check:

```text
http://localhost:8000/api/health
```

---

# 3. Frontend

Open a **second terminal**.

Go to the frontend:

```powershell
cd C:\Users\justi\mini_prj-t1\frontend
```

Install the frontend dependencies:

```powershell
npm install
```

Create the local environment file:

```powershell
Copy-Item .env.example .env.local
```

Make sure it points to the backend:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Start the frontend:

```powershell
npm run dev
```

If PowerShell gives an npm execution-policy error, use:

```powershell
npm.cmd run dev
```

The frontend will be available at:

```text
http://localhost:3000
```

---

# 4. Quick start

Once everything has been configured, you normally only need two terminals.

### Terminal 1: Backend

```powershell
cd C:\Users\justi\mini_prj-t1\backend
..\venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

### Terminal 2: Frontend

```powershell
cd C:\Users\justi\mini_prj-t1\frontend
npm run dev
```

Then open:

```text
http://localhost:3000
```

---

# Demo accounts

The database seed creates development accounts.

| Role    | Email                                             | Password        |
| ------- | ------------------------------------------------- | --------------- |
| Admin   | [admin@example.com](mailto:admin@example.com)     | DevPassword123! |
| Doctor  | [doctor@example.com](mailto:doctor@example.com)   | DevPassword123! |
| Patient | [patient@example.com](mailto:patient@example.com) | DevPassword123! |

These accounts are for development and demonstration only.

Do not use these credentials in a production deployment.

---

# How the AI booking works

The AI booking system is divided into several steps.

```text
Patient's natural-language request
            │
            ▼
      NVIDIA AI model
            │
            ▼
 Appointment request parser
            │
            ▼
 Real specialization/date/time
            │
            ▼
 Database grounding
            │
            ▼
 Real doctors and availability
            │
            ▼
 ML predictions + slot scoring
            │
            ▼
 Recommended appointment slots
            │
            ▼
 Patient selects a slot
            │
            ▼
 Normal appointment booking engine
            │
            ▼
 Confirmed appointment
```

For example:

```text
"I need a cardiologist tomorrow evening, someone experienced"
```

is converted into structured information similar to:

```text
Specialization: Cardiology
Date: 2026-09-25
Time: Evening
Experience: High
```

The AI does not directly choose a database doctor ID.

The backend resolves the specialization against the actual database and then finds real doctors and available appointment slots.

---

# Scheduling system

The scheduling engine checks the actual database before creating an appointment.

It considers:

* Doctor availability
* Doctor leave
* Existing appointments
* Appointment duration
* Time conflicts
* Requested date
* Requested time period

When an appointment is being created, the doctor record is locked during the critical scheduling operation so that two simultaneous booking attempts cannot incorrectly reserve the same slot.

This means the AI suggestions are not simply displaying fake or hard-coded appointment times.

---

# Machine learning

The project contains two trained ML models:

```text
backend/app/ml/models/
├── duration_model.joblib
├── noshow_model.joblib
├── categorical_maps.json
└── feature_names.json
```

The models are used by:

```text
backend/app/ml/service.py
```

The system currently uses ML for:

* Predicting appointment duration
* Predicting no-show probability

The predictions are used as part of appointment slot scoring.

To retrain the models:

```powershell
cd C:\Users\justi\mini_prj-t1\backend
python -m app.ml.train_models
```

The project currently does not use a separate trained waiting-time model.

---

# Testing

Backend tests can be run with:

```powershell
cd backend
python -m pytest tests/ -v
```

The AI parsing and recommendation flow can also be tested through the API documentation:

```text
http://localhost:8000/docs
```

---

# Docker

Docker configuration is included in the repository for environments where the full stack needs to be containerized.

To build and start the stack:

```bash
docker compose up --build
```

For the current Windows development setup, however, the backend and frontend are normally run directly while MySQL runs as the local MySQL service.

---

# Important files

### Backend configuration

```text
backend/.env
backend/.env.example
backend/app/core/config.py
```

### AI

```text
backend/app/ai/service.py
backend/app/ai/grounding.py
backend/app/api/ai.py
```

### Scheduling

```text
backend/app/services/appointment_service.py
backend/app/services/recommendation_service.py
backend/app/scheduling/slots.py
```

### Machine learning

```text
backend/app/ml/service.py
backend/app/ml/train_models.py
backend/app/ml/models/
```

### Frontend AI booking

```text
frontend/app/ai-book/page.tsx
```

---

# Security notes

Never commit secrets to GitHub.

The following should remain local:

```text
.env
.env.local
```

This includes:

* NVIDIA API keys
* Database passwords
* JWT secrets
* Other private configuration values

The repository should contain `.env.example` files with placeholder values instead.

---

# Current project status

The main SmartCare AI functionality has been implemented and tested locally, including:

* Authentication
* Patient, doctor and admin roles
* MySQL database
* Database migrations
* Seed data
* Doctor availability
* Leave management
* Appointment booking
* Appointment conflict checking
* AI natural-language parsing
* NVIDIA AI integration
* AI-based appointment recommendations
* ML predictions
* Notifications
* Waitlist functionality
* Admin dashboard
* Frontend and backend API integration

The project is currently intended as a development/college project rather than a production medical system.

See `STATUS.md` for the more detailed verification notes.
