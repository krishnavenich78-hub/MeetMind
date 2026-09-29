import json, os, sqlite3
DB = os.getenv("MEETMIND_DB", "meetmind.db")

def conn():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON"); return c

def init():
    with conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS meetings(id INTEGER PRIMARY KEY, type TEXT, title TEXT, date TEXT,
          attendees TEXT, notes TEXT, extracted TEXT, src TEXT, outcome TEXT);
        CREATE TABLE IF NOT EXISTS promises(id INTEGER PRIMARY KEY, meeting_id INTEGER
          REFERENCES meetings(id) ON DELETE CASCADE, owner TEXT, text TEXT, due TEXT, done INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);""")

def get_state():
    with conn() as c:
        m = []
        for r in c.execute("SELECT * FROM meetings ORDER BY date, id"):
            d = {"id": r["id"], "type": r["type"], "title": r["title"], "date": r["date"],
                 "att": json.loads(r["attendees"] or "[]"), "notes": r["notes"] or ""}
            if r["extracted"]: d["x"] = json.loads(r["extracted"])
            if r["src"]: d["src"] = r["src"]
            if r["outcome"]: d["outcome"] = json.loads(r["outcome"])
            m.append(d)
        p = [{"id": r["id"], "mid": r["meeting_id"], "owner": r["owner"], "text": r["text"],
              "due": r["due"], "done": bool(r["done"])} for r in c.execute("SELECT * FROM promises")]
        n = c.execute("SELECT value FROM meta WHERE key='n'").fetchone()
        return {"m": m, "p": p, "n": int(n["value"]) if n else 10}

def put_state(s):
    with conn() as c:
        c.execute("DELETE FROM promises"); c.execute("DELETE FROM meetings")
        for m in s.get("m", []):
            c.execute("INSERT INTO meetings VALUES(?,?,?,?,?,?,?,?,?)", (m["id"], m.get("type"), m.get("title"),
                m.get("date"), json.dumps(m.get("att", [])), m.get("notes", ""),
                json.dumps(m["x"]) if m.get("x") else None, m.get("src"),
                json.dumps(m["outcome"]) if m.get("outcome") else None))
        for q in s.get("p", []):
            c.execute("INSERT INTO promises VALUES(?,?,?,?,?,?)", (q["id"], q["mid"], q.get("owner"),
                q.get("text"), q.get("due"), 1 if q.get("done") else 0))
        c.execute("INSERT OR REPLACE INTO meta VALUES('n',?)", (str(s.get("n", 10)),))
