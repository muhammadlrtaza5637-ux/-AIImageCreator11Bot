"""
AIImageCreator11Bot
-------------------
A Telegram bot that turns text prompts into AI-generated images.

Image backend: Pollinations.ai (free, no API key required).
Framework: python-telegram-bot v21+ (async)

Env vars required:
    BOT_TOKEN         - Telegram bot token from @BotFather

Optional env vars:
    IMAGE_WIDTH       - default 1024
    IMAGE_HEIGHT      - default 1024
"""

import logging
import os
import random
import urllib.parse

import httpx
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
IMAGE_WIDTH = int(os.environ.get("IMAGE_WIDTH", "1024"))
IMAGE_HEIGHT = int(os.environ.get("IMAGE_HEIGHT", "1024"))

POLLINATIONS_BASE = "https://image.pollinations.ai/prompt/"


def build_image_url(prompt: str, seed: int | None = None) -> str:
    """Build a Pollinations.ai image URL for a given prompt."""
    encoded_prompt = urllib.parse.quote(prompt)
    seed = seed if seed is not None else random.randint(0, 2_000_000_000)
    params = {
        "width": IMAGE_WIDTH,
        "height": IMAGE_HEIGHT,
        "seed": seed,
        "nologo": "true",
    }
    query = urllib.parse.urlencode(params)
    return f"{POLLINATIONS_BASE}{encoded_prompt}?{query}", seed


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👋 Hi! I'm AI Image Creator.\n\n"
        "Send me any text description and I'll turn it into an image.\n\n"
        "Example:\n"
        "  a cyberpunk city at night, neon lights, rain\n\n"
        "Commands:\n"
        "/generate <prompt> - generate an image\n"
        "/help - show this message"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await start(update, context)


async def send_generated_image(update_message, prompt: str) -> None:
    """Fetch and send a generated image for the given prompt."""
    chat = update_message.chat
    await chat.send_action(ChatAction.UPLOAD_PHOTO)

    url, seed = build_image_url(prompt)

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        image_bytes = response.content

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🔄 Regenerate", callback_data=f"regen|{prompt[:250]}"
                )
            ]
        ]
    )

    await update_message.reply_photo(
        photo=image_bytes,
        caption=f'"{prompt}"',
        reply_markup=keyboard,
    )


async def generate_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    prompt = " ".join(context.args).strip()
    if not prompt:
        await update.message.reply_text(
            "Please include a prompt, e.g.\n/generate a red fox in the snow"
        )
        return
    await handle_prompt(update.message, prompt)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    prompt = update.message.text.strip()
    if not prompt:
        return
    await handle_prompt(update.message, prompt)


async def handle_prompt(message, prompt: str) -> None:
    try:
        await send_generated_image(message, prompt)
    except httpx.HTTPError:
        logger.exception("Image generation failed")
        await message.reply_text(
            "⚠️ Sorry, I couldn't generate that image. Please try again."
        )
    except Exception:
        logger.exception("Unexpected error")
        await message.reply_text("⚠️ Something went wrong. Please try again.")


async def regenerate_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    _, prompt = query.data.split("|", 1)
    await handle_prompt(query.message, prompt)


def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN environment variable is not set. "
            "Get a token from @BotFather and set it in your environment."
        )

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("generate", generate_command))
    application.add_handler(CallbackQueryHandler(regenerate_callback, pattern=r"^regen\|"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Bot starting (polling mode)...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
