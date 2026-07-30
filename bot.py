# # """
# Telegram bot entrypoint.

# Uses long polling (no public webhook needed for the BOT itself - only the
# run.jsonl log needs a public URL, which logger.py handles via GitHub).

# Behavior:
# - Maintains a short rolling history per chat so multi-turn tasks work
#   ("a short sequence of messages - answer the last one").
# - Runs the agent on the latest message.
# - Replies with EXACTLY one JSON object: {"answer": ..., "log_url": ...}
#   and nothing else - no markdown fences, no extra text.
# """
# import json
# import logging
# import os
# import time
# import traceback
# from threading import Thread

# from dotenv import load_dotenv
# from flask import Flask
# from telegram import Update
# from telegram.ext import Application, ContextTypes, MessageHandler, filters

# from agent import AgentError, run_agent
# from logger import log_run

# load_dotenv()
# processed_message_ids = set()
# logging.basicConfig(
#     format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
#     level=logging.INFO,
# )
# log = logging.getLogger("bot")

# MAX_HISTORY_MESSAGES = 3 # how many prior messages of context to keep per chat

# # --- DUMMY HTTP SERVER FOR RENDER WEB SERVICE ---
# flask_app = Flask('')

# @flask_app.route('/')
# def home():
#     return "Bot is alive!", 200

# def run_server():
#     # Render assigns a dynamic port via the PORT environment variable (default 8080)
#     port = int(os.environ.get("PORT", 8080))
#     flask_app.run(host='0.0.0.0', port=port)

# def keep_alive():
#     t = Thread(target=run_server, daemon=True)
#     t.start()
# # ------------------------------------------------


# async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
#     message = update.message
#     if message is None or not message.text:
#         return
    
#     if message.message_id in processed_message_ids:
#         log.info("Duplicate update ignored: %s", message.message_id)
#         return
    
#     processed_message_ids.add(message.message_id)

#     chat_id = message.chat_id
#     text = message.text.strip()
#     log.info("chat=%s received: %s", chat_id, text[:100])

#     history = context.chat_data.setdefault("history", [])

#     started = time.time()
#     error_text = None
#     final_answer = None
#     steps = []

#     try:
#         result = run_agent(text, history=history[-MAX_HISTORY_MESSAGES:])
#         final_answer = result["final_answer"]
#         steps = result["steps"]
#     except AgentError as e:
#         error_text = str(e)
#         log.error("AgentError: %s", error_text)
#     except Exception as e:  # noqa: BLE001
#         error_text = f"{type(e).__name__}: {e}"
#         log.error("Unhandled agent error:\n%s", traceback.format_exc())

#     # Always append this message to rolling history, even on error,
#     # so subsequent turns still have context.
#     history.append(text)
#     if len(history) > MAX_HISTORY_MESSAGES:
#         del history[: len(history) - MAX_HISTORY_MESSAGES]

#     record = {
#         "timestamp": time.time(),
#         "question": text,
#         "history_used": history[-MAX_HISTORY_MESSAGES:-1],
#         "steps": steps,
#         "final_answer": final_answer,
#         "error": error_text,
#         "duration_seconds": round(time.time() - started, 2),
#     }
#     log_url = log_run(record)
#     record["log_url"] = log_url

#     if error_text is not None:
#         reply_obj = {
#             "answer": None,
#             "log_url": log_url
#         }
#     else:
#         reply_obj = {
#             "answer": final_answer,
#             "log_url": log_url
#         }

#     reply_text = json.dumps(reply_obj, ensure_ascii=False)
#     log.info("chat=%s replying: %s", chat_id, reply_text[:300])
#     await message.reply_text(reply_text)


# def main() -> None:
#     # Start web server thread before starting long polling
#     keep_alive()

#     token = os.environ["TELEGRAM_BOT_TOKEN"]
#     app = Application.builder().token(token).build()
#     app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
#     log.info("Bot starting (long polling)...")
#     app.run_polling(allowed_updates=Update.ALL_TYPES)


# if __name__ == "__main__":
#     main()





"""
Telegram bot entrypoint.

Uses long polling (no public webhook needed for the BOT itself - only the
run.jsonl log needs a public URL, which logger.py handles via GitHub).

Behavior:
- Maintains a short rolling history per chat so multi-turn tasks work
  ("a short sequence of messages - answer the last one").
- Runs the agent on the latest message.
- Replies with EXACTLY one JSON object: {"answer": ..., "log_url": ...}
  and nothing else - no markdown fences, no extra text.
"""
import json
import logging
import os
import time
import traceback
from threading import Thread

from dotenv import load_dotenv
from flask import Flask
from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from agent import AgentError, run_agent
from logger import log_run

load_dotenv()
processed_message_ids = set()
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("bot")

MAX_HISTORY_MESSAGES = 3 # how many prior messages of context to keep per chat

# --- DUMMY HTTP SERVER FOR RENDER WEB SERVICE ---
flask_app = Flask('')

@flask_app.route('/')
def home():
    return "Bot is alive!", 200

def run_server():
    # Render assigns a dynamic port via the PORT environment variable (default 8080)
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_server, daemon=True)
    t.start()
# ------------------------------------------------


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if message is None or not message.text:
        return
    
    if message.message_id in processed_message_ids:
        log.info("Duplicate update ignored: %s", message.message_id)
        return
    
    processed_message_ids.add(message.message_id)

    chat_id = message.chat_id
    text = message.text.strip()
    log.info("chat=%s received: %s", chat_id, text[:100])

    history = context.chat_data.setdefault("history", [])

    started = time.time()
    error_text = None
    final_answer = None
    steps = []

    try:
        result = run_agent(text, history=history[-MAX_HISTORY_MESSAGES:])
        final_answer = result["final_answer"]
        steps = result["steps"]
    except AgentError as e:
        error_text = str(e)
        log.error("AgentError: %s", error_text)
    except Exception as e:  # noqa: BLE001
        error_text = f"{type(e).__name__}: {e}"
        log.error("Unhandled agent error:\n%s", traceback.format_exc())

    # Always append this message to rolling history, even on error,
    # so subsequent turns still have context.
    history.append(text)
    if len(history) > MAX_HISTORY_MESSAGES:
        del history[: len(history) - MAX_HISTORY_MESSAGES]

    record = {
        "timestamp": time.time(),
        "question": text,
        "history_used": history[-MAX_HISTORY_MESSAGES:-1],
        "steps": steps,
        "final_answer": final_answer,
        "error": error_text,
        "duration_seconds": round(time.time() - started, 2),
    }
    log_url = log_run(record)
    record["log_url"] = log_url

    if error_text is not None:
        reply_obj = {
            "answer": None,
            "log_url": log_url
        }
    else:
        reply_obj = {
            "answer": final_answer,
            "log_url": log_url
        }

    reply_text = json.dumps(reply_obj, ensure_ascii=False)
    log.info("chat=%s replying: %s", chat_id, reply_text[:300])
    await message.reply_text(reply_text)


def main() -> None:
    # Start web server thread before starting long polling
    keep_alive()

    token = os.environ["TELEGRAM_BOT_TOKEN"]
    app = Application.builder().token(token).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    log.info("Bot starting (long polling)...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()