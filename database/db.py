import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path("incidents.db")

ALLOWED_COLUMNS = {
    "repo",
    "commit_sha",
    "previous_good_sha",
    "rollback_commit_sha",
    "status",
    "rollback_status",
    "severity",
    "root_cause",
    "suggested_fix",
    "issue_url",
}


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS incidents (
                id TEXT PRIMARY KEY,
                repo TEXT,
                commit_sha TEXT,
                previous_good_sha TEXT,
                rollback_commit_sha TEXT,
                status TEXT,
                rollback_status TEXT,
                severity TEXT,
                root_cause TEXT,
                suggested_fix TEXT,
                issue_url TEXT,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )


def upsert_incident(data: dict) -> None:
    now = datetime.now(timezone.utc).isoformat()
    incident_id = data["id"]

    with sqlite3.connect(DB_PATH) as conn:
        existing = conn.execute(
            "SELECT id FROM incidents WHERE id = ?", (incident_id,)
        ).fetchone()

        if not existing:
            conn.execute(
                """
                INSERT INTO incidents (
                    id, repo, commit_sha, previous_good_sha, rollback_commit_sha,
                    status, rollback_status, severity, root_cause, suggested_fix,
                    issue_url, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    incident_id,
                    data.get("repo", ""),
                    data.get("commit_sha", ""),
                    data.get("previous_good_sha", ""),
                    data.get("rollback_commit_sha", ""),
                    data.get("status", "DETECTED"),
                    data.get("rollback_status", "PENDING"),
                    data.get("severity", "UNKNOWN"),
                    data.get("root_cause", ""),
                    data.get("suggested_fix", ""),
                    data.get("issue_url", ""),
                    now,
                    now,
                ),
            )
        else:
            fields = [k for k in data.keys() if k in ALLOWED_COLUMNS]
            if not fields:
                return
            assignments = ", ".join(f"{k} = ?" for k in fields) + ", updated_at = ?"
            values = [data[k] for k in fields] + [now, incident_id]
            conn.execute(f"UPDATE incidents SET {assignments} WHERE id = ?", values)


def get_all_incidents() -> list[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM incidents ORDER BY created_at DESC"
        ).fetchall()
        return [dict(row) for row in rows]


def get_incident_by_id(incident_id: str) -> dict | None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM incidents WHERE id = ?", (incident_id,)
        ).fetchone()
        return dict(row) if row else None
