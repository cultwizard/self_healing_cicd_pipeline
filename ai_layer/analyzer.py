import json
import os
import httpx
from dotenv import load_dotenv

load_dotenv()

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)


async def analyze_failure(logs: str, git_diff: str) -> dict:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return {
            "root_cause": "GEMINI_API_KEY not configured — fallback diagnosis triggered.",
            "severity": "MEDIUM",
            "suggested_fix": "Inspect the failing test stack trace in the CI logs and fix the broken code.",
        }

    prompt = f"""You are a senior DevOps SRE. Analyze the failed CI/CD logs and git diff below.
Return ONLY valid JSON with these exact keys:
- "root_cause": concise string explaining why the deployment/test failed
- "severity": one of "LOW", "MEDIUM", "HIGH", "CRITICAL"
- "suggested_fix": markdown string containing the exact corrected code snippet

=== CI / RUNTIME LOGS ===
{logs[-4000:]}

=== GIT DIFF ===
{git_diff[:4000]}
"""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post(GEMINI_URL, headers=headers, json=payload)
            res.raise_for_status()
            raw_text = res.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            if raw_text.startswith("```"):
                raw_text = raw_text.strip("`").lstrip("json").strip()
            parsed = json.loads(raw_text)
            return {
                "root_cause": parsed.get("root_cause", "Unknown root cause"),
                "severity": parsed.get("severity", "HIGH"),
                "suggested_fix": parsed.get("suggested_fix", "Manual review required."),
            }
    except httpx.HTTPStatusError as exc:
        err_msg = f"HTTP {exc.response.status_code}: {exc.response.text[:200]}"
        print(f"[AI Layer] Diagnosis error: {err_msg}")
        return {
            "root_cause": f"LLM diagnosis failed ({err_msg})",
            "severity": "HIGH",
            "suggested_fix": "Review the raw CI logs manually.",
        }
    except Exception as exc:
        print(f"[AI Layer] Diagnosis error: {type(exc).__name__}")
        return {
            "root_cause": f"LLM diagnosis failed ({type(exc).__name__})",
            "severity": "HIGH",
            "suggested_fix": "Review the raw CI logs manually.",
        }