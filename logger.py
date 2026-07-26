"""
Appends one JSON line per run to logs/run.jsonl, and pushes the updated
file to GitHub via the Contents API so it's reachable at:

  https://raw.githubusercontent.com/<owner>/<repo>/<branch>/<path>

which is a plain public wget-able URL - no auth, no expiry, exactly what
the grader needs.

Falls back to local-file-only logging (with a clear warning) if GitHub
credentials aren't configured, so the bot still runs during local testing.
"""
import base64
import json
import os
import time

import requests

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")  # "owner/repo"
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main")
LOG_FILE_PATH = os.getenv("LOG_FILE_PATH", "logs/run.jsonl")
LOCAL_LOG_PATH = os.path.join(os.path.dirname(__file__), "logs", "run.jsonl")

API_BASE = "https://api.github.com"


def public_log_url() -> str:
    if GITHUB_REPO:
        return (
            f"https://raw.githubusercontent.com/{GITHUB_REPO}/"
            f"{GITHUB_BRANCH}/{LOG_FILE_PATH}"
        )
    return "file://" + LOCAL_LOG_PATH  # local-only fallback, won't be public


def _append_local(line: str) -> None:
    os.makedirs(os.path.dirname(LOCAL_LOG_PATH), exist_ok=True)
    with open(LOCAL_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _github_headers() -> dict:
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _push_to_github(new_line: str, max_retries: int = 3) -> None:
    """
    Fetch current file (with its sha), append the new line, PUT it back.
    Retries on 409 (concurrent update) by re-fetching.
    """
    url = f"{API_BASE}/repos/{GITHUB_REPO}/contents/{LOG_FILE_PATH}"

    for attempt in range(max_retries):
        get_resp = requests.get(
            url, headers=_github_headers(), params={"ref": GITHUB_BRANCH}, timeout=15
        )
        if get_resp.status_code == 200:
            data = get_resp.json()
            current = base64.b64decode(data["content"]).decode("utf-8")
            sha = data["sha"]
        elif get_resp.status_code == 404:
            current = ""
            sha = None
        else:
            get_resp.raise_for_status()
            return

        updated = current + (new_line + "\n")
        payload = {
            "message": f"log: run @ {int(time.time())}",
            "content": base64.b64encode(updated.encode("utf-8")).decode("utf-8"),
            "branch": GITHUB_BRANCH,
        }
        if sha:
            payload["sha"] = sha

        put_resp = requests.put(
            url, headers=_github_headers(), json=payload, timeout=15
        )
        if put_resp.status_code in (200, 201):
            return
        if put_resp.status_code == 409:
            time.sleep(0.5 * (attempt + 1))
            continue
        put_resp.raise_for_status()

    raise RuntimeError("Failed to push log to GitHub after retries (409 conflicts)")


def log_run(record: dict) -> str:
    """
    record should already contain: timestamp, chat_id, question, steps,
    final_answer, log_url. Appends it as one JSON line locally and, if
    configured, to the GitHub-hosted copy. Returns the public log_url.
    """
    line = json.dumps(record, ensure_ascii=False, default=str)
    _append_local(line)

    if GITHUB_TOKEN and GITHUB_REPO:
        try:
            _push_to_github(line)
        except Exception as e:  # noqa: BLE001
            # Never let logging failures break the bot's reply to the user.
            print(f"[logger] WARNING: failed to push log to GitHub: {e}")

    return public_log_url()
