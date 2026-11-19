import os
import httpx
from dotenv import load_dotenv

load_dotenv()


def _get_headers() -> dict[str, str]:
    token = os.getenv("GITHUB_TOKEN", "").strip()
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


async def fetch_commit_diff(client: httpx.AsyncClient, repo: str, commit_sha: str) -> str:
    url = f"https://api.github.com/repos/{repo}/commits/{commit_sha}"
    headers = {**_get_headers(), "Accept": "application/vnd.github.v3.diff"}
    res = await client.get(url, headers=headers)
    if res.status_code == 200:
        return res.text[:5000]
    print(f"[GitHub] Failed to fetch diff ({res.status_code}): {res.text[:200]}")
    return "Diff unavailable."


async def execute_rollback(
    client: httpx.AsyncClient,
    repo: str,
    branch: str,
    bad_sha: str,
    target_sha: str,
) -> tuple[bool, str]:
    """
    Rolls back `branch` to the exact file tree snapshot of `target_sha` by creating
    a new non-destructive revert commit via GitHub's Git Data API.
    Returns (success, rollback_commit_sha).
    """
    if not target_sha or target_sha == bad_sha:
        print("[GitHub] Invalid target_sha for rollback.")
        return False, ""

    base = f"https://api.github.com/repos/{repo}/git"
    headers = _get_headers()

    # 1. Fetch healthy file tree SHA from previous_good_sha
    good_commit_res = await client.get(f"{base}/commits/{target_sha}", headers=headers)
    if good_commit_res.status_code != 200:
        print(f"[GitHub] Failed reading good commit ({good_commit_res.status_code}): {good_commit_res.text[:200]}")
        return False, ""
    good_tree_sha = good_commit_res.json()["tree"]["sha"]

    # 2. Fetch current HEAD SHA of the branch
    ref_res = await client.get(f"{base}/ref/heads/{branch}", headers=headers)
    if ref_res.status_code != 200:
        print(f"[GitHub] Failed reading branch ref ({ref_res.status_code}): {ref_res.text[:200]}")
        return False, ""
    current_head_sha = ref_res.json()["object"]["sha"]

    # 3. Create new rollback commit pointing to the healthy tree
    commit_res = await client.post(
        f"{base}/commits",
        headers=headers,
        json={
            "message": f"revert: auto-rollback {bad_sha[:7]} to {target_sha[:7]} [skip-heal]",
            "tree": good_tree_sha,
            "parents": [current_head_sha],
        },
    )
    if commit_res.status_code != 201:
        print(f"[GitHub] Failed creating rollback commit ({commit_res.status_code}): {commit_res.text[:200]}")
        return False, ""
    rollback_commit_sha = commit_res.json()["sha"]

    # 4. Fast-forward the branch ref to the new rollback commit
    update_ref_res = await client.patch(
        f"{base}/refs/heads/{branch}",
        headers=headers,
        json={"sha": rollback_commit_sha, "force": False},
    )
    if update_ref_res.status_code != 200:
        print(f"[GitHub] Failed updating branch ref ({update_ref_res.status_code}): {update_ref_res.text[:200]}")
        return False, ""

    print(f"[GitHub] Rolled back {repo}@{branch} -> {rollback_commit_sha[:7]}")
    return True, rollback_commit_sha


async def create_fix_issue(
    client: httpx.AsyncClient, repo: str, title: str, body: str
) -> str:
    url = f"https://api.github.com/repos/{repo}/issues"
    res = await client.post(
        url,
        headers=_get_headers(),
        json={"title": title, "body": body},
    )
    if res.status_code == 201:
        issue_url = res.json().get("html_url", "")
        print(f"[GitHub] Created issue: {issue_url}")
        return issue_url
    print(f"[GitHub] Failed creating issue ({res.status_code}): {res.text[:200]}")
    return ""
