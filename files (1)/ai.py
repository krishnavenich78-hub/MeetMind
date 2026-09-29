"""LLM layer: Claude does the work, regex rules are the fallback so the demo never breaks."""
import json, logging, os, re
log = logging.getLogger("meetmind")
try:
    from anthropic import Anthropic
    client = Anthropic() if os.getenv("ANTHROPIC_API_KEY") else None
except Exception:  # package missing or bad config
    client = None
FAST = os.getenv("MEETMIND_FAST_MODEL", "claude-haiku-4-5-20251001")
SMART = os.getenv("MEETMIND_MODEL", "claude-sonnet-5")
def enabled(): return client is not None

def llm(model, system, user, max_tokens=1500):
    r = client.messages.create(model=model, max_tokens=max_tokens, system=system,
                               messages=[{"role": "user", "content": user}])
    return "".join(b.text for b in r.content if b.type == "text").strip()

# ---------- regex fallback ----------
I = re.I
PRM = re.compile(r"\b(will|shall|promised|agreed to|to send|to share|to schedule)\b", I)
CON = re.compile(r"concern|worried|worry|risk|blocker|issue|expensive|budget|security|delay|unhappy", I)
PRF = re.compile(r"prefer|likes|wants|asked for|only want|hates", I)
DEC = re.compile(r"decided|agreed on|approved|confirmed|signed off", I)
DUE = re.compile(r"(by (?:mon|tues|wednes|thurs|fri|satur|sun)day|by tomorrow|tomorrow|next week|this week|by end of \w+)", I)

def regex_extract(notes):
    o = {"promises": [], "concerns": [], "preferences": [], "decisions": []}
    for s in (x.strip() for x in re.findall(r"[^.!?\n]+[.!?]?", notes)):
        if not s: continue
        m = re.match(r"^(I|We|[A-Z][a-z]+|The [a-z]+(?: team)?)\b", s); nm = m.group(1) if m else "Team"
        if PRM.search(s) and not CON.search(s):
            d = DUE.search(s)
            o["promises"].append({"owner": "Me" if nm == "I" else nm, "text": s.rstrip("."), "due": d.group(1) if d else "no date"})
        elif CON.search(s): o["concerns"].append(s)
        elif PRF.search(s): o["preferences"].append(s)
        elif DEC.search(s): o["decisions"].append(s)
    return o

# ---------- extraction ----------
EXTRACT_SYS = ('You extract structured memory from meeting notes. Return ONLY valid JSON, no markdown: '
 '{"promises":[{"owner":"first name, or Me if the note author","text":"full commitment","due":"date phrase or no date"}],'
 '"concerns":["..."],"preferences":["..."],"decisions":["..."]}. Every concern and preference must be a full sentence '
 'that names the person it belongs to. Include implicit promises like "I\'ll sort out a discount".')

def _json(t):
    t = re.sub(r"^```(?:json)?|```$", "", t.strip(), flags=re.M).strip()
    return json.loads(t[t.index("{"): t.rindex("}") + 1])

def extract(notes, attendees):
    if client and notes.strip():
        try:
            r = _json(llm(FAST, EXTRACT_SYS, f"Attendees: {', '.join(attendees)}\n\nNotes:\n{notes}"))
            strs = lambda k: [v for v in r.get(k, []) if isinstance(v, str) and v]
            return {"source": "ai", "concerns": strs("concerns"), "preferences": strs("preferences"),
                    "decisions": strs("decisions"),
                    "promises": [{"owner": str(p.get("owner") or "Team"), "text": str(p["text"]),
                                  "due": str(p.get("due") or "no date")} for p in r["promises"] if p.get("text")]}
        except Exception as e:
            log.warning("AI extract failed, using rules: %s", e)
    return {"source": "rules", **regex_extract(notes)}

# ---------- ask your history ----------
def ask(question, meetings):
    ctx = "\n\n".join(f"[{m['title']} · {m['date']} · with {', '.join(m['att'])}]\n{m['notes']}"
                      + (f"\nOutcome: {m['outcome'].get('out')}. Worked: {m['outcome'].get('worked')}" if m.get("outcome") else "")
                      for m in meetings)
    if client and meetings:
        try:
            a = llm(SMART, "Answer ONLY from the meeting notes provided. Be concise. Cite meeting title and date for each fact. "
                    "If the notes don't say, say nothing was found.", f"Question: {question}\n\n{ctx}", 600)
            return {"answer": a, "source": "ai", "sources": [{"title": m["title"], "date": m["date"]} for m in meetings if m["title"] in a]}
        except Exception as e:
            log.warning("AI ask failed, using keywords: %s", e)
    stop = set("what did say about the and with was for from that this have has who when where how does said".split())
    kw = [w for w in re.findall(r"[a-z]+", question.lower()) if len(w) > 2 and w not in stop]
    hits = []
    for m in meetings:
        for s in re.findall(r"[^.!?\n]+[.!?]?", m["notes"]):
            c = sum(w in s.lower() for w in kw)
            if c: hits.append((c, s.strip(), m))
    hits.sort(key=lambda h: -h[0]); hits = hits[:3]
    return {"answer": "\n".join(f"• {s}" for _, s, _ in hits) or "Nothing found in past meetings.",
            "source": "rules", "sources": [{"title": m["title"], "date": m["date"]} for _, _, m in hits]}

# ---------- follow-up email ----------
def email(m, promises):
    mine = [q for q in promises if q["owner"] in ("Me", "We")]; theirs = [q for q in promises if q not in mine]
    L = lambda a: "\n".join(f"- {q['owner']}: {q['text']} ({q['due']})" for q in a) or "- none"
    out = (m.get("outcome") or {}).get("out", "")
    if client:
        try:
            return llm(SMART, 'Write a short, warm, professional follow-up email from me. Start with "Subject:". No preamble.',
                f"To: {', '.join(m['att'])}\nMeeting: {m['title']} ({m['date']})\nMy commitments:\n{L(mine)}\n"
                f"Waiting on them:\n{L(theirs)}\nOutcome: {out or 'n/a'}\nNotes: {m['notes']}", 700)
        except Exception as e:
            log.warning("AI email failed, using template: %s", e)
    return (f"Subject: Follow-up: {m['title']}\n\nHi {', '.join(m['att'])},\n\nThanks for your time on {m['date']}. Quick recap:\n\n"
            f"What I will do:\n{L(mine)}\n\nWhat we are waiting on:\n{L(theirs)}\n\nNext steps: {out or 'confirm dates for the items above'}.\n\nBest regards")
