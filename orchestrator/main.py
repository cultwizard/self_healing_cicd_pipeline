import os
import uuid
from contextlib import asynccontextmanager

import httpx
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException
from pydantic import BaseModel

load_dotenv()

from ai_layer.analyzer import analyze_failure
from database.db import get_all_incidents, get_incident_by_id, init_db, upsert_incident
from orchestrator.github_service import (
    create_fix_issue,
    execute_rollback,
    fetch_commit_diff,
)

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "self-heal-secret-2026")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Self-Healing CI/CD Orchestrator", lifespan=lifespan)


class FailurePayload(BaseModel):
    repo: str
    branch: str = "main"
    commit_sha: str
    previous_good_sha: str
    failure_stage: str = "pytest_verify"
    runtime_logs: str


async def execute_healing_pipeline(incident_id: str, payload: FailurePayload) -> None:
    print(f"[Orchestrator] Starting self-healing pipeline for {incident_id} ({payload.commit_sha[:7]})")
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Execute Auto-Rollback Directly via GitHub Git Data API
        upsert_incident({"id": incident_id, "status": "ROLLING_BACK"})
        rolled_back, rollback_sha = await execute_rollback(
            client,
            payload.repo,
            payload.branch,
            payload.commit_sha,
            payload.previous_good_sha,
        )
        upsert_incident(
            {
                "id": incident_id,
                "status": "DIAGNOSING",
                "rollback_status": "SUCCESS" if rolled_back else "FAILED",
                "rollback_commit_sha": rollback_sha,
            }
        )

        # 2. Fetch Commit Diff & Run AI Diagnosis Layer
        git_diff = await fetch_commit_diff(client, payload.repo, payload.commit_sha)
        diagnosis = await analyze_failure(payload.runtime_logs, git_diff)

        # 3. Open GitHub Diagnostic Ticket with Suggested Fix
        root_cause = diagnosis.get("root_cause", "Deployment verification failed")
        severity = diagnosis.get("severity", "HIGH")
        suggested_fix = diagnosis.get("suggested_fix", "Manual investigation required.")

        title = f"[Self-Heal] Failed deploy {payload.commit_sha[:7]}: {root_cause[:55]}"
        rollback_line = (
            f"Completed (`{rollback_sha[:7]}`)"
            if rolled_back
            else "Failed (check orchestrator logs & GITHUB_TOKEN permissions)"
        )
        body = (
            f"### Automated Rollback\n"
            f"- **Status:** {rollback_line}\n"
            f"- **Failed Stage:** `{payload.failure_stage}`\n"
            f"- **Bad Commit:** `{payload.commit_sha}`\n"
            f"- **Restored Snapshot From:** `{payload.previous_good_sha}`\n\n"
            f"### AI Root Cause Analysis (`{severity}`)\n"
            f"{root_cause}\n\n"
            f"### Suggested Fix\n"
            f"{suggested_fix}\n"
        )
        issue_url = await create_fix_issue(client, payload.repo, title, body)

        # 4. Finalize Incident State
        upsert_incident(
            {
                "id": incident_id,
                "status": "TICKET_OPENED" if issue_url else "DIAGNOSED",
                "severity": severity,
                "root_cause": root_cause,
                "suggested_fix": suggested_fix,
                "issue_url": issue_url,
            }
        )
        print(f"[Orchestrator] Completed pipeline for {incident_id} -> {issue_url or 'no issue'}")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/incidents")
def list_incidents():
    return get_all_incidents()


@app.get("/incidents/{incident_id}")
def get_incident(incident_id: str):
    incident = get_incident_by_id(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@app.post("/webhook/failure", status_code=202)
async def handle_failure(
    payload: FailurePayload,
    background_tasks: BackgroundTasks,
    x_webhook_secret: str = Header(default=""),
):
    if x_webhook_secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    incident_id = f"inc_{uuid.uuid4().hex[:8]}"
    upsert_incident(
        {
            "id": incident_id,
            "repo": payload.repo,
            "commit_sha": payload.commit_sha,
            "previous_good_sha": payload.previous_good_sha,
            "status": "DETECTED",
        }
    )
    background_tasks.add_task(execute_healing_pipeline, incident_id, payload)
    return {"incident_id": incident_id, "status": "accepted"}
