# MeetMind — Relationship Memory Agent

FastAPI + SQLite backend, Claude API for extraction / Q&A / email drafting, regex fallback so the demo never breaks.
The backend also serves the frontend, so it is one process, one URL.

## Structure
backend/main.py    API routes + static frontend
backend/ai.py      Claude calls (extract, ask, email) + regex fallback
backend/db.py      SQLite schema: meetings, promises, meta
backend/frontend/  the 5-screen web app (calls /api/*)

## Run locally
cd backend
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                   # add ANTHROPIC_API_KEY (optional)
uvicorn main:app --reload
Open http://localhost:8000 . Header shows "AI on" (key found) or "Rules mode" (fallback).
Interactive API docs: http://localhost:8000/docs

## API
GET  /api/health       {ok, ai}
GET  /api/state        all meetings + promises
PUT  /api/state        save full state (single-workspace demo)
POST /api/extract      {notes, attendees} -> promises, concerns, preferences, decisions
POST /api/ask          {question} -> answer + cited meetings (searches saved past meetings)
POST /api/email        {meeting_id} -> follow-up email draft

## Deploy (Render, free tier)
1. Push this folder to GitHub.
2. Render -> New Web Service -> root dir `backend`, build `pip install -r requirements.txt`,
   start `uvicorn main:app --host 0.0.0.0 --port $PORT`.
3. Environment: ANTHROPIC_API_KEY, and optionally MEETMIND_DB=/data/meetmind.db with a 1 GB disk mounted at /data
   (free tier disks are ephemeral: data resets on redeploy; attach a disk or use Postgres for real persistence).
Docker: docker build -t meetmind backend && docker run -p 8000:8000 -e ANTHROPIC_API_KEY=... -v mm:/data meetmind

## Known limits / next steps
- One shared workspace, no login. Add auth + a user_id column per table for multi-user.
- PUT /api/state replaces all rows (fine for a demo; move to per-record endpoints later).
- Swap SQLite for Postgres, add Google Calendar / Gmail ingestion (phase 2).
