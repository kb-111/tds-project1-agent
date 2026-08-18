# Data Analyst Telegram Bot

An LLM-powered Telegram bot that answers data-analysis questions using inline data or publicly available datasets. The bot can fetch data from public URLs, execute Python-based analysis, and return answers in an exact JSON format.

## Overview

The bot combines Telegram, an LLM agent, Python-based data analysis, and GitHub-hosted execution logs into a single automated workflow.

```text
Telegram Message
       │
       ▼
    bot.py
       │
       ▼
   agent.py
       │
       ├── execute_python
       │       └── pandas / NumPy analysis
       │
       ├── fetch_url
       │       └── Public dataset retrieval
       │
       └── submit_answer
       │
       ▼
   logger.py
       │
       ├── Local JSONL logging
       └── GitHub Contents API
       │
       ▼
Telegram JSON Response
```

The bot responds with exactly one JSON object:

```json
{
  "answer": "...",
  "log_url": "..."
}
```

## Key Features

* Telegram-based conversational interface
* LLM-powered data analysis
* Multi-turn conversation support
* Python execution for numerical and statistical analysis
* Pandas and NumPy based data processing
* Retrieval of public datasets through URLs
* Automatic execution logging
* Public GitHub-hosted JSONL logs
* Exact JSON response formatting
* Configurable agent time and step limits
* Subprocess-based Python execution with timeout protection
* Docker and worker-based deployment support

## How It Works

### 1. User sends a question

A user sends a data-analysis question to the Telegram bot.

The question may contain:

* Inline data
* A public dataset URL
* Statistical questions
* Aggregation tasks
* Filtering and transformation requirements
* A specific JSON-compatible answer format

### 2. Agent processes the question

The LLM agent determines how to solve the problem and can use specialized tools.

Available tools include:

```text
execute_python
fetch_url
submit_answer
```

### 3. Data analysis

The `execute_python` tool allows the agent to perform analysis using Python libraries such as:

* Pandas
* NumPy

This allows the agent to calculate statistics, filter datasets, perform aggregations, transform data, and derive answers instead of relying on hard-coded responses.

### 4. Public data retrieval

The `fetch_url` tool allows the agent to retrieve publicly accessible datasets and other resources required to answer a question.

### 5. Answer submission

Once the analysis is complete, the agent uses `submit_answer` to provide the final result.

The response is then formatted into the required JSON structure.

### 6. Logging

Each execution is recorded in JSONL format.

The log is:

1. Written locally.
2. Updated in the repository through the GitHub Contents API.
3. Exposed through a public raw GitHub URL.

This provides a simple way to inspect previous executions without requiring additional cloud storage infrastructure.

## Multi-Turn Conversations

The bot maintains a short rolling history for each Telegram chat.

This allows users to ask follow-up questions while giving the agent context from earlier messages.

For example:

```text
User: Analyze this dataset.
Bot: ...

User: What is the average value?
Bot: ...

User: Now calculate it only for 2025.
Bot: ...
```

The latest question remains the primary task while relevant previous messages provide context.

## Exact JSON Response

The bot is designed to return only:

```json
{
  "answer": "<result>",
  "log_url": "<public-log-url>"
}
```

No additional fields are added to the final response.

This makes the output easy for automated systems to parse.

## Safety and Reliability

### Isolated Python Execution

Generated Python code is executed in a separate subprocess rather than directly inside the main bot process.

Each execution can have a timeout, preventing an accidental infinite loop or long-running computation from blocking the entire bot.

### Agent Step Limit

The agent has a configurable maximum number of tool-calling steps.

If the agent cannot complete the analysis within the configured limit, it can still produce a valid JSON response rather than crashing.

### Time Budget

The agent loop supports a configurable time budget.

Example:

```env
AGENT_TIME_BUDGET_SECONDS=90
```

When the time budget is reached, the agent is instructed to provide its best available answer instead of continuing indefinitely.

## Logging

Execution logs are stored in JSONL format.

Example:

```json
{"timestamp":"2026-08-18T10:30:00Z","question":"...","answer":"..."}
```

The logger maintains the local log and pushes the updated file to GitHub.

The resulting raw GitHub URL can then be returned as:

```json
{
  "answer": "...",
  "log_url": "https://raw.githubusercontent.com/..."
}
```

## Project Structure

```text
data-analyst-telegram-bot/
│
├── bot.py
├── agent.py
├── tools.py
├── logger.py
├── test_agent_local.py
├── requirements.txt
├── .env.example
├── Dockerfile
├── Procfile
├── logs/
│   └── run.jsonl
└── README.md
```

### File Responsibilities

| File                  | Purpose                                                                |
| --------------------- | ---------------------------------------------------------------------- |
| `bot.py`              | Telegram bot entrypoint, conversation history, and final JSON response |
| `agent.py`            | LLM agent loop, tool calling, response formatting, and time management |
| `tools.py`            | Python execution, URL fetching, and answer submission tools            |
| `logger.py`           | Local JSONL logging and GitHub log publishing                          |
| `test_agent_local.py` | Tests the agent without requiring Telegram                             |
| `Dockerfile`          | Container configuration                                                |
| `Procfile`            | Worker deployment configuration                                        |
| `requirements.txt`    | Python dependencies                                                    |
| `.env.example`        | Environment variable template                                          |

## Environment Variables

Create a `.env` file based on `.env.example`.

Example:

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
AIPIPE_TOKEN=your_aipipe_token
GITHUB_TOKEN=your_github_token
GITHUB_REPO=your_username/your_repository

AIPIPE_MODEL=gpt-5-mini
AGENT_TIME_BUDGET_SECONDS=90
```

### Required Credentials

#### Telegram

Create a Telegram bot using BotFather and obtain the bot token.

#### LLM Provider

Configure the token required by the OpenAI-compatible LLM endpoint used by the application.

#### GitHub

Create a repository-scoped Personal Access Token with the permissions required to update the log file.

Do not commit `.env` or any secret credentials to the repository.

## Local Installation

Clone the repository:

```bash
git clone <your-repository-url>
cd data-analyst-telegram-bot
```

Create a virtual environment:

```bash
python3 -m venv .venv
```

Activate it:

### Linux / macOS

```bash
source .venv/bin/activate
```

### Windows

```bash
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create the environment file:

```bash
cp .env.example .env
```

Then configure the required environment variables.

## Test the Agent Locally

Before starting Telegram integration, test the agent independently:

```bash
python3 test_agent_local.py
```

This allows the analysis and tool-calling pipeline to be tested without requiring a Telegram message.

## Run the Bot

Start the Telegram bot:

```bash
python3 bot.py
```

The application uses Telegram long polling, so it does not require an incoming webhook or public HTTP endpoint.

Once the bot is running, send a data-analysis question through Telegram.

## Deployment

The bot can run on any service that supports a persistent worker process.

### Railway

1. Push the repository to GitHub.
2. Create a new project from the GitHub repository.
3. Configure the required environment variables.
4. Deploy the worker.
5. Verify that the bot process starts successfully.

Example worker command:

```bash
python3 bot.py
```

### Render

Create a Background Worker with:

```text
Build Command:
pip install -r requirements.txt
```

and:

```text
Start Command:
python3 bot.py
```

Configure the required environment variables in the service settings.

### Docker

Build the container:

```bash
docker build -t data-analyst-telegram-bot .
```

Run it:

```bash
docker run -d \
  --restart unless-stopped \
  --env-file .env \
  data-analyst-telegram-bot
```

## Design Decisions

### Why GitHub for Logs?

GitHub provides a simple and inexpensive way to host execution logs publicly.

Advantages:

* No additional object-storage infrastructure
* Simple API integration
* Public raw file URLs
* Easy inspection of execution history
* Repository-based versioning

For high-volume applications, a dedicated object store or database would be more appropriate.

### Why a Subprocess for Python Execution?

Running generated Python in a separate subprocess helps isolate failures from the main Telegram process.

A timeout can also prevent a long-running or infinite computation from blocking the bot.

### Why Tool Calling?

Instead of relying entirely on the language model's internal reasoning, the agent can delegate concrete operations to tools.

For example:

```text
Question
   ↓
LLM decides what is needed
   ↓
fetch_url
   ↓
execute_python
   ↓
analyze data
   ↓
submit_answer
```

This is particularly useful for numerical questions where deterministic Python calculations are more reliable than estimating an answer directly from the language model.

## Potential Improvements

Future versions could include:

* Redis-based conversation state
* Persistent conversation storage
* Authentication and authorization
* More secure code execution using containers
* Dataset caching
* Parallel tool execution
* Structured tool outputs
* Database-backed logging
* Object-storage based logs
* Automatic retry mechanisms
* Monitoring and metrics
* Rate limiting
* Unit and integration tests
* CI/CD pipeline
* Web-based dashboard for execution logs

## Security Considerations

Never commit the following to GitHub:

```text
.env
Telegram bot tokens
LLM API tokens
GitHub Personal Access Tokens
Private datasets
Other credentials
```

Use environment variables or a secret-management system for sensitive configuration.

## License
This project is intended for educational purposes.
