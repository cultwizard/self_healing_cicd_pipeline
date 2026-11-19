# Self-Healing CI/CD Pipeline Architecture

## 1. Overview
This project implements an automated **Self-Healing CI/CD Pipeline** that detects failed deployments or verification tests, immediately rolls back the repository to the last known healthy commit, diagnoses the root cause using an LLM analyzing logs and git diffs, opens a GitHub diagnostic ticket with a suggested fix, and tracks every incident in real time on a dashboard.

## 2. Control Flow
```text
Push to main (buggy commit)
        │
        ▼
[GitHub Actions: deploy.yml]
  Runs pytest verification on demo_app
        │ (Failure & commit message does not contain [skip-heal])
        ▼
POST /webhook/failure  (X-Webhook-Secret + logs + commit SHA + previous SHA)
        │
        ▼
[Backend Orchestrator: FastAPI]
  1. Records incident in SQLite (DETECTED) & returns 202 Accepted
  2. Executes non-destructive Git tree rollback via GitHub Git Data API (ROLLING_BACK)
     └─► Pushes revert commit with [skip-heal] -> triggers green CI re-verification
  3. Fetches exact git diff of the failing commit from GitHub API (DIAGNOSING)
  4. Sends logs + git diff to AI Diagnosis Layer (Gemini 2.5 Flash)
  5. Opens a GitHub Issue with rollback details, root cause & suggested fix (TICKET_OPENED)
        │
        ▼
[Streamlit Dashboard]
  Polls GET /incidents to display live incident telemetry and ticket links
```

## 3. Incident Lifecycle State Machine
`DETECTED` -> `ROLLING_BACK` -> `DIAGNOSING` -> `TICKET_OPENED` (or `DIAGNOSED`)

## 4. Non-Destructive Rollback Mechanism
Instead of force-pushing or executing local `git` CLI commands, the orchestrator uses four GitHub Git Data API calls:
1. Read `tree.sha` from `previous_good_sha`.
2. Read the current `HEAD` commit SHA of `main`.
3. Create a new commit pointing to the healthy `tree.sha` with `HEAD` as parent and `[skip-heal]` in the message.
4. Fast-forward `refs/heads/main` (`force: false`).

This preserves full Git history, respects branch protection rules, and automatically triggers CI verification on the restored snapshot.

## 5. Team Ownership
- **Backend Orchestrator (`orchestrator/`)**: Saatyak Srivastav — FastAPI control plane, webhook security, GitHub Git Data API auto-rollback, diff retrieval, issue creation, and incident API.
- **Pipeline & Infrastructure (`demo_app/`, `.github/workflows/`)**: Sachin Sood — Target microservice, Dockerfile, automated CI/CD verification, and failure detection webhook trigger.
- **AI/Diagnosis Layer (`ai_layer/`)**: Ram Singh — LLM prompt engineering and structured JSON log/diff root cause analysis.
- **Database, Dashboard & Docs (`database/`, `dashboard/`, `docs/`)**: Pratik Kumar — SQLite incident persistence, Streamlit dashboard, and system documentation.
