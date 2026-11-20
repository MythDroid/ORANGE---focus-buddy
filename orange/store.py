"""Orange's long-term memory: one small SQLite database file on your laptop.

SQLite is a database that lives in a single file (data/orange.db). It is built
into Python, so there is nothing to install and nothing to keep running.

RULE: this is the ONLY file that talks to the database. Everything else calls the
small functions below (add_reminder, start_session, ...). If Orange ever moves to
a cloud database, only this file has to change.

Privacy: only text you ask Orange to keep goes in here (tasks, reminders, notes).
No audio and no photos are ever stored. `data/` is in .gitignore.

Times are stored as text like "2026-11-14T22:30:00" (your laptop's local time).
"""
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "orange.db"

_db = None
# Orange uses two threads (the window and the timer loop). The lock makes them
# take turns, so they never write to the database at the same moment.
_lock = threading.Lock()

_TABLES = """
CREATE TABLE IF NOT EXISTS sessions (        -- one row per study session
    id              INTEGER PRIMARY KEY,
    task            TEXT NOT NULL,           -- what you said you'd study
    planned_seconds INTEGER NOT NULL,
    started_at      TEXT NOT NULL,
    ends_at         TEXT NOT NULL,           -- moves later if you take a break
    ended_at        TEXT,                    -- empty while the session is running
    focused_seconds INTEGER DEFAULT 0,
    distractions    INTEGER DEFAULT 0,       -- used by the distraction watch (later step)
    status          TEXT NOT NULL DEFAULT 'active'   -- active / done / stopped
);
CREATE TABLE IF NOT EXISTS reminders (
    id         INTEGER PRIMARY KEY,
    text       TEXT NOT NULL,
    due_at     TEXT NOT NULL,
    done       INTEGER NOT NULL DEFAULT 0,   -- 0 = still waiting, 1 = already shown
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS notes (           -- things you asked Orange to remember
    id         INTEGER PRIMARY KEY,
    text       TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS phrases (         -- sentences YOU taught Orange
    trigger TEXT PRIMARY KEY,                -- what you say, in lower case
    kind    TEXT NOT NULL,                   -- 'means' = same as another sentence, 'reply' = just answer
    value   TEXT NOT NULL                    -- the other sentence, or the answer
);
CREATE TABLE IF NOT EXISTS allowed_titles (  -- pages you told Orange are "for study"
    title TEXT PRIMARY KEY
);
CREATE TABLE IF NOT EXISTS subjects (        -- named buckets you study under, e.g. "Machine Learning"
    id         INTEGER PRIMARY KEY,
    name       TEXT NOT NULL UNIQUE COLLATE NOCASE,   -- "dl" and "DL" count as the same subject
    created_at TEXT NOT NULL,
    archived   INTEGER NOT NULL DEFAULT 0     -- 1 = hidden from the menu, history kept
);
CREATE TABLE IF NOT EXISTS settings (        -- small choices, e.g. what Orange calls you
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def init(path=None):
    """Open (or create) the database. Call once at startup."""
    global _db
    path = Path(path) if path else DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    # check_same_thread=False lets both threads share this one connection (the lock keeps it safe).
    _db = sqlite3.connect(str(path), check_same_thread=False)
    _db.row_factory = sqlite3.Row   # Rows behave like dicts: row["task"]
    with _lock:
        _db.executescript(_TABLES)
        _db.commit()
    if get_setting("subjects_ready") is None:
        # First run with subjects: make one for every task you already studied, so the list
        # isn't empty and old study time shows up under the right name.
        _run("INSERT OR IGNORE INTO subjects (name, created_at) "
             "SELECT task, MIN(started_at) FROM sessions WHERE task != 'study' GROUP BY task COLLATE NOCASE")
        set_setting("subjects_ready", "1")


def _run(sql, args=()):
    """Run one command that changes data. Returns the new row's id (for INSERTs)."""
    if _db is None:
        raise RuntimeError("Call store.init() first.")
    with _lock:
        cur = _db.execute(sql, args)
        _db.commit()
        return cur.lastrowid


def _rows(sql, args=()):
    """Run one question (SELECT). Returns a list of dicts."""
    if _db is None:
        raise RuntimeError("Call store.init() first.")
    with _lock:
        return [dict(r) for r in _db.execute(sql, args).fetchall()]


def _t(when):
    """datetime -> text for the database."""
    return when.replace(microsecond=0).isoformat()


# ---------- study sessions ----------

def start_session(task, planned_seconds, started_at, ends_at):
    return _run("INSERT INTO sessions (task, planned_seconds, started_at, ends_at) VALUES (?, ?, ?, ?)",
                (task, int(planned_seconds), _t(started_at), _t(ends_at)))


def move_session_end(session_id, ends_at):
    """A break pushes the end time later."""
    _run("UPDATE sessions SET ends_at = ? WHERE id = ?", (_t(ends_at), session_id))


def finish_session(session_id, status, ended_at, focused_seconds):
    _run("UPDATE sessions SET status = ?, ended_at = ?, focused_seconds = ? WHERE id = ?",
         (status, _t(ended_at), int(focused_seconds), session_id))


def active_session():
    """The session that is still running (e.g. Orange was closed in the middle), or None."""
    rows = _rows("SELECT * FROM sessions WHERE status = 'active' ORDER BY id DESC LIMIT 1")
    if not rows:
        return None
    row = rows[0]
    row["started_at"] = datetime.fromisoformat(row["started_at"])
    row["ends_at"] = datetime.fromisoformat(row["ends_at"])
    return row


def focused_seconds_on(day):
    """Total focused time for sessions that started on this date."""
    rows = _rows("SELECT COALESCE(SUM(focused_seconds), 0) AS total FROM sessions "
                 "WHERE status != 'active' AND started_at LIKE ?", (day.isoformat() + "%",))
    return rows[0]["total"]


def sessions_on(day):
    """Every session that started on this date (for the summary), oldest first."""
    return _rows("SELECT id, task, focused_seconds, distractions, status FROM sessions "
                 "WHERE started_at LIKE ? ORDER BY id", (day.isoformat() + "%",))


# ---------- subjects ----------
# A session's `task` column holds its subject's name, so sessions and subjects are matched by
# name (ignoring capital letters).

def add_subject(name, now):
    _run("INSERT OR IGNORE INTO subjects (name, created_at) VALUES (?, ?)", (name.strip(), _t(now)))


def find_subject(name):
    """The subject with this name (any capitals), as a dict, or None."""
    rows = _rows("SELECT * FROM subjects WHERE name = ? COLLATE NOCASE", (name.strip(),))
    return rows[0] if rows else None


def list_subjects(archived=False):
    return [r["name"] for r in _rows("SELECT name FROM subjects WHERE archived = ? ORDER BY name COLLATE NOCASE",
                                     (1 if archived else 0,))]


def set_archived(name, archived):
    _run("UPDATE subjects SET archived = ? WHERE name = ? COLLATE NOCASE", (1 if archived else 0, name))


def delete_subject(name):
    """Removes the subject AND all its finished study sessions. Cannot be undone."""
    _run("DELETE FROM sessions WHERE task = ? COLLATE NOCASE AND status != 'active'", (name,))
    _run("DELETE FROM subjects WHERE name = ? COLLATE NOCASE", (name,))


def total_seconds_for(name):
    """All focus time ever spent on this subject (finished sessions)."""
    rows = _rows("SELECT COALESCE(SUM(focused_seconds), 0) AS total FROM sessions "
                 "WHERE task = ? COLLATE NOCASE AND status != 'active'", (name,))
    return rows[0]["total"]


# ---------- reminders ----------

def add_reminder(text, due_at, now):
    return _run("INSERT INTO reminders (text, due_at, created_at) VALUES (?, ?, ?)",
                (text, _t(due_at), _t(now)))


def due_reminders(now):
    """Reminders whose time has come (including ones missed while Orange was closed)."""
    return _rows("SELECT * FROM reminders WHERE done = 0 AND due_at <= ? ORDER BY due_at", (_t(now),))


def pending_reminders():
    rows = _rows("SELECT * FROM reminders WHERE done = 0 ORDER BY due_at")
    for r in rows:
        r["due_at"] = datetime.fromisoformat(r["due_at"])
    return rows


def finish_reminder(reminder_id):
    _run("UPDATE reminders SET done = 1 WHERE id = ?", (reminder_id,))


# ---------- notes ("remember that ...") ----------

def add_note(text, now):
    return _run("INSERT INTO notes (text, created_at) VALUES (?, ?)", (text, _t(now)))


def recent_notes(limit=5):
    return _rows("SELECT * FROM notes ORDER BY id DESC LIMIT ?", (limit,))


def delete_notes():
    _run("DELETE FROM notes")


# ---------- settings ----------

def get_setting(key, default=None):
    rows = _rows("SELECT value FROM settings WHERE key = ?", (key,))
    return rows[0]["value"] if rows else default


def set_setting(key, value):
    _run("INSERT INTO settings (key, value) VALUES (?, ?) "
         "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, str(value)))


# ---------- phrases you taught Orange ----------

def teach_phrase(trigger, kind, value):
    _run("INSERT INTO phrases (trigger, kind, value) VALUES (?, ?, ?) "
         "ON CONFLICT(trigger) DO UPDATE SET kind = excluded.kind, value = excluded.value",
         (trigger, kind, value))


def find_phrase(trigger):
    rows = _rows("SELECT * FROM phrases WHERE trigger = ?", (trigger,))
    return rows[0] if rows else None


def all_phrases():
    return _rows("SELECT * FROM phrases ORDER BY trigger")


def forget_phrase(trigger):
    """Returns True if there was such a phrase."""
    existed = find_phrase(trigger) is not None
    _run("DELETE FROM phrases WHERE trigger = ?", (trigger,))
    return existed


# ---------- distraction watch ----------

def add_distraction(session_id):
    _run("UPDATE sessions SET distractions = distractions + 1 WHERE id = ?", (session_id,))


def allow_title(title):
    _run("INSERT OR IGNORE INTO allowed_titles (title) VALUES (?)", (title,))


def is_allowed_title(title):
    return bool(_rows("SELECT 1 FROM allowed_titles WHERE title = ?", (title,)))
