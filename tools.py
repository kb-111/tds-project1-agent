"""
Tools available to the agent:
  - execute_python: run pandas/numpy analysis code in an isolated subprocess
  - fetch_url: download a public URL (dataset page, CSV, HTML table, API JSON)

Both tools return plain strings (truncated) so they're cheap to feed back
into the LLM's context window.
"""
import io
import json
import os
import subprocess
import sys
import tempfile
import textwrap

import requests

MAX_OUTPUT_CHARS = 6000
DEFAULT_TIMEOUT = int(os.getenv("CODE_EXEC_TIMEOUT", "30"))


def _truncate(text: str, limit: int = MAX_OUTPUT_CHARS) -> str:
    if text is None:
        return ""
    if len(text) <= limit:
        return text
    head = text[: limit // 2]
    tail = text[-limit // 2 :]
    return f"{head}\n...[TRUNCATED {len(text) - limit} chars]...\n{tail}"


def execute_python(code: str, timeout: int = DEFAULT_TIMEOUT) -> dict:
    """
    Execute arbitrary python in a fresh subprocess.
    pandas / numpy / requests / bs4 / json are pre-imported for convenience.
    The script must `print(...)` whatever it wants the agent to see -
    stdout is what gets returned. Any files it wants to keep should be
    written under /tmp (they don't persist across calls; re-fetch data
    each time or cache it inside a single code block).
    """
    preamble = textwrap.dedent(
        """
        import pandas as pd
        import numpy as np
        import requests
        import json
        import io
        import re
        from bs4 import BeautifulSoup
        pd.set_option("display.max_columns", 50)
        pd.set_option("display.width", 200)
        """
    )
    full_code = preamble + "\n" + code

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, dir="/tmp"
    ) as f:
        f.write(full_code)
        script_path = f.name

    try:
        proc = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "stdout": _truncate(proc.stdout),
            "stderr": _truncate(proc.stderr),
            "returncode": proc.returncode,
        }
    except subprocess.TimeoutExpired:
        return {
            "stdout": "",
            "stderr": f"TIMEOUT: execution exceeded {timeout}s",
            "returncode": -1,
        }
    finally:
        try:
            os.remove(script_path)
        except OSError:
            pass


def fetch_url(url: str, max_chars: int = MAX_OUTPUT_CHARS) -> dict:
    """
    Fetch a URL. Returns raw text (CSV/JSON/HTML) truncated to max_chars.
    Use this for MOSPI pages, data.gov.in datasets, CSV/XLSX download links,
    or any public reference the question points at.
    """
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            )
        }
        resp = requests.get(url, headers=headers, timeout=20)
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "")
        if "application/json" in content_type:
            body = json.dumps(resp.json())[:max_chars]
        else:
            body = resp.text[:max_chars]
        return {
            "status_code": resp.status_code,
            "content_type": content_type,
            "body": _truncate(body, max_chars),
        }
    except Exception as e:  # noqa: BLE001
        return {"status_code": None, "content_type": None, "body": f"ERROR: {e}"}


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "execute_python",
            "description": (
                "Run Python code to analyze data (pandas/numpy/requests/bs4 "
                "pre-imported). Use this for ALL numerical/data-analysis work: "
                "parsing inline CSV/JSON given in the question, computing "
                "statistics, filtering, aggregating, etc. Always print() the "
                "result you need to see - stdout is returned to you."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Python source to run."}
                },
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_url",
            "description": (
                "Download a public URL (MOSPI / data.gov.in / any public dataset "
                "or webpage) and return its raw text/CSV/JSON/HTML, truncated. "
                "Use this to locate and pull real public data referenced by the "
                "question before analyzing it with execute_python."
            ),
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit_answer",
            "description": (
                "Call this EXACTLY ONCE when you have the final answer, and "
                "nothing else. `answer_json` must be a JSON-encoded STRING of "
                "the value in precisely the shape the question asked for "
                "(matching its example JSON template) - e.g. if it asked for "
                '{"answer": {"state": "..."}, "log_url": "..."}, pass the '
                'string \'{"state": "Assam"}\' as answer_json - not a bare '
                "description. Never include extra keys beyond exactly what "
                "the question's template shows; grading is exact-match on "
                "the whole reply object."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "answer_json": {
                        "type": "string",
                        "description": (
                            "A JSON-encoded string of the final answer value, "
                            "matching the requested shape exactly (no extra keys)."
                        ),
                    }
                },
                "required": ["answer_json"],
            },
        },
    },
]
