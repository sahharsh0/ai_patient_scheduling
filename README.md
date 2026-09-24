# SmartCare AI — Patient Appointment Scheduling

An AI-assisted patient appointment scheduling system: Next.js frontend,
FastAPI backend, MySQL database, and a Claude-powered natural-language
booking assistant backed by real ML models and a transaction-safe
scheduling engine.

**Status:** functionally complete across all planned phases (auth,
scheduling engine, AI booking, ML predictions, waitlist, notifications,
admin dashboard). See `STATUS.md` for exactly what has and hasn't been
runtime-verified, and why.

## Demo accounts (seeded, DEV ONLY)

| Role    | Email               | Password          |
|---------|---------------------|-------------------|
| Admin   | admin@example.com   | DevPassword123!   |
| Doctor  | doctor@example.com  | DevPassword123!   |
| Patient | patient@example.com | DevPassword123!   |

**Change these before any production use.** All other seeded doctors and
patients have realistic Indian names (see `backend/seed.py`).

## Running it locally

### 1. Database
```bash
docker compose up -d mysql
```
(or point `DB_*` in `backend/.env` at your own MySQL 8+ instance)

### 2. Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env           # edit DB_*/ANTHROPIC_API_KEY as needed
alembic upgrade head
python seed.py
uvicorn app.main:app --reload
```
Visit `http://localhost:8000/api/health` and `http://localhost:8000/docs`.

To exercise the AI booking flow, set `ANTHROPIC_API_KEY` in `backend/.env`
first — without it, `/api/ai/parse` returns a clear "not configured"
clarification response rather than erroring.

To (re)train the ML models against your seeded data:
```bash
cd backend
python -m app.ml.train_models
```

### 3. Frontend
```bash
cd frontend
npm install
cp .env.example .env.local     # point NEXT_PUBLIC_API_URL at your backend
npm run dev
```
Visit `http://localhost:3000`.

### 4. Tests
```bash
cd backend
python -m pytest tests/ -v
```

### Docker (full stack)
```bash
docker compose up --build
```
The backend container runs `alembic upgrade head` automatically before
starting uvicorn (see `backend/docker-entrypoint.sh`).

## Project structure

```
smartcare-ai/
├── backend/
│   ├── app/
│   │   ├── core/          # config.py, database.py, security.py
│   │   ├── models/        # SQLAlchemy models + enums
│   │   ├── schemas/       # Pydantic request/response schemas
│   │   ├── api/           # FastAPI routers (auth, appointments, ai, doctors, ...)
│   │   ├── services/      # appointment/recommendation/notification/waitlist services
│   │   ├── ai/            # LLM parsing (service.py) + DB grounding (grounding.py)
│   │   ├── ml/            # trained models, categorical encoding, prediction service
│   │   └── scheduling/    # shared availability/overlap/leave logic (slots.py)
│   ├── alembic/           # migrations
│   ├── tests/
│   ├── seed.py
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── docker-entrypoint.sh
│   └── .env.example
├── frontend/               # Next.js 14 app (App Router) + Tailwind
├── docker-compose.yml
├── .gitignore
├── README.md               # this file
└── STATUS.md               # honest current status + verification notes
```

## Architecture notes

- **Scheduling engine** (`app/services/appointment_service.py` +
  `app/scheduling/slots.py`): every booking/reschedule locks the doctor row
  (`SELECT ... FOR UPDATE`) and re-validates availability, leave, and
  overlap conflicts inside that lock, so concurrent booking attempts for the
  same doctor are serialized by the database, not by application code.
- **AI booking flow**: natural language → `app/ai/service.py` (Claude
  tool-use, grounded with the real current date and the real specialization
  list) → `ParsedAppointmentRequest` (human concepts only, never a database
  ID) → `app/ai/grounding.py` resolves names to real rows via SQL →
  `app/services/recommendation_service.py` generates and ranks real
  available slots using the ML models → the patient picks one → booking
  goes through the exact same scheduling engine as manual booking.
- **ML models**: `duration_model.joblib` and `noshow_model.joblib`
  (RandomForest, trained on real seeded appointment history via
  `app/ml/train_models.py`). There is intentionally no trained
  "waiting-time model" — see `STATUS.md` for why.
