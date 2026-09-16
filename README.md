# AsliGhar

**Is this rental listing real?**

AsliGhar checks rental listings for the fraud pattern that's cheap to fake and expensive to catch by hand: reused photos, an implausible address, and rent that's too good to be true. It runs three independent checks and fuses them into one explainable risk score with cited evidence.

## Tech Stack

- **Backend:** Python, FastAPI, SQLite
- **Frontend:** React, Vite, TypeScript
- **Search/data:** SerpApi (`google_lens`, `google_maps`, `google_local`)
- **AI synthesis:** Groq (Llama 3.3 70B) — used only to summarize already-computed evidence, never to compute the score

## Repository Structure

```
AsliGhar/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── services/
│   │   ├── core/
│   │   ├── models/
│   │   └── main.py
│   ├── tests/
│   └── requirements.txt
└── frontend/
    ├── src/
    │   ├── components/
    │   ├── pages/
    │   └── App.tsx
    └── package.json
```

## Quick Start

```bash
# Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add SERPAPI_KEY and GROQ_API_KEY
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
cp .env.example .env
npm run dev
```

## Limitations

This produces a risk signal, not a verdict. A high score means "verify further before paying anything," not "this is definitely a scam." Reverse image search coverage depends on what's indexed, so a listing with unindexed stolen photos can still score low.
