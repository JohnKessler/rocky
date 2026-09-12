"""What Rocky remembers between conversations.

Deliberately small and legible: a table of short facts Rocky chose to keep,
and a rolling transcript. It is a SQLite file you can open and read, which
matters for something that lives on your desk and remembers things about you -
you should be able to see exactly what it has, and delete any of it.
"""

from __future__ import annotations

import logging
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS facts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    text        TEXT NOT NULL,
    category    TEXT NOT NULL DEFAULT 'general',
    created_at  REAL NOT NULL,
    last_used   REAL NOT NULL DEFAULT 0,
    uses        INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS facts_category ON facts(category);

CREATE TABLE IF NOT EXISTS turns (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    role        TEXT NOT NULL,
    text        TEXT NOT NULL,
    at          REAL NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS facts_fts
    USING fts5(text, content='facts', content_rowid='id');

CREATE TRIGGER IF NOT EXISTS facts_ai AFTER INSERT ON facts BEGIN
    INSERT INTO facts_fts(rowid, text) VALUES (new.id, new.text);
END;
CREATE TRIGGER IF NOT EXISTS facts_ad AFTER DELETE ON facts BEGIN
    INSERT INTO facts_fts(facts_fts, rowid, text) VALUES('delete', old.id, old.text);
END;
"""


@dataclass(frozen=True, slots=True)
class Fact:
    id: int
    text: str
    category: str
    created_at: float
    uses: int = 0

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "text": self.text,
            "category": self.category,
            "created_at": self.created_at,
            "uses": self.uses,
        }


class Memory:
    """Rocky's long-term memory."""

    def __init__(self, path: str, max_facts: int = 500) -> None:
        self.path = Path(path)
        self.max_facts = max_facts
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(self.path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.executescript(SCHEMA)
        self._db.commit()
        self._fts = self._probe_fts()

    def _probe_fts(self) -> bool:
        try:
            self._db.execute("SELECT rowid FROM facts_fts LIMIT 1").fetchone()
            return True
        except sqlite3.Error:
            log.info("SQLite built without FTS5; memory search falls back to LIKE")
            return False

    # -- facts --------------------------------------------------------------

    def remember(self, text: str, category: str = "general") -> Fact | None:
        text = " ".join(text.split())[:400]
        if not text:
            return None

        existing = self._db.execute(
            "SELECT * FROM facts WHERE lower(text) = lower(?)", (text,)
        ).fetchone()
        if existing:
            return _row_to_fact(existing)

        now = time.time()
        cur = self._db.execute(
            "INSERT INTO facts (text, category, created_at) VALUES (?, ?, ?)",
            (text, category, now),
        )
        self._db.commit()
        self._prune()
        return Fact(id=int(cur.lastrowid), text=text, category=category, created_at=now)

    def recall(self, query: str = "", limit: int = 8) -> list[Fact]:
        """Facts matching ``query``, or the most useful ones if empty."""
        query = query.strip()
        if not query:
            rows = self._db.execute(
                "SELECT * FROM facts ORDER BY uses DESC, created_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [_row_to_fact(r) for r in rows]

        rows: list[sqlite3.Row] = []
        if self._fts:
            try:
                rows = self._db.execute(
                    "SELECT f.* FROM facts_fts JOIN facts f ON f.id = facts_fts.rowid "
                    "WHERE facts_fts MATCH ? ORDER BY rank LIMIT ?",
                    (_fts_query(query), limit),
                ).fetchall()
            except sqlite3.Error:
                rows = []
        if not rows:
            rows = self._db.execute(
                "SELECT * FROM facts WHERE text LIKE ? ORDER BY uses DESC LIMIT ?",
                (f"%{query}%", limit),
            ).fetchall()

        facts = [_row_to_fact(r) for r in rows]
        if facts:
            self._db.executemany(
                "UPDATE facts SET uses = uses + 1, last_used = ? WHERE id = ?",
                [(time.time(), f.id) for f in facts],
            )
            self._db.commit()
        return facts

    def forget(self, fact_id: int) -> bool:
        cur = self._db.execute("DELETE FROM facts WHERE id = ?", (fact_id,))
        self._db.commit()
        return cur.rowcount > 0

    def all_facts(self, limit: int = 200) -> list[Fact]:
        rows = self._db.execute(
            "SELECT * FROM facts ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [_row_to_fact(r) for r in rows]

    def _prune(self) -> None:
        """Drop the least useful facts once over the cap.

        Ordered by uses then age, so something Rocky keeps coming back to
        survives even if it is old.
        """
        count = self._db.execute("SELECT COUNT(*) AS n FROM facts").fetchone()["n"]
        if count <= self.max_facts:
            return
        self._db.execute(
            "DELETE FROM facts WHERE id IN ("
            "  SELECT id FROM facts ORDER BY uses ASC, last_used ASC, created_at ASC LIMIT ?"
            ")",
            (count - self.max_facts,),
        )
        self._db.commit()

    # -- transcript ---------------------------------------------------------

    def log_turn(self, role: str, text: str) -> None:
        self._db.execute(
            "INSERT INTO turns (role, text, at) VALUES (?, ?, ?)",
            (role, text[:2000], time.time()),
        )
        self._db.commit()

    def recent_turns(self, limit: int = 40) -> list[dict]:
        rows = self._db.execute(
            "SELECT role, text, at FROM turns ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in reversed(rows)]

    def stats(self) -> dict:
        facts = self._db.execute("SELECT COUNT(*) AS n FROM facts").fetchone()["n"]
        turns = self._db.execute("SELECT COUNT(*) AS n FROM turns").fetchone()["n"]
        return {"facts": facts, "turns": turns, "path": str(self.path), "fts": self._fts}

    def close(self) -> None:
        self._db.close()


def _row_to_fact(row: sqlite3.Row) -> Fact:
    return Fact(
        id=int(row["id"]), text=row["text"], category=row["category"],
        created_at=float(row["created_at"]), uses=int(row["uses"]),
    )


def _fts_query(query: str) -> str:
    """Make user text safe for FTS5, which treats plenty of punctuation as
    operators and raises on a stray quote."""
    words = [w for w in "".join(c if c.isalnum() else " " for c in query).split() if w]
    return " OR ".join(words) if words else '""'
