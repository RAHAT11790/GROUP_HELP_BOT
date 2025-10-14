import logging
import json
import os
import sys
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler
from telegram.constants import ParseMode
import re
from flask import Flask
from threading import Thread

# Flask app for Render
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    app.run(host='0.0.0.0', port=5000)

# লগিং কনফিগারেশন - Unbuffered for Render
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# ডাটা ফাইল নাম
KEYWORD_DATA_FILE = "keyword_data.json"
PHOTO_DATA_FILE = "photo_data.json"
ADMIN_DATA_FILE = "admin_data.json"

# Environment variables from Render - Token must be set, no fallback
BOT_TOKEN = os.environ['BOT_TOKEN']
ADMIN_IDS = [int(x.strip()) for x in os.environ.get('ADMIN_IDS', '6621572366,-1002892874648').split(',')]

# ফটো সেট করার জন্য টেম্পোরারি স্টোরেজ
photo_temp = {}
bulk_temp = {}

# এডমিন চেক করার ফাংশন
def is_admin(update: Update):
    user_id = update.effective_user.id
    
    # যদি মেসেজ ফরওয়ার্ড হয় চ্যানেল থেকে
    if update.message and update.message.forward_from_chat:
        forwarded_chat_id = update.message.forward_from_chat.id
        if forwarded_chat_id in ADMIN_IDS:
            return True
    
    # নরমাল এডমিন চেক
    return user_id in ADMIN_IDS

# ডাটা লোড করার ফাংশন
def load_data():
    keyword_store = {}
    photo_store = {}
    
    try:
        if os.path.exists(KEYWORD_DATA_FILE):
            with open(KEYWORD_DATA_FILE, 'r', encoding='utf-8') as f:
                keyword_store = json.load(f)
    except Exception as e:
        logger.error(f"Keyword data load error: {e}")
    
    try:
        if os.path.exists(PHOTO_DATA_FILE):
            with open(PHOTO_DATA_FILE, 'r', encoding='utf-8') as f:
                photo_store = json.load(f)
    except Exception as e:
        logger.error(f"Photo data load error: {e}")
    
    # Load admins from file if exists, merge with env
    try:
        if os.path.exists(ADMIN_DATA_FILE):
            with open(ADMIN_DATA_FILE, 'r') as f:
                file_admins = json.load(f)
                ADMIN_IDS.extend(file_admins)
                ADMIN_IDS = list(set(ADMIN_IDS))  # Dedupe
    except Exception as e:
        logger.error(f"Admin data load error: {e}")
    
    return keyword_store, photo_store

# ডাটা সেভ করার ফাংশন
def save_data(keyword_store, photo_store):
    try:
        with open(KEYWORD_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(keyword_store, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Keyword data save error: {e}")
    
    try:
        with open(PHOTO_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(photo_store, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Photo data save error: {e}")
    
    # Save admins
    try:
        with open(ADMIN_DATA_FILE, 'w') as f:
            json.dump(ADMIN_IDS, f)
    except Exception as e:
        logger.error(f"Admin data save error: {e}")

# ডাটা লোড করুন
keyword_store, photo_store = load_data()

# ওয়েলকাম মেসেজ টেমপ্লেট
WELCOME_TEMPLATE = """🎉 𝑾𝒆𝒍𝒄𝒐𝒎𝒆 𝒕𝒐 𓆩{mention}𓆪, 𝒕𝒉𝒆 𝒖𝒍𝒕𝒊𝒎𝒂𝒕𝒆 𝒉𝒖𝒃 𝒇𝒐𝒓 𝒂𝒍𝒍 𝒂𝒏𝒊𝒎𝒆 𝒍𝒐𝒗𝒆𝒓𝒔! 🎉

💫 Watch every twist, every turn —
🔓 100% FREE
🗣️ Now with Hindi Dubbing
🎬 𝒊𝒇 𝒚𝒐𝒖 𝒇𝒊𝒏𝒅 𝒂𝒏𝒚 𝒂𝒏𝒊𝒎𝒆 𝒕𝒚𝒑𝒆 𝒏𝒂𝒎𝒆 𝒐𝒏𝒍𝒚  

🍿 𝑯𝒂𝒑𝒑𝒚 𝑾𝒂𝒕𝒄𝒉𝒊𝒏𝒈!
⬇️𝑐𝑙𝑖𝑐𝑘 𝑡ℎ𝑖𝑠 𝑏𝑢𝑡𝑡𝑜𝑛⬇️"""

async def start(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text(
        'হ্যালো! আমি গ্রুপ হেল্প বট\n\n'
        'কমান্ড লিস্ট:\n'
        'start - Bot activ check kore\n'
        'rs - Ekta keyword set kore [keyword] link\n'
        'md - Bulk keyword add kore\n'
        'list - Shudhu keyword list dekhao\n'
        'delfilter - Ekta keyword delete koro\n'
        'clear - Shob keyword delete koro\n'
        'photo - Photo/GIF set koro (dui step e)\n'
        'removephoto - Photo/GIF remove koro\n'
        'addadmin - Notun admin add koro\n'
        'admins - Shob admin der list dekhao'
    )

async def set_filter(update: Update, context: CallbackContext) -> None:
    # এডমিন চেক
    if not is_admin(update):
        await update.message.reply_text("❌ আপনি এডমিন নন! এই কমান্ড ব্যবহার করার অনুমতি নেই।")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text('ব্যবহার: /rs [keyword1,keyword2] লিংক')
        return
    
    # ব্র্যাকেট থেকে কীওয়ার্ড বের করা
    args_text = ' '.join(context.args)
    bracket_match = re.search(r'\[(.*?)\]', args_text)
    
    if not bracket_match:
        await update.message.reply_text('ব্যবহার: /rs [keyword1,keyword2] লিংক\nব্র্যাকেটের ভিতরে কীওয়ার্ড দিন')
        return
    
    keywords_text = bracket_match.group(1)
    link = args_text[bracket_match.end():].strip()
    
    if not link:
        await update.message.reply_text('লিংক প্রদান করুন\nব্যবহার: /rs [keyword1,keyword2] লিংক')
        return
    
    # কীওয়ার্ডগুলো আলাদা করা
    keywords = [kw.strip() for kw in keywords_text.split(',') if kw.strip()]
    
    if not keywords:
        await update.message.reply_text('কমা দিয়ে কীওয়ার্ড দিন\nউদাহরণ: /rs [movie,cinema,film] লিংক')
        return
    
    chat_id = update.effective_chat.id
    
    # কীওয়ার্ড স্টোর করুন
    if str(chat_id) not in keyword_store:
        keyword_store[str(chat_id)] = {}
    
    added_keywords = []
    for keyword in keywords:
        keyword_store[str(chat_id)][keyword] = link
        added_keywords.append(keyword)
    
    # ডাটা সেভ করুন
    save_data(keyword_store, photo_store)
    
    keyword_list = ", ".join(added_keywords)
    await update.message.reply_text(f'✅ কীওয়ার্ড সেট করা হয়েছে!\n\nকীওয়ার্ড: {keyword_list}\nলিংক: {link}')

async def bulk_add_keywords(update: Update, context: CallbackContext) -> None:
    # এডমিন চেক
    if not is_admin(update):
        await update.message.reply_text("❌ আপনি এডমিন নন! এই কমান্ড ব্যবহার করার অনুমতি নেই।")
        return
    
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    await update.message.reply_text(
        "📝 **বাল্ক কীওয়ার্ড এড**\n\n"
        "এখন নিচের ফরম্যাটে কীওয়ার্ডগুলো সেন্ড করুন:\n\n"
        "```\n"
        "md [keyword1,keyword2] link1\n"
        "md [keyword3,keyword4] link2\n"
        "md [keyword5] link3\n"
        "```\n\n"
        "উদাহরণ:\n"
        "```\n"
        "md [Naruto,Anime] https://t.me/link1\n"
        "md [One Piece] https://t.me/link2\n"
        "md [Dragon Ball,DBZ] https://t.me/link3\n"
        "```\n\n"
        "💡 **নোট:** শুধু `md` দিয়ে শুরু করতে হবে, `/md` নয়!"
    )
    
    # ইউজারকে বাল্ক মোডে সেট করুন
    bulk_temp[user_id] = {'chat_id': chat_id, 'waiting_for_bulk': True}

async def handle_bulk_message(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # চেক করুন যদি ইউজার বাল্ক কীওয়ার্ডের জন্য অপেক্ষা করছে
    if user_id in bulk_temp and bulk_temp[user_id]['waiting_for_bulk']:
        
        if not update.message.text:
            await update.message.reply_text("❌ টেক্সট মেসেজ প্রয়োজন")
            return
        
        message_text = update.message.text
        lines = message_text.split('\n')
        
        added_count = 0
        errors = []
        
        for line in lines:
            line = line.strip()
            if line.startswith('md '):
                try:
                    # md কমান্ড পার্স করুন - improved parsing
                    parts = line.split(' ', 2)  # শুধু প্রথম 2 spaces এ split
                    if len(parts) >= 3:
                        bracket_content = parts[1]
                        link = parts[2].strip()
                        
                        # ব্র্যাকেট থেকে কীওয়ার্ড বের করুন
                        bracket_match = re.search(r'\[(.*?)\]', bracket_content)
                        if bracket_match and link:
                            keywords_text = bracket_match.group(1)
                            keywords = [kw.strip() for kw in keywords_text.split(',') if kw.strip()]
                            
                            if keywords and link:
                                # কীওয়ার্ড স্টোর করুন
                                if str(chat_id) not in keyword_store:
                                    keyword_store[str(chat_id)] = {}
                                
                                for keyword in keywords:
                                    keyword_store[str(chat_id)][keyword] = link
                                    added_count += 1
                            else:
                                errors.append(f"কীওয়ার্ড বা লিংক নেই: {line}")
                        else:
                            errors.append(f"ব্র্যাকেট বা লিংক ভুল: {line}")
                    else:
                        errors.append(f"ইনভ্যালিড ফরম্যাট: {line}")
                except Exception as e:
                    errors.append(f"পার্সিং error: {line} - {str(e)}")
            elif line.strip() and not line.startswith('md '):
                errors.append(f"ভুল ফরম্যাট: {line} - 'md' দিয়ে শুরু করুন")
        
        # ডাটা সেভ করুন
        save_data(keyword_store, photo_store)
        
        response = f"✅ বাল্ক এড সম্পূর্ণ!\n\nএড করা হয়েছে: {added_count} টি কীওয়ার্ড"
        if errors:
            response += f"\n\nত্রুটি ({len(errors)} টি):\n" + "\n".join(errors[:5])
        
        await update.message.reply_text(response)
        
        # টেম্পোরারি ডাটা ক্লিয়ার করুন
        del bulk_temp[user_id]

async def handle_message(update: Update, context: CallbackContext) -> None:
    # যদি বাল্ক মোডে থাকে, তাহলে আলাদা হ্যান্ডেল করবে
    user_id = update.effective_user.id
    if user_id in bulk_temp and bulk_temp[user_id]['waiting_for_bulk']:
        await handle_bulk_message(update, context)
        return
    
    message = update.message
    chat_id = message.chat_id
    text = message.text if message.text else ''
    
    if str(chat_id) in keyword_store:
        for keyword, link in keyword_store[str(chat_id)].items():
            # Case insensitive search
            if keyword.lower() in text.lower():
                logger.info(f"Keyword match: {keyword} for chat {chat_id}")
                # mention তৈরি করুন
                mention = message.from_user.mention_markdown()
                
                # ওয়েলকাম মেসেজ তৈরি করুন
                welcome_message = WELCOME_TEMPLATE.format(mention=mention)
                
                # ইনলাইন বাটন তৈরি করুন
                keyboard = [
                    [InlineKeyboardButton("📥 WATCH AND DOWNLOAD 📥", url=link)]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                # ফটো আছে কিনা চেক করুন
                if str(chat_id) in photo_store and photo_store[str(chat_id)]:
                    try:
                        # চেক করুন যদি এটি GIF হয় নাকি ফটো
                        if photo_store[str(chat_id)].get('type') == 'gif':
                            await message.reply_animation(
                                animation=photo_store[str(chat_id)]['file_id'],
                                caption=welcome_message,
                                reply_markup=reply_markup,
                                parse_mode=ParseMode.MARKDOWN
                            )
                        else:
                            await message.reply_photo(
                                photo=photo_store[str(chat_id)]['file_id'],
                                caption=welcome_message,
                                reply_markup=reply_markup,
                                parse_mode=ParseMode.MARKDOWN
                            )
                    except Exception as e:
                        logger.error(f"Media reply error: {e}")
                        # যদি ফটো/GIF সেন্ড করতে সমস্যা হয়, শুধু টেক্সট সেন্ড করুন
                        await message.reply_text(
                            welcome_message,
                            reply_markup=reply_markup,
                            parse_mode=ParseMode.MARKDOWN
                        )
                else:
                    await message.reply_text(
                        welcome_message,
                        reply_markup=reply_markup,
                        parse_mode=ParseMode.MARKDOWN
                    )
                break

async def list_keywords(update: Update, context: CallbackContext) -> None:
    chat_id = update.effective_chat.id
    
    if str(chat_id) in keyword_store and keyword_store[str(chat_id)]:
        keywords_list = []
        for keyword in keyword_store[str(chat_id)].keys():
            keywords_list.append(f"• `{keyword}`")
        
        response_text = "🎬 **সকল কীওয়ার্ড:**\n" + "\n".join(keywords_list)
        await update.message.reply_text(response_text, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text("❌ কোনো কীওয়ার্ড সেট করা নেই।")

async def delete_filter(update: Update, context: CallbackContext) -> None:
    # এডমিন চেক
    if not is_admin(update):
        await update.message.reply_text("❌ আপনি এডমিন নন!")
        return
    
    if len(context.args) < 1:
        await update.message.reply_text('ব্যবহার: /delfilter keyword')
        return
    
    # পুরো keyword টি নিন (case insensitive)
    keyword_input = ' '.join(context.args)
    chat_id = update.effective_chat.id
    
    if str(chat_id) in keyword_store and keyword_store[str(chat_id)]:
        # আসল কীওয়ার্ড খুঁজে বের করুন (case insensitive search)
        found_keyword = None
        for existing_keyword in keyword_store[str(chat_id)].keys():
            if existing_keyword.lower() == keyword_input.lower():
                found_keyword = existing_keyword
                break
        
        if found_keyword:
            # লিংকটি সেভ করে রাখুন (কনফার্মেশনে দেখানোর জন্য)
            link = keyword_store[str(chat_id)][found_keyword]
            del keyword_store[str(chat_id)][found_keyword]
            # ডাটা সেভ করুন
            save_data(keyword_store, photo_store)
            await update.message.reply_text(
                f'✅ কীওয়ার্ড ডিলিট করা হয়েছে!\n\n'
                f'কীওয়ার্ড: {found_keyword}\n'
                f'লিংক: {link}'
            )
        else:
            await update.message.reply_text('❌ এই কীওয়ার্ডটি পাওয়া যায়নি।')
    else:
        await update.message.reply_text('❌ কোনো কীওয়ার্ড সেট করা নেই।')

async def clear_filters(update: Update, context: CallbackContext) -> None:
    # এডমিন চেক
    if not is_admin(update):
        await update.message.reply_text("❌ আপনি এডমিন নন!")
        return
    
    chat_id = update.effective_chat.id
    
    if str(chat_id) in keyword_store:
        keyword_count = len(keyword_store[str(chat_id)])
        keyword_store[str(chat_id)] = {}
        # ডাটা সেভ করুন
        save_data(keyword_store, photo_store)
        await update.message.reply_text(f'✅ সব কীওয়ার্ড ডিলিট করা হয়েছে! মোট: {keyword_count}')
    else:
        await update.message.reply_text('❌ কোনো ফিল্টার সেট করা নেই।')

async def set_photo(update: Update, context: CallbackContext) -> None:
    # এডমিন চেক
    if not is_admin(update):
        await update.message.reply_text("❌ আপনি এডমিন নন!")
        return
    
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # ইউজারকে ফটো/GIF সেন্ড করতে বলুন
    await update.message.reply_text("📸 এখন একটি ফটো বা GIF সেন্ড করুন...")
    photo_temp[user_id] = {'chat_id': chat_id, 'waiting_for_photo': True}

async def handle_photo(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # চেক করুন যদি ইউজার ফটো/GIF সেন্ড করার জন্য অপেক্ষা করছে
    if user_id in photo_temp and photo_temp[user_id]['waiting_for_photo']:
        
        if update.message.photo:
            # ফটো সেট করুন
            photo_file = update.message.photo[-1].file_id
            photo_store[str(chat_id)] = {'file_id': photo_file, 'type': 'photo'}
            await update.message.reply_text("✅ ফটো সেট করা হয়েছে! এখন থেকে প্রতিটি রিপ্লাই এই ফটো সহ দেখাবে।")
        
        elif update.message.animation:
            # GIF সেট করুন
            gif_file = update.message.animation.file_id
            photo_store[str(chat_id)] = {'file_id': gif_file, 'type': 'gif'}
            await update.message.reply_text("✅ GIF সেট করা হয়েছে! এখন থেকে প্রতিটি রিপ্লাই এই GIF সহ দেখাবে।")
        
        else:
            await update.message.reply_text("❌ একটি ফটো বা GIF সেন্ড করুন।")
        
        # ডাটা সেভ করুন
        save_data(keyword_store, photo_store)
        
        # টেম্পোরারি ডাটা ক্লিয়ার করুন
        del photo_temp[user_id]

async def remove_photo(update: Update, context: CallbackContext) -> None:
    # এডমিন চেক
    if not is_admin(update):
        await update.message.reply_text("❌ আপনি এডমিন নন!")
        return
    
    chat_id = update.effective_chat.id
    
    if str(chat_id) in photo_store:
        del photo_store[str(chat_id)]
        # ডাটা সেভ করুন
        save_data(keyword_store, photo_store)
        await update.message.reply_text("✅ ফটো/GIF রিমুভ করা হয়েছে!")
    else:
        await update.message.reply_text("❌ কোনো ফটো/GIF সেট করা নেই।")

async def add_admin(update: Update, context: CallbackContext) -> None:
    # এডমিন চেক
    if not is_admin(update):
        await update.message.reply_text("❌ আপনি এডমিন নন!")
        return
    
    if len(context.args) < 1:
        await update.message.reply_text('ব্যবহার: /addadmin user_id')
        return
    
    try:
        new_admin_id = int(context.args[0])
        if new_admin_id not in ADMIN_IDS:
            ADMIN_IDS.append(new_admin_id)
            save_data(keyword_store, photo_store)  # Saves admins too
            await update.message.reply_text(f'✅ এডমিন অ্যাড করা হয়েছে! User ID: {new_admin_id}')
        else:
            await update.message.reply_text('❌ এই ইউজার ইতিমধ্যেই এডমিন!')
    except ValueError:
        await update.message.reply_text('❌ সঠিক User ID দিন (সংখ্যা)')

async def show_admins(update: Update, context: CallbackContext) -> None:
    # এডমিন চেক
    if not is_admin(update):
        await update.message.reply_text("❌ আপনি এডমিন নন!")
        return
    
    admin_list = "\n".join([f"• `{admin_id}`" for admin_id in ADMIN_IDS])
    await update.message.reply_text(f"👑 **বর্তমান এডমিনরা:**\n{admin_list}", parse_mode=ParseMode.MARKDOWN)

def main() -> None:
    # Flask server start in separate thread
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    # বট টোকেন ব্যবহার করুন
    try:
        application = Application.builder().token(BOT_TOKEN).build()

        # কমান্ড হ্যান্ডলার
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("rs", set_filter))  # একক কীওয়ার্ড সেট
        application.add_handler(CommandHandler("md", bulk_add_keywords))  # বাল্ক কীওয়ার্ড এড
        application.add_handler(CommandHandler("list", list_keywords))  # শুধু কীওয়ার্ড লিস্ট
        application.add_handler(CommandHandler("delfilter", delete_filter))  # কীওয়ার্ড ডিলিট (এডমিন)
        application.add_handler(CommandHandler("clear", clear_filters))  # সব ডিলিট (এডমিন)
        application.add_handler(CommandHandler("photo", set_photo))  # ফটো সেট (এডমিন) - দুই ধাপে
        application.add_handler(CommandHandler("removephoto", remove_photo))  # ফটো রিমুভ (এডমিন)
        application.add_handler(CommandHandler("addadmin", add_admin))  # নতুন এডমিন অ্যাড (এডমিন)
        application.add_handler(CommandHandler("admins", show_admins))  # এডমিন লিস্ট দেখাবে (এডমিন)
        
        # মেসেজ হ্যান্ডলার
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        # ফটো এবং GIF হ্যান্ডলার
        application.add_handler(MessageHandler(filters.PHOTO | filters.ANIMATION, handle_photo))

        logger.info("Bot handlers added successfully")
        print("বট চলছে...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except AttributeError as e:
        if '_polling_cleanup_cb' in str(e):
            logger.error("PTB Updater error—upgrade python-telegram-bot to >=22.5 for Python 3.13 compat.")
        raise
    except Exception as e:
        logger.error(f"Bot startup failed: {e}")
        raise

if __name__ == '__main__':
    main()
