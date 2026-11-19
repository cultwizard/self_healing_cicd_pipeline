# Self-Healing CI/CD Pipeline

An automated CI/CD self-healing system that detects failed deployments, performs an instant non-destructive rollback via the GitHub Git Data API, analyzes failure logs and commit diffs using Gemini, opens a GitHub diagnostic ticket with a suggested fix, and tracks incidents on a live dashboard.

## Project Structure
```text
self-healing-cicd/
├── .github/workflows/deploy.yml   # CI verification & failure webhook trigger
├── demo_app/                      # Target FastAPI service, tests & Dockerfile
├── orchestrator/                  # FastAPI control plane & GitHub API rollback/issues
├── ai_layer/                      # Gemini LLM log + diff root-cause analyzer
├── database/                      # SQLite incident store
├── dashboard/                     # Streamlit live incident monitoring UI
├── docs/architecture.md           # System architecture & state machine docs
├── requirements.txt
├── .env.example
└── .gitignore
```

## Local Setup (Windows PowerShell)
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```
Fill in `.env` with:
- `GITHUB_TOKEN`: Fine-grained PAT with **Contents (Read & Write)** and **Issues (Read & Write)** on this repository.
- `WEBHOOK_SECRET`: Shared secret string matching GitHub Actions Secrets.
- `GEMINI_API_KEY`: Google AI Studio API key.

## Run Locally
1. **Verify demo app tests:**
   ```powershell
   $env:PYTHONPATH="."; pytest demo_app/test_app.py
   ```
2. **Start Backend Orchestrator (Terminal 1):**
   ```powershell
   uvicorn orchestrator.main:app --port 8000 --reload
   ```
3. **Start Incident Dashboard (Terminal 2):**
   ```powershell
   streamlit run dashboard/app.py
   ```
4. **Expose Orchestrator for GitHub Actions (Terminal 3 or Render):**
   ```powershell
   ngrok http 8000
   ```
   Add `ORCHESTRATOR_URL` (your ngrok/Render HTTPS URL, no trailing slash) and `WEBHOOK_SECRET` to **GitHub Repo Settings -> Secrets and variables -> Actions**.

## Demo Test
1. Push the initial working baseline to `main` (CI turns green).
2. Break `demo_app/app.py` (e.g., change `a / b` to `a / 0`) and push to `main`.
3. Watch `deploy.yml` fail -> Orchestrator roll back `main` -> CI re-run green on the restored commit -> GitHub Issue open with the AI fix -> Dashboard update with full incident details.
