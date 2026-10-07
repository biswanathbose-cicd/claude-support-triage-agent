"""SQLite persistence: tickets, review queue and an append-only audit log (who/what/when for every decision)."""
from __future__ import annotations
import json, sqlite3, time

SCHEMA = """
CREATE TABLE IF NOT EXISTS tickets(id TEXT PRIMARY KEY, customer_email TEXT, subject TEXT, body TEXT, triage TEXT,
  route TEXT, reasons TEXT, status TEXT, draft_subject TEXT, draft_body TEXT, created REAL);
CREATE TABLE IF NOT EXISTS audit(n INTEGER PRIMARY KEY AUTOINCREMENT, ticket_id TEXT, actor TEXT, action TEXT, detail TEXT, ts REAL);
"""


class Store:
    def __init__(self, path: str = ":memory:"):
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    def audit(self, ticket_id: str, actor: str, action: str, detail: dict | None = None) -> None:
        self.db.execute("INSERT INTO audit(ticket_id,actor,action,detail,ts) VALUES(?,?,?,?,?)",
                        (ticket_id, actor, action, json.dumps(detail or {}), time.time()))
        self.db.commit()

    def save(self, ticket, triage, route, reasons, status, draft=None) -> None:
        self.db.execute("INSERT OR REPLACE INTO tickets VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                        (ticket.id, ticket.customer_email, ticket.subject, ticket.body, json.dumps(triage.__dict__ if triage else None),
                         route, json.dumps(list(reasons)), status, draft[0] if draft else None, draft[1] if draft else None, time.time()))
        self.db.commit()

    def get(self, ticket_id: str):
        return self.db.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,)).fetchone()

    def set_status(self, ticket_id: str, status: str, draft: tuple[str, str] | None = None) -> None:
        if draft:
            self.db.execute("UPDATE tickets SET status=?, draft_subject=?, draft_body=? WHERE id=?", (status, *draft, ticket_id))
        else:
            self.db.execute("UPDATE tickets SET status=? WHERE id=?", (status, ticket_id))
        self.db.commit()

    def pending(self) -> list[sqlite3.Row]:
        return self.db.execute("SELECT * FROM tickets WHERE status='pending_review' ORDER BY created").fetchall()

    def audit_trail(self, ticket_id: str) -> list[sqlite3.Row]:
        return self.db.execute("SELECT * FROM audit WHERE ticket_id=? ORDER BY n", (ticket_id,)).fetchall()
