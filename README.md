# TDS P1 — Data Analyst Telegram Bot

An LLM agent, wired to Telegram, that answers data-analysis questions (inline
data or public datasets like MOSPI/data.gov.in) and replies with exactly one
JSON object: `{"answer": ..., "log_url": "..."}`.

## How it works

```
Telegram message
      │
      ▼
  bot.py  ──────────────► agent.py (LLM tool-calling loop, via aipipe.org)
      │                       │
      │                       ├─ execute_python   (pandas/numpy sandbox)
      │                       ├─ fetch_url         (pull public datasets)
      │                       └─ submit_answer     (ends the loop)
      │
      ▼
  logger.py → appends run to logs/run.jsonl locally
             → pushes updated file to GitHub via Contents API
             → log_url = https://raw.githubusercontent.com/<repo>/<branch>/logs/run.jsonl
      │
      ▼
  Telegram reply: {"answer": <shaped exactly as asked>, "log_url": "..."}
```

- **Multi-turn**: the bot keeps a short rolling per-chat history and only
  answers the latest message, using earlier ones as context.
- **No fixed answer key**: the agent reads the JSON template embedded in each
  question and reasons its way to a real answer using code execution and
  live data fetches, not lookups.
- **Log hosting solves `log_url` for free**: every run is committed straight
  into `logs/run.jsonl` in *this same repo*, so the raw GitHub URL is always
  public and `wget`-able with zero extra infrastructure.

## 1. Local setup

```bash
git clone <your-fork-url>
cd tds-p1-telegram-bot
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# fill in .env: TELEGRAM_BOT_TOKEN, AIPIPE_TOKEN, GITHUB_TOKEN, GITHUB_REPO
```

Get a bot token from [@BotFather](https://t.me/BotFather) — username must end
in `bot`. Get your aipipe token from [aipipe.org/login](https://aipipe.org/login)
(sign in with your student email) — this is what powers the agent's "brain"
via an OpenAI-compatible endpoint. Create a fine-grained GitHub PAT scoped to
**Contents: read & write** on this repo only.

Sanity-check the agent loop before touching Telegram at all:

```bash
python3 test_agent_local.py
```

Then run the bot itself:

```bash
python3 bot.py
```

Message your bot on Telegram to confirm it replies with valid JSON.

## 2. Testing against the official grading pipeline

```bash
git clone https://github.com/Jivraj-18/tds-p1-t2-2026-telegram-bot
cd tds-p1-t2-2026-telegram-bot
# point it at your bot username per its own README, add sample questions
# to evals/questions.json, run its eval script
```

## 3. Deploy (so the bot stays reachable during grading)

Any always-on worker host works since the bot uses long polling (no inbound
webhook/port needed). Simplest options:

### Option A — Railway (fastest)
1. Push this repo to your own public GitHub.
2. railway.app → New Project → Deploy from GitHub repo.
3. Set the environment variables from `.env.example` in Railway's Variables tab.
4. Railway auto-detects the `Procfile` and runs `python3 bot.py` as a worker.
5. Confirm in the deploy logs: `Bot starting (long polling)...`

### Option B — Render
1. New → Background Worker → connect your GitHub repo.
2. Build command: `pip install -r requirements.txt`
3. Start command: `python3 bot.py`
4. Add the same environment variables.

### Option C — Any VPS / Docker host
```bash
docker build -t tds-bot .
docker run -d --restart unless-stopped --env-file .env tds-bot
```

**Important:** whichever host you pick, keep it running through the grading
window — the bot only answers messages while its process is alive (long
polling, no message queue/backlog guarantees beyond Telegram's own retry
window).

## 4. Files

| File | Purpose |
|---|---|
| `bot.py` | Telegram entrypoint, per-chat history, final JSON reply |
| `agent.py` | aipipe.org (OpenAI-compatible) tool-calling loop; enforces exact requested JSON shape and a time budget |
| `tools.py` | `execute_python`, `fetch_url`, `submit_answer` tool implementations |
| `logger.py` | Appends JSONL run log locally + pushes to GitHub for a public `log_url` |
| `test_agent_local.py` | Standalone smoke test, no Telegram required |
| `Dockerfile` / `Procfile` | Deployment |

## 5. Design choices worth knowing

- **Why commit logs to the repo instead of S3/GCS?** Zero extra
  infrastructure, zero extra secrets beyond a repo-scoped PAT you already
  need anyway, and `raw.githubusercontent.com` is permanently public and
  free. Swap `logger.py`'s backend for a bucket if you'd rather not commit
  logs on every message (e.g. under heavy grading traffic, GitHub API rate
  limits could bite — see below).
- **Rate limits**: GitHub's Contents API is ~5000 req/hr authenticated,
  fine for a grading run of dozens of questions. If you expect very high
  volume, batch log writes or switch to a real object store.
- **Sandboxing**: `execute_python` runs in a fresh subprocess per call with a
  timeout, not `exec()` in-process — a crash or infinite loop in generated
  code can't take down the bot.
- **Failure mode**: if the agent hits `MAX_AGENT_STEPS` without calling
  `submit_answer`, the bot still replies with valid JSON
  (`{"answer": null, "log_url": ...}`) rather than crashing or sending
  malformed output — the full trace is still in the log for review.
- **Exact-match grading**: grading compares your whole reply object exactly,
  so `bot.py` only ever emits precisely `{"answer": ..., "log_url": ...}` —
  never extra fields (no `confidence`, no `reasoning`, nothing else) — and
  the agent's system prompt drills into the model that `answer`'s *value*
  must match the requested shape exactly, including nesting.
- **Time budget**: `AGENT_TIME_BUDGET_SECONDS` (default 90s) is a soft
  wall-clock cutoff inside the agent loop — once it's crossed, the model is
  told to submit its best current answer immediately instead of continuing
  to investigate, so a slow multi-tool chain doesn't blow the grader's
  per-question `timeout_seconds`. Tune this down if your `evals/` runs show
  you're cutting it close.
- **Model choice**: `AIPIPE_MODEL` defaults to `gpt-5-mini` (matches the
  course's starter example). aipipe.org proxies several providers — check
  aipipe.org's docs/dashboard for the current list if you want to try a
  different model for cost or quality reasons.
