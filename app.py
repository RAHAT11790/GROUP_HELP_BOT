import logging
import json
import os
import re
import asyncio
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from telegram.constants import ParseMode

# ------------------- Flask -------------------
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "✅ Bot is Alive on Railway!"

# ------------------- Logging -------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ------------------- Files -------------------
FILTER_FILE = "filters_data.json"
PHOTO_FILE = "photo_data.json"
ADMIN_FILE = "admin_data.json"

# ------------------- JSON Helper -------------------
def load_json(file, default):
    if os.path.exists(file):
        with open(file, "r", encoding="utf-8") as f:
            return json.load(f)
    return default

def save_json(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ------------------- Data -------------------
keyword_store = load_json(FILTER_FILE, {})
photo_store = load_json(PHOTO_FILE, {})
ADMIN_IDS = load_json(ADMIN_FILE, [6621572366])

# ------------------- Bot Settings -------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
RAILWAY_URL = os.environ.get("RAILWAY_URL")

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN environment variable missing")
if not RAILWAY_URL:
    raise ValueError("❌ RAILWAY_URL environment variable missing")

WELCOME_TEMPLATE = """🎉 𝑾𝒆𝒍𝒄𝒐𝒎𝒆 𝒕𝒐 𓆩{mention}𓆪 🎉

💫 Watch every twist, every turn —
🔓 100% FREE
🗣️ Now with Hindi Dubbing
📚 All Seasons • All Episodes
💎 Join:@CARTOONFUNNY03
"""

photo_temp = {}

def is_admin(user_id):
    return user_id in ADMIN_IDS

# ------------------- Commands -------------------
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "👋 হ্যালো! আমি Anime Keyword Bot!\n\n"
        "একসাথে অনেকগুলো কীওয়ার্ড যোগ করতে:\n"
        "/rs\n"
        "[Naruto] https://link1\n"
        "[Attack on Titan] https://link2\n"
        "[One Piece, OP] https://link3\n\n"
        "📸 /photo - ফটো বা GIF সেট করতে\n"
        "👑 /addadmin user_id - নতুন এডমিন অ্যাড করতে"
    )

# ✅ Add filters
async def set_filter(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    chat_id = str(update.effective_chat.id)

    if not is_admin(user_id):
        await update.message.reply_text("❌ আপনি এডমিন নন!")
        return

    text = update.message.text.split("\n", 1)
    if len(text) < 2:
        await update.message.reply_text("ব্যবহার:\n/rs\n[Keyword] লিংক\n[Another] লিংক")
        return

    multi_lines = text[1].strip().split("\n")
    if chat_id not in keyword_store:
        keyword_store[chat_id] = {}

    added_count = 0
    for line in multi_lines:
        match = re.search(r"\[(.*?)\]\s+(https?://\S+)", line)
        if not match:
            continue

        keywords = [k.strip().lower() for k in match.group(1).split(",") if k.strip()]
        link = match.group(2).strip()

        for kw in keywords:
            keyword_store[chat_id][kw] = link
            added_count += 1

    save_json(FILTER_FILE, keyword_store)
    await update.message.reply_text(f"✅ মোট {added_count} কীওয়ার্ড সেভ হয়েছে!")

# ✅ Keyword match reply
async def handle_message(update: Update, context: CallbackContext):
    message = update.message
    chat_id = str(message.chat_id)
    text = message.text.lower() if message.text else ""

    if chat_id in keyword_store:
        for keyword, link in keyword_store[chat_id].items():
            if keyword in text:
                mention = message.from_user.mention_markdown()
                msg = WELCOME_TEMPLATE.format(mention=mention)
                buttons = [[InlineKeyboardButton("📥 WATCH & DOWNLOAD 📥", url=link)]]
                markup = InlineKeyboardMarkup(buttons)

                if chat_id in photo_store and photo_store[chat_id]:
                    info = photo_store[chat_id]
                    if info["type"] == "gif":
                        await message.reply_animation(animation=info["file_id"], caption=msg, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)
                    else:
                        await message.reply_photo(photo=info["file_id"], caption=msg, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)
                else:
                    await message.reply_text(msg, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)
                break

# ✅ Admin commands (clear, photo, etc.)
async def clear_filters(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    chat_id = str(update.effective_chat.id)
    if not is_admin(user_id):
        await update.message.reply_text("❌ আপনি এডমিন নন!")
        return
    count = len(keyword_store.get(chat_id, {}))
    keyword_store[chat_id] = {}
    save_json(FILTER_FILE, keyword_store)
    await update.message.reply_text(f"✅ সব ফিল্টার মুছে ফেলা হয়েছে ({count})!")

# ------------------- Application -------------------
application = Application.builder().token(BOT_TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("rs", set_filter))
application.add_handler(CommandHandler("clear", clear_filters))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# ------------------- Webhook -------------------
@flask_app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    asyncio.create_task(application.process_update(update))
    return "ok", 200

# ------------------- Run -------------------
if __name__ == "__main__":
    print("🚀 Starting Flask + Telegram Webhook...")
    PORT = int(os.environ.get("PORT", 8080))

    async def set_webhook():
        url = f"{RAILWAY_URL}/{BOT_TOKEN}"
        await application.bot.set_webhook(url=url)
        print(f"✅ Webhook set successfully at {url}")

    asyncio.run(set_webhook())
    flask_app.run(host="0.0.0.0", port=PORT)
