import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv
load_dotenv()
from fastapi import Body, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import ai, db

@asynccontextmanager
async def lifespan(_):
    db.init(); yield

app = FastAPI(title="MeetMind API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("CORS_ORIGINS", "*").split(","), allow_methods=["*"], allow_headers=["*"])

class ExtractIn(BaseModel): notes: str; attendees: list[str] = []
class AskIn(BaseModel): question: str
class EmailIn(BaseModel): meeting_id: int

@app.get("/api/health")
def health(): return {"ok": True, "ai": ai.enabled()}

@app.get("/api/state")
def get_state(): return db.get_state()

@app.put("/api/state")
def put_state(state: dict = Body(...)):
    db.put_state(state); return {"ok": True}

@app.post("/api/extract")
def extract(b: ExtractIn): return ai.extract(b.notes, b.attendees)

@app.post("/api/ask")
def ask(b: AskIn):
    past = [m for m in db.get_state()["m"] if m["type"] == "past"]
    return ai.ask(b.question, past)

@app.post("/api/email")
def email(b: EmailIn):
    s = db.get_state(); m = next((x for x in s["m"] if x["id"] == b.meeting_id), None)
    if not m: raise HTTPException(404, "meeting not found")
    return {"email": ai.email(m, [q for q in s["p"] if q["mid"] == b.meeting_id]), "source": "ai" if ai.enabled() else "template"}

app.mount("/", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "frontend"), html=True), name="ui")
