"""
DataAnalystAgent: given a natural-language data-analysis question (which
embeds the exact JSON reply shape it wants), runs a tool-calling loop against
an LLM served through aipipe.org (OpenAI-compatible /chat/completions) until
the model calls `submit_answer`, and returns:
  - the final answer value (already shaped as requested)
  - a step-by-step trace (for the JSONL log)

Enforces a soft wall-clock time budget so the bot never blows the grader's
per-question timeout, even if MAX_AGENT_STEPS hasn't been hit yet.
"""
import json
import os
import time
from dotenv import load_dotenv


load_dotenv()
from openai import OpenAI

from tools import TOOL_SCHEMAS, execute_python, fetch_url

AIPIPE_BASE_URL = os.getenv("AIPIPE_BASE_URL", "https://aipipe.org/openai/v1")
MODEL = os.getenv("AIPIPE_MODEL", "gpt-5-mini")
MAX_STEPS = int(os.getenv("MAX_AGENT_STEPS", "12"))
TIME_BUDGET_SECONDS = float(os.getenv("AGENT_TIME_BUDGET_SECONDS", "90"))

SYSTEM_PROMPT = """You are a rigorous data analyst agent operating over Telegram.

You will be given a data-analysis question. It may:
- embed data directly in the message text (inline CSV/JSON/table), and/or
- reference a public dataset (MOSPI, data.gov.in, or similar) you must locate
  and fetch yourself.

The question ALWAYS specifies, via an example, the exact JSON shape the final
"answer" field must take. Read that template carefully and match it exactly -
same keys, same nesting, same value types (string vs number vs list vs object).
Grading is EXACT whole-object equality - never add extra keys beyond exactly
what the template shows.

Rules:
1. Never guess a number or fact you can compute or look up - use the
   execute_python tool to parse inline data or compute statistics, and the
   fetch_url tool to retrieve any external dataset the question points at.
2. Show your work through tool calls, not through prose - keep any text
   response minimal; you are not chatting with a human right now.
3. If a dataset URL 404s or the structure isn't what you expect, try
   reasonable alternate URLs/paths (e.g. MOSPI's data portal, data.gov.in
   API/OGD endpoints) before giving up. If, after genuine effort, no live
   source is reachable, give your best evidence-based estimate rather than
   refusing - but prefer real data whenever it's reachable.
4. When you are fully confident in the final answer, call `submit_answer`
   exactly once with `answer_json` set to a JSON-encoded STRING of the value
   in the exact requested shape - just the value itself, not the whole
   {"answer": ..., "log_url": ...} envelope (e.g. if the shape requested is
   {"state": "Assam"}, call submit_answer(answer_json='{"state": "Assam"}')).
5. If the conversation contains multiple prior messages, only answer the
   LAST question, using earlier messages only as context if relevant.
6. You are on a time budget. If you're told your budget is almost up, submit
   your best current answer immediately rather than continuing to investigate.
"""


class AgentError(Exception):
    pass


def _get_client() -> OpenAI:
    return OpenAI(
        base_url=AIPIPE_BASE_URL,
        api_key=os.environ["AIPIPE_TOKEN"],
    )


def run_agent(question_text: str, history: list[str] | None = None) -> dict:
    """
    Runs the tool-calling loop. Returns:
      {
        "final_answer": <json-serializable value>,
        "steps": [ {tool, input, output}, ... ],
        "raw_final_text": <any trailing text the model produced, if present>
      }
    Raises AgentError if the model never calls submit_answer within
    MAX_STEPS or TIME_BUDGET_SECONDS.
    """
    client = _get_client()

    user_content = ""
    if history:
        user_content += "Prior messages in this conversation (context only):\n"
        for i, h in enumerate(history):
            user_content += f"[{i+1}] {h}\n"
        user_content += "\nAnswer only the question below:\n"
    user_content += question_text

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
    steps = []
    start_time = time.monotonic()
    budget_warning_sent = False

    for step_num in range(MAX_STEPS):
        elapsed = time.monotonic() - start_time

        if elapsed > TIME_BUDGET_SECONDS and not budget_warning_sent:
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "TIME BUDGET ALMOST UP. Call submit_answer right now "
                        "with your best current answer - do not call any "
                        "other tool."
                    ),
                }
            )
            budget_warning_sent = True
        elif elapsed > TIME_BUDGET_SECONDS * 1.3:
            # Model ignored the warning - stop burning time entirely.
            raise AgentError(
                f"Exceeded hard time budget ({elapsed:.1f}s) without submit_answer "
                f"for question: {question_text[:200]}"
            )

        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOL_SCHEMAS,
            tool_choice="auto",
        )
        choice = response.choices[0]
        msg = choice.message
        tool_calls = msg.tool_calls or []

        if not tool_calls:
            # Model stopped without calling a tool - nudge it once more.
            messages.append({"role": "assistant", "content": msg.content or ""})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "You must call a tool. If you have the final answer, "
                        "call submit_answer now."
                    ),
                }
            )
            continue

        # OpenAI-format assistant turn must echo back the tool_calls it made.
        messages.append(
            {
                "role": "assistant",
                "content": msg.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in tool_calls
                ],
            }
        )

        submitted = None
        submission_error = None

        for tc in tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}

            if name == "submit_answer":
                raw = args.get("answer_json", "")
                try:
                    submitted = json.loads(raw) if isinstance(raw, str) else raw
                except json.JSONDecodeError as e:
                    submission_error = f"submit_answer got invalid JSON: {e}"
                steps.append(
                    {"tool": "submit_answer", "input": args, "output": None}
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": "recorded",
                    }
                )
                continue

            if name == "execute_python":
                result = execute_python(args.get("code", ""))
            elif name == "fetch_url":
                result = fetch_url(args.get("url", ""))
            else:
                result = {"error": f"unknown tool {name}"}

            steps.append({"tool": name, "input": args, "output": result})
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result)[:8000],
                }
            )

        if submission_error:
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"{submission_error}. Call submit_answer again with "
                        "valid JSON in answer_json."
                    ),
                }
            )
            continue

        if submitted is not None:
            return {
                "final_answer": submitted,
                "steps": steps,
                "raw_final_text": msg.content or "",
            }

    raise AgentError(
        f"Agent did not submit_answer within {MAX_STEPS} steps for question: "
        f"{question_text[:200]}"
    )
