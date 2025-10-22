import logging
import json
import os
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from telegram.constants import ParseMode

# লগিং সেটআপ
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ডাটা ফাইলের নাম
FILTER_FILE = "filters_data.json"
PHOTO_FILE = "photo_data.json"
ADMIN_FILE = "admin_data.json"

# ------------------- হেল্পার ফাংশন -------------------

def load_json(file, default):
    if os.path.exists(file):
        with open(file, "r", encoding="utf-8") as f:
            return json.load(f)
    return default

def save_json(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ------------------- ডাটা লোড -------------------

keyword_store = load_json(FILTER_FILE, {})
photo_store = load_json(PHOTO_FILE, {})
ADMIN_IDS = load_json(ADMIN_FILE, [6621572366])  # ডিফল্ট এডমিন

# ------------------- বট সেটআপ -------------------

BOT_TOKEN = "8437757573:AAHz-hT0E6pzIzJpkL3rtzLVR5oihqsbWhk"

WELCOME_TEMPLATE = """🔥 𝗪𝗘𝗟𝗖𝗢𝗠𝗘 𓆩{mention}𓆪 🔥
━━━━━━━━━━━━━━━━━━━
🎬 𝑬𝒗𝒆𝒓𝒚 𝑻𝒘𝒊𝒔𝒕, 𝑬𝒗𝒆𝒓𝒚 𝑻𝒖𝒓𝒏 — 𝐈𝐧 𝐇𝐢𝐧𝐝𝐢 𝐃𝐮𝐛𝐛𝐢𝐧𝐠 🎧
⚡ 𝐓𝐲𝐩𝐞 𝐘𝐨𝐮𝐫 𝐅𝐚𝐯𝐨𝐮𝐫𝐢𝐭𝐞 𝐀𝐧𝐢𝐦𝐞 𝐚𝐧𝐝 𝐄𝐧𝐣𝐨𝐲 𝐍𝐨𝐰 💪
🍿 𝑯𝒂𝒑𝒑𝒚 𝑾𝒂𝒕𝒄𝒉𝒊𝒏𝒈 𝑾𝒂𝒓𝒓𝒊𝒐𝒓! ⚔️
━━━━━━━━━━━━━━━━━━━
🔰 𝙅𝙤𝙞𝙣 𝙊𝙪𝙧 𝘾𝙤𝙢𝙢𝙪𝙣𝙞𝙩𝙮: @CARTOONFUNNY03
"""

photo_temp = {}

def is_admin(user_id):
    return user_id in ADMIN_IDS

def clean_keyword(text):
    """কীওয়ার্ড ক্লিনআপ করে শুধু মূল শব্দগুলো বের করে"""
    # বিশেষ কারাক্টার রিমুভ করুন
    cleaned = re.sub(r'[❖◆★▪•‣✧📡@#ᴏғғɪᴄɪᴀʟ]', '', text)
    # ব্র্যাকেট এবং অতিরিক্ত স্পেস রিমুভ করুন
    cleaned = re.sub(r'[\(\)\[\]\{\}]', '', cleaned)
    # ড্যাশ/হাইফেন রিমুভ করুন
    cleaned = re.sub(r'[-–—]', ' ', cleaned)
    # একাধিক স্পেস রিমুভ করুন
    cleaned = re.sub(r'\s+', ' ', cleaned)
    # লাইন ব্রেক রিমুভ করুন
    cleaned = cleaned.replace('\n', ' ').replace('\r', ' ')
    # প্রান্তের স্পেস ট্রিম করুন এবং লোয়ারকেস করুন
    return cleaned.strip().lower()

def find_matching_keyword(user_text, keyword_store, chat_id):
    """ইউজারের টেক্সটে কোনো কীওয়ার্ড ম্যাচ করছে কিনা চেক করুন"""
    if chat_id not in keyword_store:
        return None
    
    user_text_clean = clean_keyword(user_text)
    user_words = set(user_text_clean.split())
    
    # ডিবাগিং জন্য
    logger.info(f"ইউজার টেক্সট ক্লিন: {user_text_clean}")
    logger.info(f"ইউজার ওয়ার্ডস: {user_words}")
    
    for keyword, link in keyword_store[chat_id].items():
        keyword_clean = clean_keyword(keyword)
        keyword_words = set(keyword_clean.split())
        
        # যদি ইউজারের টেক্সটে কীওয়ার্ডের সব শব্দ থাকে
        if keyword_words.issubset(user_words):
            logger.info(f"ম্যাচ পাওয়া গেছে: {keyword} -> {link}")
            return link
        
        # অথবা যদি কীওয়ার্ডের ৭০%+ শব্দ মেলে
        common_words = keyword_words.intersection(user_words)
        if len(common_words) >= len(keyword_words) * 0.7:
            logger.info(f"পার্শিয়াল ম্যাচ: {keyword} -> {link}")
            return link
    
    return None

# ------------------- কমান্ড -------------------

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

# ✅ একসাথে অনেক কীওয়ার্ড যোগ
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

# ✅ টেক্সট হ্যান্ডলার - IMPROVED VERSION
async def handle_message(update: Update, context: CallbackContext):
    message = update.message
    chat_id = str(message.chat_id)
    text = message.text if message.text else ""

    if not text.strip():
        return

    # ডিবাগ লগ
    logger.info(f"ইউজার মেসেজ: {text}")

    if chat_id in keyword_store:
        matched_link = find_matching_keyword(text, keyword_store, chat_id)
        
        if matched_link:
            mention = message.from_user.mention_markdown()
            msg = WELCOME_TEMPLATE.format(mention=mention)
            buttons = [[InlineKeyboardButton("📥 WATCH & DOWNLOAD 📥", url=matched_link)]]
            markup = InlineKeyboardMarkup(buttons)

            if chat_id in photo_store and photo_store[chat_id]:
                info = photo_store[chat_id]
                if info["type"] == "gif":
                    await message.reply_animation(
                        animation=info["file_id"], 
                        caption=msg, 
                        reply_markup=markup, 
                        parse_mode=ParseMode.MARKDOWN
                    )
                else:
                    await message.reply_photo(
                        photo=info["file_id"], 
                        caption=msg, 
                        reply_markup=markup, 
                        parse_mode=ParseMode.MARKDOWN
                    )
            else:
                await message.reply_text(msg, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)

# ✅ কীওয়ার্ড লিস্ট
async def list_keywords(update: Update, context: CallbackContext):
    chat_id = str(update.effective_chat.id)
    if chat_id in keyword_store and keyword_store[chat_id]:
        msg = "🎬 **কীওয়ার্ড লিস্ট:**\n"
        for k, v in keyword_store[chat_id].items():
            msg += f"• `{k}` → {v}\n"
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text("❌ কোনো কীওয়ার্ড সেট করা নেই।")

# ✅ কীওয়ার্ড ডিলিট
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

# ✅ সব ফিল্টার ক্লিয়ার
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

# ✅ ফটো সেট
async def set_photo(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    chat_id = str(update.effective_chat.id)
    if not is_admin(user_id):
        await update.message.reply_text("❌ আপনি এডমিন নন!")
        return
    await update.message.reply_text("📸 এখন একটি ফটো বা GIF পাঠান...")
    photo_temp[user_id] = {"chat_id": chat_id, "waiting": True}

# ✅ ফটো রিসিভ
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

# ✅ ফটো রিমুভ
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

# ✅ নতুন এডমিন যোগ
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

# ------------------- বট রান -------------------

def main():
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

    print("✅ Bot চলছে... (স্মার্ট কীওয়ার্ড ম্যাচিং সক্রিয়)")
    app.run_polling()

if __name__ == "__main__":
    main()
