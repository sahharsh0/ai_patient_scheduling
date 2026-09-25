# SmartCare AI — Frontend

This is the frontend for **SmartCare AI**, a patient appointment scheduling system with AI-assisted booking.

The frontend is built with **Next.js, React, TypeScript, and Tailwind CSS** and communicates with the FastAPI backend through REST APIs.

## Features

The frontend currently includes:

* Patient registration and login
* Doctor login
* Admin login
* Patient dashboard
* Doctor dashboard
* Admin dashboard
* Doctor browsing
* Manual appointment booking
* AI appointment booking
* Appointment recommendations
* Appointment history
* Appointment cancellation and rescheduling
* Doctor availability management
* Doctor leave management
* Notifications
* Waitlist-related functionality

## Tech stack

* Next.js
* React
* TypeScript
* Tailwind CSS

## Running the frontend

First, make sure the SmartCare AI backend is running on:

```text
http://localhost:8000
```

Then open a terminal in the frontend directory:

```powershell
cd C:\Users\justi\mini_prj-t1\frontend
```

Install the dependencies:

```powershell
npm install
```

Create the local environment file:

```powershell
Copy-Item .env.example .env.local
```

Make sure `.env.local` contains:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Start the development server:

```powershell
npm run dev
```

If PowerShell blocks the npm command, use:

```powershell
npm.cmd run dev
```

Then open:

```text
http://localhost:3000
```

## Backend

The frontend expects the FastAPI backend to be available at:

```text
http://localhost:8000
```

The backend API documentation is available at:

```text
http://localhost:8000/docs
```

The backend is located in the project's `backend` directory.

## Project structure

```text
frontend/
├── app/
│   ├── ai-book/
│   ├── book/
│   ├── patient/
│   ├── doctor/
│   ├── admin/
│   └── ...
│
├── components/
├── hooks/
├── lib/
├── public/
├── services/
├── types/
├── .env.example
├── package.json
└── README.md
```

## AI booking

The AI booking page allows patients to describe what they need in normal language.

For example:

```text
I need a cardiologist tomorrow evening, someone experienced
```

The request is sent to the backend, where the NVIDIA AI service extracts the appointment requirements.

The frontend then displays the available recommendations returned by the backend.

The patient can select a recommended appointment and confirm the booking.

## Environment variables

The frontend uses:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Do not add private API keys to the frontend.

The NVIDIA API key is used by the backend and should remain inside the backend's `.env` file.

## Development

To stop the development server, press:

```text
Ctrl + C
```

in the terminal where `npm run dev` is running.
