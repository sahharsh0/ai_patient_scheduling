# SmartCare AI — Project Status

This file gives a practical overview of what is currently implemented and what has been tested locally.

The project has been developed as a college/project-level full-stack application. The main appointment booking, AI booking, scheduling, ML, authentication, notification, waitlist, and dashboard features are implemented.

Some production-level improvements are still possible, but the main application flow has been tested locally with a real MySQL database.

---

## Current status

**Overall: Functionally working locally**

The following parts have been implemented and locally verified:

* Authentication
* Patient, doctor, and admin roles
* MySQL database
* Database migrations
* Seed data
* Doctor availability
* Doctor leave management
* Manual appointment booking
* Appointment conflict checking
* AI natural-language appointment parsing
* NVIDIA AI integration
* AI appointment recommendations
* ML predictions
* Appointment notifications
* Waitlist functionality
* Admin statistics
* Frontend/backend integration

---

# Backend

## Fixed backend issues

Several issues from the earlier version of the project were fixed, including:

* Incorrect imports in the appointment API
* Schema and ORM model naming conflicts
* Invalid appointment status values
* Missing imports in the AI API
* Incorrect handling of the authenticated user
* Old Pydantic v1 configuration
* Scheduling and overlap logic problems
* Missing appointment duration field
* Client-supplied patient/doctor IDs where the authenticated user should be used

The backend now starts successfully with:

```powershell
uvicorn app.main:app --reload --port 8000
```

The health endpoint and Swagger documentation have been tested locally.

---

# Database

The project uses MySQL.

Current development database:

```text
Host: localhost
Port: 3306
Database: smartcare_ai
User: smartcare
```

Database migrations have been successfully applied using:

```powershell
alembic upgrade head
```

The seed script has also been successfully run.

The seeded database contains:

* 8 specializations
* 20 doctors
* 50 patients
* Around 300 historical appointments
* Upcoming scheduled appointments
* Demo accounts
* Doctor availability
* Doctor leave periods

---

# Scheduling engine

The scheduling system checks actual doctor availability before an appointment is created.

It checks:

* Weekly doctor availability
* Doctor leave
* Existing appointments
* Appointment duration
* Time overlap
* Requested date
* Requested time period

The overlap check uses an actual interval comparison rather than only checking whether two appointments start at the same time.

The booking process also locks the relevant doctor row while validating and creating the appointment. This helps prevent two simultaneous requests from reserving the same slot.

---

# AI booking

The AI system was originally designed around Claude, but the current project uses the **NVIDIA API**.

Current configuration:

```text
Provider: NVIDIA
Model: z-ai/glm-5.3-flash
API base: https://integrate.api.nvidia.com/v1
```

The API key is stored locally in `backend/.env` and is not committed to the repository.

---

## How the AI flow works

A patient can enter a request such as:

```text
I need a cardiologist tomorrow evening, someone experienced
```

The AI extracts information such as:

```text
Specialization: Cardiology
Date: 2026-09-25
Time: Evening
Experience preference: High
```

The AI does not create or guess database IDs.

The backend then:

1. Resolves the specialization against the database.
2. Finds matching doctors.
3. Generates real available appointment slots.
4. Filters the slots according to the requested date and time.
5. Uses the ML models to generate predictions.
6. Scores the available slots.
7. Shows the patient the recommended appointments.
8. Lets the patient choose a slot.
9. Sends the selected appointment through the normal appointment creation service.

The AI therefore does not bypass the normal scheduling system.

---

# AI verification

The following AI request was tested locally:

```text
I need a cardiologist tomorrow evening, someone experienced
```

The parser correctly identified:

```text
Specialization: Cardiology
Date: 2026-09-25
Time: Evening
Experience: High
```

The recommendation system returned real available slots for the requested date and evening time period.

After one of the recommended slots was booked, that slot was no longer returned as available.

This confirms that the AI recommendation flow is connected to the actual scheduling and database logic rather than displaying fixed demo data.

---

# Machine learning

The project currently uses two ML models:

```text
duration_model.joblib
noshow_model.joblib
```

They are used for:

* Appointment duration prediction
* No-show probability prediction

The prediction service is located at:

```text
backend/app/ml/service.py
```

The models are trained using appointment data from the application's database.

The previous categorical encoding approach based on Python's `hash()` function was replaced with fixed categorical mappings so that training and prediction use consistent values.

---

## ML dependency

The saved models were originally created with scikit-learn 1.7.2 while the environment had scikit-learn 1.5.2.

This produced model-version warnings.

The environment was updated to:

```text
scikit-learn 1.7.2
```

The ML predictor was then imported successfully and the recommendation flow was tested again without the previous version-mismatch warnings.

---

# Recommendation system

The recommendation system is located at:

```text
backend/app/services/recommendation_service.py
```

It combines:

* Doctor information
* Patient history where available
* Doctor history
* Appointment timing
* ML predictions
* Experience preference
* Wait preference
* Requested date
* Requested time

Explicit date and time preferences are treated as filters rather than simply being used as weak scoring preferences.

For example, if the patient asks for:

```text
tomorrow evening
```

the recommendation system searches the requested date and evening window instead of silently returning appointments from another date.

---

# Frontend

The frontend is built with:

* Next.js
* React
* TypeScript
* Tailwind CSS

The frontend successfully starts locally using:

```powershell
npm run dev
```

or, when PowerShell blocks the npm command:

```powershell
npm.cmd run dev
```

The application is available at:

```text
http://localhost:3000
```

---

# Frontend fixes

The following frontend issues were fixed:

* Broken JSX
* Unterminated strings
* Missing `use client`
* Rules-of-Hooks violation
* Authentication redirect race condition
* Client-side patient/doctor ID handling
* Registration field-name mismatch
* Duplicate `Dr.` displayed before doctor names
* AI booking input text visibility
* Incorrect admin booking link
* TypeScript callback typing issues

The authentication context now waits for the saved session to be restored before protected pages decide whether the user needs to be redirected.

---

# Appointment booking verification

A complete AI booking was tested locally.

The tested flow was:

```text
Login
  ↓
Patient dashboard
  ↓
AI booking
  ↓
Natural-language request
  ↓
AI parsing
  ↓
Doctor/slot recommendations
  ↓
Select appointment
  ↓
Create appointment
  ↓
Notification generated
  ↓
Appointment visible on patient dashboard
```

The appointment was created in the real MySQL database and appeared in the patient's dashboard.

A notification confirming the appointment was also generated.

---

# Notifications

The application includes in-app notifications.

Notifications are connected to appointment actions such as:

* Booking
* Cancellation
* Rescheduling
* Waitlist matching

The notification endpoint is:

```text
GET /api/notifications
```

---

# Waitlist

The waitlist feature has real backend endpoints and database integration.

The system can:

* Add patients to the waitlist
* Retrieve waitlist information
* Check the waitlist when an appointment is cancelled
* Notify a matching patient

---

# Doctor schedule management

Doctors can manage their availability and leave periods through the frontend.

The schedule page is:

```text
/doctor/schedule
```

The system also checks whether a new leave period conflicts with existing scheduled appointments and reports those conflicts to the doctor.

---

# Admin dashboard

The admin dashboard includes statistics calculated from the real database.

The backend endpoint is:

```text
GET /api/admin/stats
```

The statistics are not hard-coded.

---

# Authentication and security

The application uses JWT authentication.

Authenticated identity is taken from the logged-in user rather than trusting patient or doctor IDs supplied by the frontend.

Production safety checks are also included.

When production mode is enabled, the backend refuses to start if:

* The default JWT secret is still being used
* Debug mode is enabled
* Localhost is still allowed by the production CORS configuration

---

# Rate limiting

The backend includes request rate limiting.

The current implementation stores rate-limit information in memory.

This is suitable for the current single-process development setup, but it would need a shared store such as Redis for a multi-instance production deployment.

The previous issue where rate-limit failures returned HTTP 500 instead of HTTP 429 has been fixed.

---

# Testing completed

The following have been tested locally:

### Backend

* Backend startup
* API health check
* Swagger/OpenAPI
* Database connection
* Alembic migrations
* Seed script
* Authentication
* AI parsing
* AI recommendations
* Appointment creation
* Appointment conflict handling
* Notifications
* ML prediction

### Frontend

* Development server startup
* Login
* Patient dashboard
* AI booking page
* AI recommendation display
* Appointment selection
* Booking confirmation
* Patient appointment display

---

# Known limitations

These are not currently blocking the main application flow.

### Rate limiting

The rate limiter is in-memory, so it is not suitable for a multi-server deployment without a shared store.

### No email/SMS

Notifications are currently in-app only.

### Frontend automated tests

There are no full Jest/Playwright frontend test suites yet.

### Admin analytics

The admin dashboard currently provides statistics but does not include advanced charts or long-term trend analysis.

### Pagination

Some API endpoints use fixed limits instead of full pagination.

### No-show model

The usefulness of the no-show model depends on the amount and distribution of historical appointment data in the seeded database. A freshly seeded development database should be checked before treating the model's evaluation metrics as meaningful.

---

# Deployment

Docker configuration is included in the repository.

The backend Docker entrypoint runs:

```text
alembic upgrade head
```

before starting the FastAPI server.

The ML model files are included in the backend image.

A complete production Docker deployment has not been the main development environment, so production deployment should still be tested separately before being relied upon.

---

# Important security note

Never commit the following files containing real credentials:

```text
backend/.env
frontend/.env.local
```

These files can contain:

* NVIDIA API keys
* Database passwords
* JWT secrets
* Other private configuration

Only the example configuration files should be committed:

```text
backend/.env.example
frontend/.env.example
```

---

# Demo accounts

The development seed provides:

| Role    | Email                                             | Password        |
| ------- | ------------------------------------------------- | --------------- |
| Admin   | [admin@example.com](mailto:admin@example.com)     | DevPassword123! |
| Doctor  | [doctor@example.com](mailto:doctor@example.com)   | DevPassword123! |
| Patient | [patient@example.com](mailto:patient@example.com) | DevPassword123! |

These accounts are for development/demo use only.

---

# Conclusion

SmartCare AI currently has a working local full-stack implementation covering the main planned features.

The most important end-to-end flow has been verified:

```text
Natural-language request
        ↓
NVIDIA AI parsing
        ↓
Database grounding
        ↓
Real doctor availability
        ↓
ML-based recommendation
        ↓
Patient selects slot
        ↓
Normal scheduling engine
        ↓
Database appointment
        ↓
Notification
```

The remaining work is mainly around production hardening, scaling, automated frontend testing, and additional UI improvements rather than replacing the core application architecture.
