import os
import logging
from collections import defaultdict
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import anthropic

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# Per-chat conversation history (in-memory; resets on restart)
conversation_histories: dict[int, list[dict]] = defaultdict(list)
MAX_HISTORY = 20  # keep last 20 messages per chat


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    conversation_histories[chat_id].clear()
    await update.message.reply_text(
        "Hi! I'm Sylvia. How can I help you today?\n\n"
        "Use /reset to start a fresh conversation."
    )


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    conversation_histories[chat_id].clear()
    await update.message.reply_text("Conversation reset. Let's start fresh!")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user_text = update.message.text

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    history = conversation_histories[chat_id]
    history.append({"role": "user", "content": user_text})

    # Trim to keep only the last MAX_HISTORY messages
    if len(history) > MAX_HISTORY:
        history[:] = history[-MAX_HISTORY:]

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system="You are Sylvia, a friendly and knowledgeable AI assistant. "
                   "Be concise, warm, and helpful.",
            messages=history,
        )
        reply = response.content[0].text
        history.append({"role": "assistant", "content": reply})
    except anthropic.APIError as e:
        logger.error("Anthropic API error: %s", e)
        reply = "Sorry, I ran into an issue reaching my AI backend. Please try again in a moment."

    await update.message.reply_text(reply)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Update %s caused error: %s", update, context.error)


def main() -> None:
    if not TELEGRAM_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set in environment / .env file")
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY is not set in environment / .env file")

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)

    logger.info("Sylvia bot is running — polling for messages…")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
