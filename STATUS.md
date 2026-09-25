# SmartCare AI — Project Status

This document provides the current implementation and testing status of SmartCare AI.

SmartCare AI is a full-stack AI-powered patient appointment scheduling system developed as a college/project-level application. The system integrates a web frontend, FastAPI backend, MySQL database, NVIDIA AI, machine learning models, and a deterministic appointment scheduling engine.

## Overall Project Status

**Status: Functionally working locally**

The main application workflow is implemented and has been tested locally using a real MySQL database.

### Current implementation status

| Feature                                 | Status  |
| --------------------------------------- | ------- |
| Authentication                          | Working |
| Patient, Doctor, and Admin roles        | Working |
| MySQL database                          | Working |
| Database migrations                     | Working |
| Seed data                               | Working |
| Doctor availability                     | Working |
| Doctor leave management                 | Working |
| Manual appointment booking              | Working |
| Appointment conflict checking           | Working |
| AI natural-language appointment parsing | Working |
| NVIDIA AI integration                   | Working |
| AI appointment recommendations          | Working |
| ML predictions                          | Working |
| Appointment notifications               | Working |
| Waitlist functionality                  | Working |
| Admin statistics                        | Working |
| Frontend/backend integration            | Working |

---

# System Architecture

SmartCare AI consists of the following major components:

```text
Frontend
Next.js + React + TypeScript + Tailwind CSS
                    ↓
                REST API
                    ↓
Backend
FastAPI + Pydantic + SQLAlchemy
                    ↓
              MySQL Database
                    ↓
        Scheduling + ML Services
                    ↑
              NVIDIA AI
```

The AI is used primarily for understanding natural-language appointment requests. Appointment availability, scheduling constraints, database operations, and final booking are handled by the backend.

---

# Backend Status

The backend is implemented using:

* FastAPI
* Pydantic
* SQLAlchemy
* Alembic
* JWT authentication
* Python

The backend starts successfully using:

```powershell
uvicorn app.main:app --reload --port 8000
```

The API health endpoint and Swagger/OpenAPI documentation have been tested locally.

### Backend capabilities

The backend currently provides:

* Authentication
* Role-based access
* Patient management
* Doctor management
* Appointment management
* Doctor availability management
* Doctor leave management
* AI appointment parsing
* AI recommendations
* Machine learning predictions
* Notifications
* Waitlist management
* Admin statistics
* Rate limiting

---

# Database Status

The project uses MySQL.

### Development database

```text
Host: localhost
Port: 3306
Database: smartcare_ai
User: smartcare
```

Database migrations are managed using Alembic.

Current database schema has been successfully migrated using:

```powershell
alembic upgrade head
```

### Seeded development data

The development database contains:

* 8 medical specializations
* 20 doctors
* 50 patients
* Around 300 historical appointments
* Upcoming scheduled appointments
* Demo accounts
* Doctor availability
* Doctor leave periods

The database is used by the scheduling, recommendation, notification, and dashboard systems rather than being used only as static demonstration data.

---

# Authentication and Authorization

The application uses JWT-based authentication.

Three user roles are supported:

```text
Patient
Doctor
Admin
```

Authentication determines the identity of the logged-in user, while authorization determines which operations that user is allowed to perform.

The authenticated user's identity is obtained from the JWT rather than relying on patient or doctor IDs supplied by the frontend.

The frontend also maintains the authenticated session between page refreshes until the JWT expires or the user logs out.

---

# Appointment Scheduling

The appointment scheduling engine uses actual doctor schedules and database information.

Before creating an appointment, the system checks:

* Doctor's weekly availability
* Doctor leave periods
* Existing appointments
* Appointment duration
* Time overlap
* Requested date
* Requested time period

The system uses interval-based overlap checking rather than only comparing appointment start times.

The booking process also locks the relevant doctor record while validating and creating an appointment, helping prevent simultaneous requests from reserving the same slot.

---

# Manual Booking

Patients can book appointments through the standard booking interface.

The manual booking process is:

```text
Select specialization
        ↓
Select doctor
        ↓
Select date
        ↓
Select available time
        ↓
Confirm appointment
        ↓
Appointment stored in MySQL
        ↓
Notification generated
```

The appointment is created through the backend scheduling service and stored in the actual database.

---

# AI Booking

The AI booking system uses the **NVIDIA API**.

### Current AI configuration

```text
Provider: NVIDIA
Model: z-ai/glm-5.3-flash
API base: https://integrate.api.nvidia.com/v1
```

The NVIDIA API key is stored locally in `backend/.env` and is excluded from version control.

## AI request processing

Patients can describe their appointment request using natural language.

Example:

```text
I need a cardiologist tomorrow evening, someone experienced
```

The AI extracts structured information such as:

```text
Specialization: Cardiology
Date: 2026-09-25
Time: Evening
Experience preference: High
```

The backend then validates and processes this information.

### AI workflow

```text
Patient natural-language request
              ↓
        NVIDIA AI parsing
              ↓
     Structured appointment data
              ↓
 Database specialization matching
              ↓
       Doctor availability
              ↓
      Scheduling constraints
              ↓
        ML predictions
              ↓
     Recommendation scoring
              ↓
       Available time slots
              ↓
       Patient selects slot
              ↓
     Normal booking service
              ↓
      Appointment created
```

The AI does not directly create appointments or select database IDs.

---

# AI Verification Status

The AI appointment workflow has been tested locally.

Test request:

```text
I need a cardiologist tomorrow evening, someone experienced
```

The system identified:

```text
Specialization: Cardiology
Date: 2026-09-25
Time: Evening
Experience: High
```

The recommendation system then returned available appointments matching the requested date and evening period.

After a recommended appointment was booked, that slot was no longer returned as available.

This demonstrates that the AI recommendation system is connected to the actual scheduling engine and database.

---

# Machine Learning Status

The project currently contains two trained machine learning models:

```text
duration_model.joblib
noshow_model.joblib
```

### Models

**Appointment Duration Model**

Predicts the expected duration of an appointment.

**No-show Model**

Predicts the probability of a patient not attending an appointment.

The ML service is located at:

```text
backend/app/ml/service.py
```

The models use data from the application's appointment database.

Categorical features use fixed mappings so that the same encoding is used during training and prediction.

### Current ML environment

```text
scikit-learn: 1.7.2
```

The ML prediction service has been successfully imported and tested as part of the recommendation workflow.

The ML predictions are used as supporting information for recommendation scoring and are not treated as guaranteed outcomes.

---

# Recommendation System

The recommendation engine is located at:

```text
backend/app/services/recommendation_service.py
```

It considers:

* Doctor information
* Patient history where available
* Doctor history
* Appointment timing
* Predicted appointment duration
* Predicted no-show probability
* Experience preference
* Waiting-time preference
* Requested date
* Requested time

Explicit date and time requirements are treated as filters.

For example:

```text
tomorrow evening
```

causes the system to search the requested date and evening period rather than returning an appointment from another date.

---

# Notifications

The system provides in-app notifications.

Notifications are generated for appointment-related events including:

* Booking
* Cancellation
* Rescheduling
* Waitlist matching

Notification endpoint:

```text
GET /api/notifications
```

Notifications are currently stored and displayed inside the application.

---

# Waitlist

The application includes a database-backed waitlist system.

The waitlist can:

* Add patients to the waitlist
* Retrieve waitlist information
* Detect matching availability after cancellation
* Notify matching patients

The waitlist functionality is implemented through backend APIs and database records.

---

# Doctor Schedule Management

Doctors can manage their schedules through:

```text
/doctor/schedule
```

The scheduling system supports:

* Weekly availability
* Leave periods
* Schedule updates
* Leave conflict checking

The system checks whether a new leave period conflicts with existing scheduled appointments.

---

# Admin Dashboard

The admin dashboard provides statistics calculated from the actual database.

Backend endpoint:

```text
GET /api/admin/stats
```

The dashboard currently includes database-driven statistics rather than hard-coded values.

The current admin account is configured as:

```text
Name: Harsh
Email: admin@example.com
Role: Admin
```

---

# Frontend Status

The frontend is built using:

* Next.js
* React
* TypeScript
* Tailwind CSS

The development server runs using:

```powershell
npm run dev
```

or:

```powershell
npm.cmd run dev
```

The application is available locally at:

```text
http://localhost:3000
```

### Current frontend functionality

The frontend provides interfaces for:

* Login
* Registration
* Patient dashboard
* Doctor dashboard
* Admin dashboard
* Manual appointment booking
* AI appointment booking
* Appointment management
* Doctor schedule management
* Notifications
* Waitlist functionality

Frontend and backend communication is implemented through REST APIs.

---

# End-to-End Application Flow

The main patient workflow has been tested locally:

```text
Login
  ↓
Patient Dashboard
  ↓
AI Booking
  ↓
Natural-Language Request
  ↓
NVIDIA AI Parsing
  ↓
Database Validation
  ↓
Doctor Availability
  ↓
ML Recommendation
  ↓
Select Appointment
  ↓
Create Appointment
  ↓
MySQL Database
  ↓
Notification
  ↓
Appointment Displayed
```

The appointment was created in the real MySQL database and subsequently appeared in the patient's dashboard.

---

# Security Status

The application uses:

* JWT authentication
* Password hashing
* Role-based authorization
* Environment-based secrets
* Authenticated-user identity
* Backend validation
* Rate limiting

Production safety checks are also included.

When production mode is enabled, the backend checks that:

* The default JWT secret is not being used.
* Debug mode is disabled.
* Localhost is not present in the production CORS configuration.

---

# Rate Limiting

The backend includes API rate limiting.

The current rate limiter stores its state in memory.

This is appropriate for the current single-process development environment.

For a multi-instance production deployment, a shared store such as Redis would be required.

Rate-limit failures return HTTP `429 Too Many Requests`.

---

# Testing Status

## Backend testing

The following have been tested locally:

* Backend startup
* API health check
* Swagger/OpenAPI
* MySQL database connection
* Alembic migrations
* Seed data
* Authentication
* Role-based access
* AI parsing
* NVIDIA AI integration
* AI recommendations
* Appointment creation
* Appointment conflict handling
* Notifications
* ML prediction

## Frontend testing

The following have been tested locally:

* Development server startup
* Login
* Registration
* Patient dashboard
* AI booking
* AI recommendation display
* Appointment selection
* Appointment booking
* Booking confirmation
* Patient appointment display

---

# Current Limitations

The core application is functional locally, but several areas can still be improved.

### Production deployment

A complete production deployment has not yet been the primary development environment and should be tested separately.

### Rate limiting

The current rate limiter uses in-memory storage and is therefore intended for a single-process environment.

### Notifications

Notifications are currently in-app only.

There is currently no email or SMS notification service.

### Automated frontend testing

There are currently no complete Jest or Playwright frontend test suites.

### Admin analytics

The admin dashboard provides database-driven statistics but does not currently include advanced charts or long-term trend analysis.

### Pagination

Some API endpoints currently use fixed result limits rather than complete pagination.

### ML evaluation

The no-show model's usefulness depends on the amount and distribution of historical appointment data available in the development database. More representative real-world data would be required for meaningful production evaluation.

### AI dependency

AI appointment parsing depends on access to the NVIDIA API and a valid API key.

---

# Deployment Status

Docker configuration is included in the repository.

The backend container runs database migrations before starting the FastAPI server:

```text
alembic upgrade head
```

The ML model files are included in the backend image.

The application is currently considered **locally functional**, while production deployment requires additional testing and configuration.

---

# Security and Environment Files

Private configuration files are excluded from version control.

The following files should never contain committed credentials:

```text
backend/.env
frontend/.env.local
```

These files may contain:

* NVIDIA API keys
* Database passwords
* JWT secrets
* Private configuration

Only example configuration files should be committed:

```text
backend/.env.example
frontend/.env.example
```

---

# Demo Accounts

The development seed provides the following accounts:

| Role    | Email                                             | Password        |
| ------- | ------------------------------------------------- | --------------- |
| Admin   | [admin@example.com](mailto:admin@example.com)     | DevPassword123! |
| Doctor  | [doctor@example.com](mailto:doctor@example.com)   | DevPassword123! |
| Patient | [patient@example.com](mailto:patient@example.com) | DevPassword123! |

These accounts are intended for development and demonstration purposes only.

---

# Final Project Status

**SmartCare AI is currently a functionally working local full-stack application.**

The major planned components are implemented:

```text
Frontend
    ✓
Backend
    ✓
MySQL Database
    ✓
Authentication
    ✓
Role-based Access
    ✓
Manual Booking
    ✓
AI Booking
    ✓
NVIDIA AI Integration
    ✓
Scheduling Engine
    ✓
Machine Learning
    ✓
Recommendations
    ✓
Notifications
    ✓
Waitlist
    ✓
Admin Dashboard
    ✓
Docker Configuration
    ✓
```

The core end-to-end workflow is operational:

```text
Natural-Language Appointment Request
                ↓
          NVIDIA AI Parsing
                ↓
        Database Grounding
                ↓
      Doctor Availability
                ↓
        ML Predictions
                ↓
     Appointment Recommendation
                ↓
        Patient Selection
                ↓
      Scheduling Validation
                ↓
       MySQL Appointment
                ↓
          Notification
```

The current remaining work is primarily related to production deployment, scaling, automated testing, advanced analytics, external notification services, and improving the ML models with larger and more representative datasets.
