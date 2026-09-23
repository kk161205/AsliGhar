# AsliGhar

**Is this rental listing real?**

AsliGhar checks rental listings for the fraud pattern that's cheap to fake and expensive to catch by hand: reused photos, an implausible address, and rent that's too good to be true. It runs three independent checks and fuses them into one explainable risk score with cited evidence.

## Tech Stack

- **Backend:** Python, FastAPI, Postgres (Neon)
- **Frontend:** React, Vite, TypeScript
- **Search/data:** SerpApi (`google_lens`, `google_maps`, organic `google`)
- **AI synthesis:** Groq (`openai/gpt-oss-120b`) — used only to summarize already-computed evidence, never to compute the score
- **Auth:** `bcrypt` password hashing, session cookies (JWT, `httpOnly`)

## Repository Structure

```
AsliGhar/
├── backend/
│   ├── app/
│   │   ├── api/            # scan.py, auth.py
│   │   ├── services/       # serpapi_client, groq_client, scoring, evidence, auth_service
│   │   ├── core/           # config, constants, logging, rate limiting, auth
│   │   ├── models/         # Pydantic schemas + SQLAlchemy models
│   │   └── main.py
│   ├── scripts/            # one-time DB migrations
│   ├── tests/
│   └── requirements.txt
└── frontend/
    ├── src/
    │   ├── auth/            # session state
    │   ├── components/
    │   ├── pages/           # Landing, Login, Signup, Dashboard, Scan, Results, HowItWorks
    │   └── App.tsx
    └── package.json
```

## Quick Start

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add SERPAPI_KEY, GROQ_API_KEY, DATABASE_URL, JWT_SECRET
uvicorn app.main:app --reload --port 8000

# Frontend (no env file needed — the dev server proxies /api to the backend)
cd frontend
npm install
npm run dev
```

`JWT_SECRET` can be generated with:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

If your database already has data in it from before authentication was added, run the migration scripts under `backend/scripts/` once (in order) before starting the server — `Base.metadata.create_all` only creates missing tables, it never alters an existing table's columns.

## Deployment

Frontend on Vercel, backend on Render, database on Neon. Vercel rewrites `/api/*` to the Render backend (see `frontend/vercel.json`), so the browser only ever talks to the Vercel origin — the backend's `CORS_ALLOWED_ORIGINS` setting only matters for a setup that skips that rewrite. `COOKIE_SECURE=true` and `PUBLIC_BASE_URL` pointing at the public Render URL are both required in production; the latter is also what makes reverse image search possible at all (see Limitations below).

## Signing in

The scan form requires an account. Sign up with an email, password, full name, and city (your city prefills the scan form's city field on future scans). Sessions last 7 days.

## Limitations

This produces a risk signal, not a verdict. A high score means "verify further before paying anything," not "this is definitely a scam." Reverse image search coverage depends on what's indexed, so a listing with unindexed stolen photos can still score low. Image-reuse detection specifically requires the backend to be reachable from the public internet — `google_lens` can't fetch a photo hosted at `localhost`.
