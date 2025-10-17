import logging
import json
import os
import re
from flask import Flask
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from telegram.constants import ParseMode

# ------------------- Flask Server for UptimeRobot -------------------
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "✅ RS Group Bot is Alive!"

def run():
    flask_app.run(host="0.0.0.0", port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# ------------------- Logging -------------------
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ------------------- File Names -------------------
FILTER_FILE = "filters_data.json"
PHOTO_FILE = "photo_data.json"
ADMIN_FILE = "admin_data.json"

# ------------------- Helper Functions -------------------
def load_json(file, default):
    if os.path.exists(file):
        with open(file, "r", encoding="utf-8") as f:
            return json.load(f)
    return default

def save_json(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ------------------- Load Data -------------------
keyword_store = load_json(FILTER_FILE, {})
photo_store = load_json(PHOTO_FILE, {})
ADMIN_IDS = load_json(ADMIN_FILE, [6621572366])

# ------------------- Bot Token (Render Environment Variable) -------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN not found! Please set it in Render Environment Variables.")

WELCOME_TEMPLATE = """🎉 𝑾𝒆𝒍𝒄𝒐𝒎𝒆 𝒕𝒐 𓆩{mention}𓆪 🎉

💫 𝐖𝐚𝐭𝐜𝐡 𝐞𝐯𝐞𝐫𝐲 𝐭𝐰𝐢𝐬𝐭, 𝐞𝐯𝐞𝐫𝐲 𝐭𝐮𝐫𝐧 —
🗣️ 𝐈𝐧 𝐇𝐢𝐧𝐝𝐢 𝐃𝐮𝐛𝐛𝐢𝐧𝐠
🎬 𝒊𝒇 𝒚𝒐𝒖 𝒇𝒊𝒏𝒅 𝒂𝒏𝒚 𝒂𝒏𝒊𝒎𝒆 𝒕𝒚𝒑𝒆 𝒏𝒂𝒎𝒆 𝒐𝒏𝒍𝒚  

🍿 𝑯𝒂𝒑𝒑𝒚 𝑾𝒂𝒕𝒄𝒉𝒊𝒏𝒈!
⬇️𝐂𝐋𝐈𝐂𝐊 𝐓𝐇𝐈𝐒 𝐁𝐔𝐓𝐓𝐎𝐍⬇️"""

photo_temp = {}

def is_admin(user_id):
    return user_id in ADMIN_IDS

# ------------------- Commands -------------------
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "👋 হ্যালো! আমি RS Group Bot!\n\n"
        "একসাথে অনেকগুলো কীওয়ার্ড যোগ করতে:\n"
        "/rs\n[Name] লিংক\n[Another] লিংক\n\n"
        "📸 /photo - ফটো বা GIF সেট করতে\n"
        "👑 /addadmin user_id - নতুন এডমিন অ্যাড করতে"
    )

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
    await update.message.reply_text(f"✅ মোট {added_count} কীওয়ার্ড সেভ হয়েছে (স্থায়ীভাবে)!")

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

async def list_keywords(update: Update, context: CallbackContext):
    chat_id = str(update.effective_chat.id)
    if chat_id in keyword_store and keyword_store[chat_id]:
        msg = "🎬 **কীওয়ার্ড লিস্ট:**\n"
        for k, v in keyword_store[chat_id].items():
            msg += f"• `{k}` → {v}\n"
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text("❌ কোনো কীওয়ার্ড সেট করা নেই।")

async def delete_filter(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    chat_id = str(update.effective_chat.id)

    if not is_admin(user_id):
        await update.message.reply_text("❌ আপনি এডমিন নন!")
        return

    if len(context.args) < 1:
        await update.message.reply_text("ব্যবহার: /delfilter keyword")
        return

    kw = context.args[0].lower()
    if chat_id in keyword_store and kw in keyword_store[chat_id]:
        del keyword_store[chat_id][kw]
        save_json(FILTER_FILE, keyword_store)
        await update.message.reply_text(f"✅ '{kw}' মুছে ফেলা হয়েছে!")
    else:
        await update.message.reply_text("❌ কীওয়ার্ডটি পাওয়া যায়নি।")

async def clear_filters(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    chat_id = str(update.effective_chat.id)
    if not is_admin(user_id):
        await update.message.reply_text("❌ আপনি এডমিন নন!")
        return

    count = len(keyword_store.get(chat_id, {}))
    keyword_store[chat_id] = {}
    save_json(FILTER_FILE, keyword_store)
    await update.message.reply_text(f"✅ সব ফিল্টার ডিলিট হয়েছে! মোট: {count}")

async def set_photo(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    chat_id = str(update.effective_chat.id)
    if not is_admin(user_id):
        await update.message.reply_text("❌ আপনি এডমিন নন!")
        return
    await update.message.reply_text("📸 এখন একটি ফটো বা GIF পাঠান...")
    photo_temp[user_id] = {"chat_id": chat_id, "waiting": True}

async def handle_photo(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    chat_id = str(update.effective_chat.id)

    if user_id in photo_temp and photo_temp[user_id]["waiting"]:
        if update.message.photo:
            file_id = update.message.photo[-1].file_id
            photo_store[chat_id] = {"file_id": file_id, "type": "photo"}
        elif update.message.animation:
            file_id = update.message.animation.file_id
            photo_store[chat_id] = {"file_id": file_id, "type": "gif"}
        else:
            await update.message.reply_text("❌ ফটো বা GIF দিন।")
            return

        save_json(PHOTO_FILE, photo_store)
        await update.message.reply_text("✅ ফটো/GIF সেভ হয়েছে (স্থায়ীভাবে)!")
        del photo_temp[user_id]

async def remove_photo(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    chat_id = str(update.effective_chat.id)
    if not is_admin(user_id):
        await update.message.reply_text("❌ আপনি এডমিন নন!")
        return
    if chat_id in photo_store:
        del photo_store[chat_id]
        save_json(PHOTO_FILE, photo_store)
        await update.message.reply_text("✅ ফটো/GIF রিমুভ হয়েছে!")
    else:
        await update.message.reply_text("❌ কোনো ফটো সেট করা নেই।")

async def add_admin(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ আপনি এডমিন নন!")
        return

    if len(context.args) < 1:
        await update.message.reply_text("ব্যবহার: /addadmin user_id")
        return

    try:
        new_admin = int(context.args[0])
        if new_admin not in ADMIN_IDS:
            ADMIN_IDS.append(new_admin)
            save_json(ADMIN_FILE, ADMIN_IDS)
            await update.message.reply_text(f"✅ নতুন এডমিন অ্যাড হয়েছে: {new_admin}")
        else:
            await update.message.reply_text("❌ এই ইউজার ইতিমধ্যেই এডমিন।")
    except ValueError:
        await update.message.reply_text("❌ সঠিক ইউজার আইডি দিন।")

# ------------------- Main -------------------
def main():
    keep_alive()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("rs", set_filter))
    app.add_handler(CommandHandler("list", list_keywords))
    app.add_handler(CommandHandler("delfilter", delete_filter))
    app.add_handler(CommandHandler("clear", clear_filters))
    app.add_handler(CommandHandler("photo", set_photo))
    app.add_handler(CommandHandler("removephoto", remove_photo))
    app.add_handler(CommandHandler("addadmin", add_admin))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO | filters.ANIMATION, handle_photo))

    print("✅ RS Group Bot চলছে... Render + Flask সক্রিয়!")
    app.run_polling()

if __name__ == "__main__":
    main()
