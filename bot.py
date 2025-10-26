import os
import json
import logging
import threading
import time
from datetime import datetime
import asyncio
from telegram import (
    Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    CallbackQueryHandler, ContextTypes
)

# -----------------------
# Logging
# -----------------------
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# -----------------------
# Config / Files
# -----------------------
TOKEN = "8061585389:AAFT-3cubiYTU9VjX9VVYDE8Q6hh6mJJc-s"  # এখানে তোমার বট টোকেন দিয়ে দেবে
CHANNEL_FILE = "channels.json"
POST_FILE = "posts.json"
MULTIPOST_FILE = "multiposts.json"

# -----------------------
# Helpers: JSON file IO
# -----------------------
def load_json(filename):
    if not os.path.exists(filename):
        return []
    with open(filename, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception:
            return []

def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def ensure_files():
    if not os.path.exists(CHANNEL_FILE):
        save_json(CHANNEL_FILE, [])
    if not os.path.exists(POST_FILE):
        save_json(POST_FILE, [])
    if not os.path.exists(MULTIPOST_FILE):
        save_json(MULTIPOST_FILE, [])

# -----------------------
# Step stack helpers (for one-step back behavior)
# -----------------------
def push_step(context: ContextTypes.DEFAULT_TYPE, name: str, info: dict = None):
    if 'step_stack' not in context.user_data:
        context.user_data['step_stack'] = []
    context.user_data['step_stack'].append({'name': name, 'info': info or {}})

def pop_step(context: ContextTypes.DEFAULT_TYPE):
    if 'step_stack' in context.user_data and context.user_data['step_stack']:
        return context.user_data['step_stack'].pop()
    return None

def peek_prev_step(context: ContextTypes.DEFAULT_TYPE):
    if 'step_stack' in context.user_data and len(context.user_data['step_stack']) >= 1:
        return context.user_data['step_stack'][-1]
    return None

def clear_steps(context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop('step_stack', None)

# -----------------------
# Button parser
# -----------------------
def parse_buttons_from_text(text):
    if not text:
        return None
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("&&")]
        row = []
        for p in parts:
            if " - " in p:
                title, action = p.split(" - ", 1)
                title = title.strip()[:64]
                action = action.strip()
                if action.startswith(("http://", "https://", "tg://", "https://t.me")):
                    row.append(InlineKeyboardButton(title, url=action))
                elif action.startswith(("popup:", "alert:")):
                    row.append(InlineKeyboardButton(title, callback_data=action))
                else:
                    row.append(InlineKeyboardButton(title, callback_data=action[:64]))
            else:
                row.append(InlineKeyboardButton(p[:64], callback_data="noop"))
        if row:
            rows.append(row)
    return InlineKeyboardMarkup(rows) if rows else None

# -----------------------
# UI keyboards
# -----------------------
def main_menu_kb():
    kb = [
        [InlineKeyboardButton("➕ Add channel", callback_data="menu_add_channel"),
         InlineKeyboardButton("📜 Channel list", callback_data="menu_channel_list")],
        [InlineKeyboardButton("✍️ Create post", callback_data="menu_create_post"),
         InlineKeyboardButton("📂 My posts", callback_data="menu_my_posts")],
        [InlineKeyboardButton("📤 Send post", callback_data="menu_send_post"),
         InlineKeyboardButton("🌐 All Channels (Send)", callback_data="menu_send_all")],
        [InlineKeyboardButton("🧾 Multipost", callback_data="menu_multipost"),
         InlineKeyboardButton("✏️ Edit post", callback_data="menu_edit_post")],
        [InlineKeyboardButton("🗑 Delete", callback_data="menu_delete")],
        [InlineKeyboardButton("📘 Button Guide", callback_data="menu_guide")]
    ]
    return InlineKeyboardMarkup(kb)

def back_to_menu_kb(text="↩️ Back to Menu"):
    return InlineKeyboardMarkup([[InlineKeyboardButton(text, callback_data="back_to_menu")]])

def step_back_kb(text="↩️ Back (one step)"):
    return InlineKeyboardMarkup([[InlineKeyboardButton(text, callback_data="step_back")]])

def multipost_menu_kb(post_count: int):
    kb = [
        [InlineKeyboardButton("➕ Create New Post", callback_data="create_new_multipost")],
        [InlineKeyboardButton("📤 Send All Posts", callback_data="send_all_multipost")],
        [InlineKeyboardButton("↩️ Back to Menu", callback_data="back_to_menu")]
    ]
    return InlineKeyboardMarkup(kb)

# -----------------------
# /start
# -----------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    clear_steps(context)
    txt = (
        "👋 স্বাগতম — Multi Channel Poster Bot! \n\n"
        "নিচের বাটনগুলো দিয়ে কাজগুলো করা যাবে।\n\n"
        "📘 বাটন গাইড দেখতে 'Button Guide' বাটনে চাপ দাও।"
    )
    await update.message.reply_text(txt, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu_kb())

# -----------------------
# Add Channel
# -----------------------
async def menu_add_channel_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data['expecting_forward_for_add'] = True
    push_step(context, 'expecting_forward_for_add')
    await q.message.reply_text(
        "📩 চ্যানেল অ্যাড করতে, চ্যানেল থেকে একটি মেসেজ ফরওয়ার্ড করে এখানে পাঠাও।\n\n"
        "⚠️ নিশ্চিত করো বটটি সেই চ্যানেলে admin আছে।",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=step_back_kb()
    )

async def forward_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg.forward_from_chat:
        await update.message.reply_text("❌ এটি চ্যানেল থেকে ফরওয়ার্ড করা মেসেজ নয়।", reply_markup=main_menu_kb())
        return

    chat = msg.forward_from_chat  
    if chat.type != 'channel':  
        await update.message.reply_text("❌ ফরওয়ার্ড করা মেসেজটি একটি চ্যানেলের নয়।", reply_markup=main_menu_kb())  
        return  

    channels = load_json(CHANNEL_FILE)  
    existing_ids = [c['id'] for c in channels]  
    if chat.id in existing_ids:  
        await update.message.reply_text(f"⚠️ চ্যানেল *{chat.title}* আগে থেকেই যুক্ত আছে।", parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu_kb())  
        context.user_data.pop('expecting_forward_for_add', None)  
        pop_step(context)  
        return  

    channels.append({'id': chat.id, 'title': chat.title or str(chat.id)})  
    save_json(CHANNEL_FILE, channels)  
    await update.message.reply_text(f"✅ চ্যানেল *{chat.title}* সফলভাবে যুক্ত হয়েছে!", parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu_kb())  
    context.user_data.pop('expecting_forward_for_add', None)  
    pop_step(context)

# -----------------------
# Channel list & remove/view
# -----------------------
async def menu_channel_list_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    channels = load_json(CHANNEL_FILE)
    if not channels:
        await q.message.reply_text("📭 এখনো কোনো চ্যানেল নেই। Add channel দিয়ে চ্যানেল যোগ করো।", reply_markup=main_menu_kb())
        return

    kb = []  
    for ch in channels:  
        kb.append([InlineKeyboardButton(ch['title'][:40], callback_data=f"view_channel_{ch['id']}"),  
                   InlineKeyboardButton("❌ Remove", callback_data=f"remove_channel_{ch['id']}")])  
    kb.append([InlineKeyboardButton("↩️ Back to Menu", callback_data="back_to_menu")])  
    await q.message.reply_text("📜 আপনার চ্যানেলগুলো:", reply_markup=InlineKeyboardMarkup(kb))

async def view_channel_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    parts = q.data.split("_", 2)
    if len(parts) < 3:
        await q.message.reply_text("Invalid")
        return
    ch_id = int(parts[2])
    channels = load_json(CHANNEL_FILE)
    ch = next((c for c in channels if c['id'] == ch_id), None)
    if not ch:
        await q.message.reply_text("Channel not found.", reply_markup=back_to_menu_kb())
        return
    await q.message.reply_text(f"📣 Channel: *{ch['title']}*\nID: `{ch['id']}`", parse_mode=ParseMode.MARKDOWN, reply_markup=back_to_menu_kb())

async def remove_channel_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("Removing...")
    try:
        ch_id = int(q.data.split("_", 2)[2])
    except:
        await q.message.reply_text("Invalid")
        return
    channels = load_json(CHANNEL_FILE)
    channels = [c for c in channels if c['id'] != ch_id]
    save_json(CHANNEL_FILE, channels)
    await q.message.reply_text("✅ চ্যানেল মুছে দেয়া হয়েছে।", reply_markup=main_menu_kb())

# -----------------------
# Create post flow
# -----------------------
async def menu_create_post_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data.pop('creating_post', None)
    context.user_data.pop('pending_file_id', None)
    context.user_data.pop('pending_type', None)
    clear_steps(context)
    context.user_data['creating_post'] = True
    push_step(context, 'creating_post')
    await q.message.reply_text(
        "📝 পোস্ট তৈরি শুরু হয়েছে।\n\n"
        "আপনি চাইলে প্রথমে মিডিয়া (ছবি/ভিডিও) পাঠাতে পারো — মিডিয়া পাঠালে বট সেটি সেভ করবে এবং পরে আপনি বাটন যোগ করতে পারবেন।\n"
        "অথবা সরাসরি টেক্সট পাঠালে সেটাও পোস্ট হিসেবে সেভ হবে।\n\n"
        "📎 মিডিয়া পাঠালে বট ক্যাপশন চেক করবে — যদি না থাকে তাহলে আপনি Add Caption বা Skip করে এগোতে পারবেন।",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=step_back_kb()
    )

async def save_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = context.user_data

    if user.get('awaiting_buttons_for_post_id'):  
        post_id = user.get('awaiting_buttons_for_post_id')  
        buttons_raw = update.message.text or ""  
        posts = load_json(POST_FILE)  
        p = next((x for x in posts if x['id'] == post_id), None)  
        if not p:  
            await update.message.reply_text("❌ পোস্ট পাওয়া যায়নি।", reply_markup=main_menu_kb())  
            user.pop('awaiting_buttons_for_post_id', None)  
            pop_step(context)  
            return  
        p['buttons_raw'] = buttons_raw  
        save_json(POST_FILE, posts)  
        # Multipost mode চেক করুন
        is_multipost = user.get('creating_multipost', False)
        if is_multipost:
            kb = [
                [InlineKeyboardButton("➕ Create New Post", callback_data="create_new_multipost")],
                [InlineKeyboardButton("📤 Send All Posts", callback_data="send_all_multipost")],
                [InlineKeyboardButton("↩️ Back to Menu", callback_data="back_to_menu")]
            ]
            await update.message.reply_text(
                f"✅ বাটন যোগ হয়েছে! পোস্ট #{post_id} সেভ হয়েছে। মোট পোস্ট: {len(user.get('multipost_list', []))}\n\nচাইলে নতুন পোস্ট তৈরি করো বা সব পাঠাও:",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(kb)
            )
        else:
            kb = [  
                [InlineKeyboardButton("📤 Send Post", callback_data=f"send_post_{post_id}")],  
                [InlineKeyboardButton("↩️ Back to Menu", callback_data="back_to_menu")]  
            ]  
            await update.message.reply_text(  
                "✅ বাটন সংরক্ষণ হয়েছে! এখন চাইলে পোস্ট পাঠাও:",  
                parse_mode=ParseMode.MARKDOWN,  
                reply_markup=InlineKeyboardMarkup(kb)  
            )  
        user.pop('awaiting_buttons_for_post_id', None)  
        pop_step(context)  
        return  

    if user.get('awaiting_caption_text'):  
        caption = update.message.text or ""  
        fid = user.get('pending_file_id')  
        mtype = user.get('pending_type')  
        posts = load_json(POST_FILE)  
        posts.append({  
            "id": len(posts) + 1,  
            "text": caption,  
            "buttons_raw": "",  
            "media_id": fid,  
            "media_type": mtype  
        })  
        save_json(POST_FILE, posts)  
        new_id = len(posts)  
        kb = [  
            [InlineKeyboardButton("➕ Add Buttons", callback_data=f"add_buttons_{new_id}")],  
            [InlineKeyboardButton("📤 Send Post", callback_data=f"send_post_{new_id}")],  
            [InlineKeyboardButton("↩️ Back to Menu", callback_data="back_to_menu")]  
        ]  
        await update.message.reply_text("✅ ক্যাপশনসহ মিডিয়া সেভ হয়েছে! এখন চাইলে বাটন যোগ করো বা সরাসরি পাঠাও:", reply_markup=InlineKeyboardMarkup(kb))  
        user.pop('awaiting_caption_text', None)  
        user.pop('pending_file_id', None)  
        user.pop('pending_type', None)  
        pop_step(context)  
        return  

    if user.get('awaiting_caption_text_multipost'):
        caption = update.message.text or ""
        fid = user.get('pending_file_id')
        mtype = user.get('pending_type')
        posts = load_json(POST_FILE)
        new_id = len(posts) + 1
        posts.append({
            "id": new_id,
            "text": caption,
            "buttons_raw": "",
            "media_id": fid,
            "media_type": mtype
        })
        save_json(POST_FILE, posts)
        if 'multipost_list' not in context.user_data:
            context.user_data['multipost_list'] = []
        context.user_data['multipost_list'].append(new_id)
        kb = [
            [InlineKeyboardButton("➕ Add Buttons", callback_data=f"add_buttons_{new_id}")],
            [InlineKeyboardButton("➕ Create New Post", callback_data="create_new_multipost")],
            [InlineKeyboardButton("📤 Send All Posts", callback_data="send_all_multipost")],
            [InlineKeyboardButton("↩️ Back to Menu", callback_data="back_to_menu")]
        ]
        await update.message.reply_text(
            f"✅ ক্যাপশনসহ মিডিয়া পোস্ট #{new_id} সেভ হয়েছে! মোট পোস্ট: {len(context.user_data['multipost_list'])}\n\nচাইলে বাটন যোগ করো, নতুন পোস্ট তৈরি করো বা সব পাঠাও:",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        user.pop('awaiting_caption_text_multipost', None)
        user.pop('pending_file_id', None)
        user.pop('pending_type', None)
        pop_step(context)
        return

    if user.get('awaiting_buttons_for_multipost'):
        buttons_raw = update.message.text or ""
        # Last post ধরে নিন বা temp থেকে
        if 'multipost_temp' in context.user_data:
            temp_post = context.user_data['multipost_temp']
            temp_post['buttons_raw'] = buttons_raw
            posts = load_json(POST_FILE)
            new_id = len(posts) + 1
            temp_post['id'] = new_id
            posts.append(temp_post)
            save_json(POST_FILE, posts)
            if 'multipost_list' not in context.user_data:
                context.user_data['multipost_list'] = []
            context.user_data['multipost_list'].append(new_id)
            context.user_data.pop('multipost_temp', None)
            kb = multipost_menu_kb(len(context.user_data['multipost_list']))
            await update.message.reply_text(
                f"✅ বাটন যোগ হয়েছে! পোস্ট #{new_id} সেভ হয়েছে। মোট পোস্ট: {len(context.user_data['multipost_list'])}",
                reply_markup=kb
            )
        else:
            await update.message.reply_text("❌ কোনো পোস্ট খুঁজে পাওয়া যায়নি।", reply_markup=main_menu_kb())
        user.pop('awaiting_buttons_for_multipost', None)
        pop_step(context)
        return

    if user.get('creating_multipost'):  
        text = update.message.text or ""  
        lines = text.splitlines()  
        btn_lines = []  
        main_lines = []  
        started_buttons = False  
        for line in lines:  
            if " - " in line and (("http" in line) or ("t.me" in line) or "&&" in line or "popup:" in line or "alert:" in line or "share:" in line):  
                started_buttons = True  
                btn_lines.append(line)  
            else:  
                if started_buttons:  
                    btn_lines.append(line)  
                else:  
                    main_lines.append(line)  
        main_text = "\n".join(main_lines).strip()  
        btn_text = "\n".join(btn_lines).strip()  
          
        # অটো সেভ করবে  
        posts = load_json(POST_FILE)  
        new_id = len(posts) + 1
        new_post = {  
            "id": new_id,
            "text": main_text,  
            "buttons_raw": btn_text,  
            "media_id": None,  
            "media_type": None  
        }  
        posts.append(new_post)  
        save_json(POST_FILE, posts)  
          
        # মাল্টিপোস্ট লিস্টে যোগ করবে  
        if 'multipost_list' not in context.user_data:  
            context.user_data['multipost_list'] = []  
        context.user_data['multipost_list'].append(new_id)  
          
        kb = [  
            [InlineKeyboardButton("➕ Add Buttons", callback_data=f"add_buttons_{new_id}")],  
            [InlineKeyboardButton("➕ Create New Post", callback_data="create_new_multipost")],  
            [InlineKeyboardButton("📤 Send All Posts", callback_data="send_all_multipost")],  
            [InlineKeyboardButton("↩️ Back to Menu", callback_data="back_to_menu")]  
        ]  
        await update.message.reply_text(  
            f"✅ পোস্ট #{new_id} অটো সেভ হয়েছে! মোট পোস্ট: {len(context.user_data['multipost_list'])}\n\n"
            "চাইলে বাটন যোগ করো বা নতুন পোস্ট তৈরি করো।",  
            reply_markup=InlineKeyboardMarkup(kb)  
        )  
        return  

    if user.get('editing_post'):  
        pid = user.get('editing_post')  
        text = update.message.text or ""  
        posts = load_json(POST_FILE)  
        p = next((x for x in posts if x['id'] == pid), None)  
        if not p:  
            await update.message.reply_text("❌ পোস্ট পাওয়া যায়নি।", reply_markup=main_menu_kb())  
            user.pop('editing_post', None)  
            pop_step(context)  
            return  
        lines = text.splitlines()  
        btn_lines = []  
        main_lines = []  
        started_buttons = False  
        for line in lines:  
            if " - " in line and (("http" in line) or ("t.me" in line) or "&&" in line or "popup:" in line or "alert:" in line):  
                started_buttons = True  
                btn_lines.append(line)  
            else:  
                if started_buttons:  
                    btn_lines.append(line)  
                else:  
                    main_lines.append(line)  
        if main_lines:  
            p['text'] = "\n".join(main_lines).strip()  
        if btn_lines:  
            p['buttons_raw'] = "\n".join(btn_lines).strip()  
        save_json(POST_FILE, posts)  
        await update.message.reply_text("✅ পোস্ট আপডেট হয়েছে!", reply_markup=main_menu_kb())  
        user.pop('editing_post', None)  
        pop_step(context)  
        return  

    if user.get('creating_post'):  
        text = update.message.text or ""  
        posts = load_json(POST_FILE)  
        lines = text.splitlines()  
        btn_lines = []  
        main_lines = []  
        started_buttons = False  
        for line in lines:  
            if " - " in line and (("http" in line) or ("t.me" in line) or "&&" in line or "popup:" in line or "alert:" in line or "share:" in line):  
                started_buttons = True  
                btn_lines.append(line)  
            else:  
                if started_buttons:  
                    btn_lines.append(line)  
                else:  
                    main_lines.append(line)  
        main_text = "\n".join(main_lines).strip()  
        btn_text = "\n".join(btn_lines).strip()  
        posts.append({"id": len(posts) + 1, "text": main_text, "buttons_raw": btn_text, "media_id": None, "media_type": None})  
        save_json(POST_FILE, posts)  
        await update.message.reply_text("✅ পোস্ট সংরক্ষণ করা হয়েছে!", reply_markup=main_menu_kb())  
        context.user_data.pop('creating_post', None)  
        pop_step(context)  
        return

# -----------------------
# Media handler
# -----------------------
async def media_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    fid = None
    mtype = None
    if msg.photo:
        fid = msg.photo[-1].file_id
        mtype = "photo"
    elif msg.video:
        fid = msg.video.file_id
        mtype = "video"
    elif msg.animation:
        fid = msg.animation.file_id
        mtype = "animation"

    if not fid:  
        await msg.reply_text("❌ শুধু ছবি/ভিডিও/GIF পাঠাও।", reply_markup=main_menu_kb())  
        return  

    if context.user_data.get('creating_multipost'):  
        if msg.caption:  
            # অটো সেভ করবে  
            posts = load_json(POST_FILE)  
            new_id = len(posts) + 1
            new_post = {  
                "id": new_id,
                "text": msg.caption,  
                "buttons_raw": "",  
                "media_id": fid,  
                "media_type": mtype  
            }  
            posts.append(new_post)  
            save_json(POST_FILE, posts)  
              
            # মাল্টিপোস্ট লিস্টে যোগ করবে  
            if 'multipost_list' not in context.user_data:  
                context.user_data['multipost_list'] = []  
            context.user_data['multipost_list'].append(new_id)  
              
            kb = [  
                [InlineKeyboardButton("➕ Add Buttons", callback_data=f"add_buttons_{new_id}")],  
                [InlineKeyboardButton("➕ Create New Post", callback_data="create_new_multipost")],  
                [InlineKeyboardButton("📤 Send All Posts", callback_data="send_all_multipost")],  
                [InlineKeyboardButton("↩️ Back to Menu", callback_data="back_to_menu")]  
            ]  
            await msg.reply_text(  
                f"✅ মিডিয়া পোস্ট #{new_id} অটো সেভ হয়েছে! মোট পোস্ট: {len(context.user_data['multipost_list'])}\n\n"
                "চাইলে বাটন যোগ করো বা নতুন পোস্ট তৈরি করো।",  
                reply_markup=InlineKeyboardMarkup(kb)  
            )  
            return  
          
        context.user_data['pending_file_id'] = fid  
        context.user_data['pending_type'] = mtype  
        push_step(context, 'awaiting_caption_choice_multipost', {'file_id': fid, 'type': mtype})  
        kb = [  
            [InlineKeyboardButton("✍️ Add Caption", callback_data="add_caption_multipost")],  
            [InlineKeyboardButton("⏭️ Skip (no caption)", callback_data="skip_caption_multipost")],  
            [InlineKeyboardButton("↩️ Back (one step)", callback_data="step_back")]  
        ]  
        await msg.reply_text("📝 আপনি কি ক্যাপশন যোগ করতে চান?", reply_markup=InlineKeyboardMarkup(kb))  
        return  

    if msg.caption:  
        posts = load_json(POST_FILE)  
        posts.append({  
            "id": len(posts) + 1,  
            "text": msg.caption,  
            "buttons_raw": "",  
            "media_id": fid,  
            "media_type": mtype  
        })  
        save_json(POST_FILE, posts)  
        new_id = len(posts)  
        kb = [  
            [InlineKeyboardButton("➕ Add Buttons", callback_data=f"add_buttons_{new_id}")],  
            [InlineKeyboardButton("📤 Send Post", callback_data=f"send_post_{new_id}")],  
            [InlineKeyboardButton("↩️ Back to Menu", callback_data="back_to_menu")]  
        ]  
        await msg.reply_text("✅ মিডিয়া ও ক্যাপশন সেভ হয়েছে! এখন চাইলে বাটন যোগ করো বা সরাসরি পাঠাও:", reply_markup=InlineKeyboardMarkup(kb))  
        return  

    context.user_data['pending_file_id'] = fid  
    context.user_data['pending_type'] = mtype  
    push_step(context, 'awaiting_caption_choice', {'file_id': fid, 'type': mtype})  
    kb = [  
        [InlineKeyboardButton("✍️ Add Caption", callback_data="add_caption")],  
        [InlineKeyboardButton("⏭️ Skip (no caption)", callback_data="skip_caption")],  
        [InlineKeyboardButton("↩️ Back (one step)", callback_data="step_back")]  
    ]  
    await msg.reply_text("📝 আপনি কি ক্যাপশন যোগ করতে চান?", reply_markup=InlineKeyboardMarkup(kb))

async def caption_choice_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    if data == "add_caption":
        await q.message.reply_text("✍️ এখন ক্যাপশন লিখে পাঠান:", reply_markup=step_back_kb())
        context.user_data['awaiting_caption_text'] = True
        push_step(context, 'awaiting_caption_text', {'pending_file_id': context.user_data.get('pending_file_id')})
    elif data == "skip_caption":
        fid = context.user_data.get('pending_file_id')
        mtype = context.user_data.get('pending_type')
        posts = load_json(POST_FILE)
        posts.append({
            "id": len(posts) + 1,
            "text": "",
            "buttons_raw": "",
            "media_id": fid,
            "media_type": mtype
        })
        save_json(POST_FILE, posts)
        new_id = len(posts)
        kb = [
            [InlineKeyboardButton("➕ Add Buttons", callback_data=f"add_buttons_{new_id}")],
            [InlineKeyboardButton("📤 Send Post", callback_data=f"send_post_{new_id}")],
            [InlineKeyboardButton("↩️ Back to Menu", callback_data="back_to_menu")]
        ]
        await q.message.reply_text("✅ মিডিয়া (ক্যাপশন ছাড়া) সেভ করা হয়েছে! এখন চাইলে বাটন যোগ করো বা সরাসরি পাঠাও:", reply_markup=InlineKeyboardMarkup(kb))
        context.user_data.pop('pending_file_id', None)
        context.user_data.pop('pending_type', None)
        pop_step(context)
    else:
        await q.message.reply_text("❌ অজানা অপশন", reply_markup=main_menu_kb())

async def caption_choice_multipost_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    if data == "add_caption_multipost":
        await q.message.reply_text("✍️ এখন ক্যাপশন লিখে পাঠান:", reply_markup=step_back_kb())
        context.user_data['awaiting_caption_text_multipost'] = True
        push_step(context, 'awaiting_caption_text_multipost')
    elif data == "skip_caption_multipost":
        fid = context.user_data.get('pending_file_id')
        mtype = context.user_data.get('pending_type')
        # অটো সেভ করবে  
        posts = load_json(POST_FILE)  
        new_id = len(posts) + 1
        new_post = {  
            "id": new_id,
            "text": "",  
            "buttons_raw": "",  
            "media_id": fid,  
            "media_type": mtype  
        }  
        posts.append(new_post)  
        save_json(POST_FILE, posts)  
          
        # মাল্টিপোস্ট লিস্টে যোগ করবে  
        if 'multipost_list' not in context.user_data:  
            context.user_data['multipost_list'] = []  
        context.user_data['multipost_list'].append(new_id)  
          
        kb = [  
            [InlineKeyboardButton("➕ Add Buttons", callback_data=f"add_buttons_{new_id}")],  
            [InlineKeyboardButton("➕ Create New Post", callback_data="create_new_multipost")],  
            [InlineKeyboardButton("📤 Send All Posts", callback_data="send_all_multipost")],  
            [InlineKeyboardButton("↩️ Back to Menu", callback_data="back_to_menu")]  
        ]  
        await q.message.reply_text(  
            f"✅ মিডিয়া পোস্ট #{new_id} অটো সেভ হয়েছে! মোট পোস্ট: {len(context.user_data['multipost_list'])}\n\n"
            "চাইলে বাটন যোগ করো বা নতুন পোস্ট তৈরি করো।",  
            reply_markup=InlineKeyboardMarkup(kb)  
        )  
        context.user_data.pop('pending_file_id', None)  
        context.user_data.pop('pending_type', None)  
        pop_step(context)  
    else:  
        await q.message.reply_text("❌ অজানা অপশন", reply_markup=main_menu_kb())

async def add_buttons_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    # Callback data parse করুন  
    callback_data = q.data  
    print(f"Raw callback data: {callback_data}")  
      
    # "add_buttons_" এর পরের অংশটি নিন  
    if callback_data.startswith("add_buttons_"):  
        try:  
            pid_str = callback_data.replace("add_buttons_", "")  
            pid = int(pid_str)  
            print(f"Parsed post ID: {pid}")  
        except Exception as e:  
            print(f"Error parsing post ID: {e}")  
            await q.message.reply_text("❌ পোস্ট আইডি বুঝতে পারছি না।", reply_markup=main_menu_kb())  
            return  
    else:  
        await q.message.reply_text("❌ ইনভ্যালিড রিকোয়েস্ট।", reply_markup=main_menu_kb())  
        return  
      
    # পোস্ট exists কিনা চেক করুন  
    posts = load_json(POST_FILE)  
    p = next((x for x in posts if x['id'] == pid), None)  
    if not p:  
        await q.message.reply_text("❌ পোস্ট পাওয়া যায়নি।", reply_markup=main_menu_kb())  
        return  
      
    context.user_data['awaiting_buttons_for_post_id'] = pid  
    push_step(context, 'awaiting_buttons_for_post_id', {'post_id': pid})  
      
    await q.message.reply_text(  
        "✍️ এখন বাটন লাইন পাঠাও (উদাহরণ):\n\n"  
        "`Button 1 - https://example.com && Button 2 - https://example2.com`\n\n"  
        "বা multiple lines এ:\n"  
        "`Button 1 - https://example.com`\n"  
        "`Button 2 - https://example2.com`\n\n"  
        "📘 ফরম্যাট গাইড দেখতে 'Button Guide' চাপো।",  
        parse_mode=ParseMode.MARKDOWN,  
        reply_markup=step_back_kb()  
    )

# -----------------------
# My posts / view / delete / edit flows - UPDATED
# -----------------------
async def menu_my_posts_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    posts = load_json(POST_FILE)
    if not posts:
        await q.message.reply_text("📭 কোনো পোস্ট নেই। Create post দিয়ে পোস্ট যোগ করো।", reply_markup=back_to_menu_kb())
        return

    kb = []  
    for p in posts:  
        # পোস্টের প্রথম 20টি অক্ষর টাইটেল হিসেবে দেখাবে  
        title = p.get('text', 'No Title')[:20] + "..." if len(p.get('text', '')) > 20 else p.get('text', 'No Title')  
        if not title.strip():  
            title = "Media Post"  
          
        kb.append([  
            InlineKeyboardButton(f"📄 {title}", callback_data=f"view_post_{p['id']}"),  
            InlineKeyboardButton("🗑 Delete", callback_data=f"del_post_{p['id']}")  
        ])  
      
    kb.append([InlineKeyboardButton("📤 Send All Posts", callback_data="send_all_posts")])  
    kb.append([InlineKeyboardButton("↩️ Back to Menu", callback_data="back_to_menu")])  
      
    await q.message.reply_text("🗂 আপনার পোস্টগুলো:", reply_markup=InlineKeyboardMarkup(kb))

async def view_post_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    pid = int(q.data.split("_")[-1])
    posts = load_json(POST_FILE)
    p = next((x for x in posts if x['id'] == pid), None)
    if not p:
        await q.message.reply_text("❌ পোস্ট পাওয়া যায়নি।", reply_markup=back_to_menu_kb())
        return

    # পোস্টের কন্টেন্ট দেখাবে  
    text_content = p.get('text', '')  
    if not text_content.strip():  
        text_content = "📷 Media Post"  
      
    text = f"*📝 পোস্ট #{p['id']}*\n\n{text_content}"  
      
    if p.get('buttons_raw'):  
        text += f"\n\n*বাটন:*\n`{p['buttons_raw']}`"  
      
    markup = parse_buttons_from_text(p.get('buttons_raw',''))  
      
    # একশন বাটন  
    action_kb = [  
        [InlineKeyboardButton("✏️ Edit Post", callback_data=f"edit_post_{p['id']}"),  
         InlineKeyboardButton("📤 Send Post", callback_data=f"send_post_{p['id']}")],  
        [InlineKeyboardButton("➕ Add Buttons", callback_data=f"add_buttons_{p['id']}"),  
         InlineKeyboardButton("🗑 Delete", callback_data=f"del_post_{p['id']}")],  
        [InlineKeyboardButton("↩️ Back to Posts", callback_data="menu_my_posts")]  
    ]  
    action_markup = InlineKeyboardMarkup(action_kb)  
      
    try:  
        if p.get('media_type') == "photo":  
            await q.message.reply_photo(  
                photo=p['media_id'],   
                caption=text,   
                parse_mode=ParseMode.MARKDOWN,   
                reply_markup=action_markup  
            )  
        elif p.get('media_type') == "video":  
            await q.message.reply_video(  
                video=p['media_id'],   
                caption=text,   
                parse_mode=ParseMode.MARKDOWN,   
                reply_markup=action_markup  
            )  
        elif p.get('media_type') == "animation":  
            await q.message.reply_animation(  
                animation=p['media_id'],   
                caption=text,   
                parse_mode=ParseMode.MARKDOWN,   
                reply_markup=action_markup  
            )  
        else:  
            await q.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=action_markup)  
    except Exception as e:  
        await q.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=action_markup)

async def del_post_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    pid = int(q.data.split("_")[-1])
    posts = load_json(POST_FILE)
    posts = [p for p in posts if p['id'] != pid]
    for i, p in enumerate(posts):
        p['id'] = i + 1
    save_json(POST_FILE, posts)
    await q.message.reply_text("✅ পোস্ট মুছে দেয়া হয়েছে।", reply_markup=main_menu_kb())

async def menu_edit_post_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    posts = load_json(POST_FILE)
    if not posts:
        await q.message.reply_text("❗ কোনো পোস্ট নেই।", reply_markup=back_to_menu_kb())
        return

    kb = []  
    for p in posts:  
        # পোস্টের প্রথম 20টি অক্ষর টাইটেল হিসেবে দেখাবে  
        title = p.get('text', 'No Title')[:20] + "..." if len(p.get('text', '')) > 20 else p.get('text', 'No Title')  
        if not title.strip():  
            title = "Media Post"  
          
        kb.append([InlineKeyboardButton(f"✏️ {title}", callback_data=f"edit_post_{p['id']}")])  
      
    kb.append([InlineKeyboardButton("↩️ Back to Menu", callback_data="back_to_menu")])  
    await q.message.reply_text("✏️ কোন পোস্ট এডিট করতে চাও?", reply_markup=InlineKeyboardMarkup(kb))

async def choose_edit_post_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    pid = int(q.data.split("_")[-1])

    # আগের পোস্ট কন্টেন্ট দেখাবে  
    posts = load_json(POST_FILE)  
    p = next((x for x in posts if x['id'] == pid), None)  
    if not p:  
        await q.message.reply_text("❌ পোস্ট পাওয়া যায়নি।", reply_markup=main_menu_kb())  
        return  
      
    # আগের কন্টেন্ট দেখাবে এডিট করার জন্য  
    old_text = p.get('text', '')  
    old_buttons = p.get('buttons_raw', '')  
      
    preview_text = f"*✏️ এডিট পোস্ট #{pid}*\n\n"  
      
    if old_text:  
        preview_text += f"*বর্তমান টেক্সট:*\n{old_text}\n\n"  
    else:  
        preview_text += "*বর্তমান টেক্সট:* 📷 Media Post\n\n"  
      
    if old_buttons:  
        preview_text += f"*বর্তমান বাটন:*\n`{old_buttons}`\n\n"  
      
    preview_text += "নতুন টেক্সট বা বাটন লাইন পাঠাও (বাটন ফরম্যাট দেখতে Guide চাপো):"  
      
    context.user_data['editing_post'] = pid  
    push_step(context, 'editing_post', {'post_id': pid})  
      
    await q.message.reply_text(preview_text, parse_mode=ParseMode.MARKDOWN, reply_markup=step_back_kb())

# -----------------------
# Multipost - COMPLETELY FIXED
# -----------------------
async def menu_multipost_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    # রিসেট করবে  
    context.user_data['creating_multipost'] = True  
    context.user_data['multipost_list'] = []  
    clear_steps(context)  
    push_step(context, 'creating_multipost')  
      
    await q.message.reply_text(  
        "🧾 *Multipost Mode চালু হয়েছে!*\n\n"  
        "এখন থেকে প্রতিটি পোস্ট *অটো সেভ* হবে।\n\n"  
        "📝 আপনি যা করতে পারেন:\n"  
        "• টেক্সট পোস্ট পাঠালে অটো সেভ হবে\n"  
        "• মিডিয়া পাঠালে অটো সেভ হবে\n"  
        "• বাটন যোগ করতে পারবেন\n"  
        "• অনেকগুলো পোস্ট তৈরি করে একসাথে সেন্ড করতে পারবেন\n\n"  
        "এখন প্রথম পোস্ট তৈরি শুরু করো:",  
        parse_mode=ParseMode.MARKDOWN,  
        reply_markup=step_back_kb()  
    )

async def create_new_multipost_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    context.user_data['creating_multipost'] = True  
    push_step(context, 'creating_multipost')  
      
    await q.message.reply_text(  
        "📝 নতুন পোস্ট তৈরি শুরু করো।\n\n"  
        "মিডিয়া (ছবি/ভিডিও/GIF) অথবা টেক্সট পাঠাও।\n"  
        "পোস্ট অটো সেভ হবে!",  
        parse_mode=ParseMode.MARKDOWN,  
        reply_markup=step_back_kb()  
    )

async def send_all_multipost_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    multipost_ids = context.user_data.get('multipost_list', [])  
    if not multipost_ids:  
        await q.message.reply_text("❌ কোনো পোস্ট তৈরি করা হয়নি।", reply_markup=main_menu_kb())  
        return  
      
    posts = load_json(POST_FILE)  
    total_sent = 0  
      
    await q.message.reply_text(f"📤 {len(multipost_ids)}টি পোস্ট পাঠানো হচ্ছে...")  
      
    for pid in multipost_ids:  
        post = next((p for p in posts if p['id'] == pid), None)  
        if post:  
            sent = await send_post_to_channels(context, post)  
            total_sent += sent  
            # প্রতিটি পোস্ট সেন্ড হওয়ার পর একটু delay  
            await asyncio.sleep(1)  
      
    # ক্লিন আপ  
    context.user_data.pop('multipost_list', None)  
    context.user_data.pop('creating_multipost', None)  
    clear_steps(context)  
      
    await q.message.reply_text(  
        f"✅ মোট {len(multipost_ids)}টি পোস্ট {total_sent} চ্যানেলে পাঠানো হয়েছে!",  
        reply_markup=main_menu_kb()  
    )

# -----------------------
# Send helpers
# -----------------------
async def send_post_to_channels(context: ContextTypes.DEFAULT_TYPE, post: dict):
    channels = load_json(CHANNEL_FILE)
    sent = 0
    for ch in channels:
        try:
            markup = parse_buttons_from_text(post.get('buttons_raw', ''))
            caption = post.get("text", "")
            if post.get("media_type") == "photo":
                await context.bot.send_photo(chat_id=ch['id'], photo=post["media_id"], caption=caption or None, parse_mode=ParseMode.MARKDOWN, reply_markup=markup)
            elif post.get("media_type") == "video":
                await context.bot.send_video(chat_id=ch['id'], video=post["media_id"], caption=caption or None, parse_mode=ParseMode.MARKDOWN, reply_markup=markup)
            elif post.get("media_type") == "animation":
                await context.bot.send_animation(chat_id=ch['id'], animation=post["media_id"], caption=caption or None, parse_mode=ParseMode.MARKDOWN, reply_markup=markup)
            else:
                await context.bot.send_message(chat_id=ch['id'], text=caption or "(No text)", parse_mode=ParseMode.MARKDOWN, reply_markup=markup)
            sent += 1
        except Exception as e:
            logging.exception("Send Error to channel %s", ch.get('id'))
    return sent

# -----------------------
# Send post
# -----------------------
async def menu_send_post_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    posts = load_json(POST_FILE)
    channels = load_json(CHANNEL_FILE)
    if not posts:
        await q.message.reply_text("❗ কোনো পোস্ট নেই। আগে Create post দিয়ে পোস্ট যোগ করো।", reply_markup=back_to_menu_kb())
        return
    if not channels:
        await q.message.reply_text("❗ কোনো চ্যানেল নেই। Add channel দিয়ে যোগ করো।", reply_markup=back_to_menu_kb())
        return

    kb = []  
    for p in posts:  
        # পোস্টের প্রথম 20টি অক্ষর টাইটেল হিসেবে দেখাবে  
        title = p.get('text', 'No Title')[:20] + "..." if len(p.get('text', '')) > 20 else p.get('text', 'No Title')  
        if not title.strip():  
            title = "Media Post"  
          
        kb.append([InlineKeyboardButton(f"📤 {title}", callback_data=f"send_post_{p['id']}")])  
      
    kb.append([InlineKeyboardButton("📤 Send All Posts", callback_data="send_all_posts")])  
    kb.append([InlineKeyboardButton("↩️ Back to Menu", callback_data="back_to_menu")])  
      
    await q.message.reply_text("📤 কোন পোস্ট পাঠাতে চাও?", reply_markup=InlineKeyboardMarkup(kb))

async def send_post_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    try:  
        post_id = int(q.data.split("_")[-1])  
        print(f"Send post ID: {post_id}")  
    except:  
        await q.message.reply_text("❌ পোস্ট আইডি পাওয়া যায়নি।", reply_markup=back_to_menu_kb())  
        return  

    posts = load_json(POST_FILE)  
    post = next((x for x in posts if x["id"] == post_id), None)  
    if not post:  
        await q.message.reply_text("❌ পোস্ট পাওয়া যায়নি।", reply_markup=back_to_menu_kb())  
        return  

    sent = await send_post_to_channels(context, post)  
    await q.message.reply_text(f"✅ পোস্ট {sent} চ্যানেলে পাঠানো হয়েছে।", reply_markup=main_menu_kb())

async def send_all_posts_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    posts = load_json(POST_FILE)
    if not posts:
        await q.message.reply_text("❗ কোনো পোস্ট নেই।", reply_markup=back_to_menu_kb())
        return

    total_sent = 0  
    for post in posts:  
        sent = await send_post_to_channels(context, post)  
        total_sent += sent  
        # প্রতিটি পোস্ট সেন্ড হওয়ার পর একটু delay  
        await asyncio.sleep(1)  
      
    await q.message.reply_text(f"✅ সমস্ত {len(posts)}টি পোস্ট {total_sent} চ্যানেলে পাঠানো হয়েছে!", reply_markup=main_menu_kb())

async def menu_send_all_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    posts = load_json(POST_FILE)
    if not posts:
        await q.message.reply_text("❗ কোনো পোস্ট নেই।", reply_markup=back_to_menu_kb())
        return
    kb = []
    for p in posts:
        # পোস্টের প্রথম 20টি অক্ষর টাইটেল হিসেবে দেখাবে
        title = p.get('text', 'No Title')[:20] + "..." if len(p.get('text', '')) > 20 else p.get('text', 'No Title')
        if not title.strip():
            title = "Media Post"

        kb.append([InlineKeyboardButton(f"🌐 {title}", callback_data=f"choose_all_{p['id']}")])  
      
    kb.append([InlineKeyboardButton("🌐 Send All Posts", callback_data="send_all_posts")])  
    kb.append([InlineKeyboardButton("↩️ Back to Menu", callback_data="back_to_menu")])  
      
    await q.message.reply_text("কোন পোস্ট All Channels-এ পাঠাবো?", reply_markup=InlineKeyboardMarkup(kb))

async def choose_all_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    pid = int(q.data.split("_")[-1])
    posts = load_json(POST_FILE)
    post = next((x for x in posts if x['id'] == pid), None)
    if not post:
        await q.message.reply_text("❌ পোস্ট পাওয়া যায়নি।", reply_markup=back_to_menu_kb())
        return
    sent = await send_post_to_channels(context, post)
    await q.message.reply_text(f"✅ পোস্ট {sent} চ্যানেলে পাঠানো হয়েছে!", reply_markup=main_menu_kb())

# -----------------------
# Button guide and generic callbacks
# -----------------------
async def menu_guide_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    text = (
        "Button Format Guide\n\n"
        "• Single button:\n"
        "Button text - https://t.me/example\n\n"
        "• Multiple buttons same line:\n"
        "Button 1 - https://t.me/a && Button 2 - https://t.me/b\n\n"
        "• Multiple rows of buttons:\n"
        "Button text - https://t.me/LinkExample\nButton text - https://t.me/LinkExample\n\n"
        "• Insert a button that displays a popup:\n"
        "Button text - popup: Text of the popup\n\n"
        "Example:\n⎙ WATCH & DOWNLOAD ⎙ - https://t.me/fandub01 && 💬 GROUP - https://t.me/hindianime03"
    )
    await q.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_to_menu_kb())

async def generic_callback_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data or ""
    if data.startswith("popup:") or data.startswith("alert:"):
        txt = data.split(":",1)[1].strip()
        try:
            await q.answer(text=txt, show_alert=True)
        except:
            await q.message.reply_text(txt)
    elif data == "noop":
        await q.message.reply_text("🔘 বাটন ক্লিক হয়েছে (কোনো কার্য নেই)।")
    else:
        await q.message.reply_text("🔘 বাটন ক্লিক: " + data)

# -----------------------
# Back to menu
# -----------------------
async def back_to_menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    clear_steps(context)
    await q.message.reply_text("↩️ মূল মেনুতে ফিরে আসা হলো", reply_markup=main_menu_kb())

# -----------------------
# Step-back
# -----------------------
async def step_back_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    current = pop_step(context)
    prev = peek_prev_step(context)
    if current:
        name = current.get('name')
        if name == 'awaiting_caption_text':
            context.user_data.pop('awaiting_caption_text', None)
            context.user_data.pop('pending_file_id', None)
            context.user_data.pop('pending_type', None)
        elif name == 'awaiting_buttons_for_post_id':
            context.user_data.pop('awaiting_buttons_for_post_id', None)
        elif name == 'creating_multipost':
            context.user_data.pop('creating_multipost', None)
            context.user_data.pop('multipost_list', None)
        elif name == 'editing_post':
            context.user_data.pop('editing_post', None)
        elif name == 'expecting_forward_for_add':
            context.user_data.pop('expecting_forward_for_add', None)
        elif name == 'awaiting_caption_text_multipost':
            context.user_data.pop('awaiting_caption_text_multipost', None)
            context.user_data.pop('pending_file_id', None)
            context.user_data.pop('pending_type', None)
        elif name == 'awaiting_buttons_for_multipost':
            context.user_data.pop('awaiting_buttons_for_multipost', None)

    if not prev:  
        await q.message.reply_text("↩️ আর কোন পূর্বের ধাপ নেই — মূল মেনুতে ফিরে গেলাম।", reply_markup=main_menu_kb())  
        clear_steps(context)  
        return  

    pname = prev.get('name')  
    info = prev.get('info', {})  
    if pname == 'creating_post':  
        await q.message.reply_text("📝 তুমি পোস্ট তৈরিতে আছ — মিডিয়া পাঠাও বা টেক্সট লিখে পাঠাও।", reply_markup=step_back_kb())  
    elif pname == 'awaiting_caption_choice':  
        await q.message.reply_text("📝 আপনি কি ক্যাপশন যোগ করতে চান?", reply_markup=InlineKeyboardMarkup([  
            [InlineKeyboardButton("✍️ Add Caption", callback_data="add_caption")],  
            [InlineKeyboardButton("⏭️ Skip (no caption)", callback_data="skip_caption")],  
            [InlineKeyboardButton("↩️ Back (one step)", callback_data="step_back")]  
        ]))  
    elif pname == 'awaiting_caption_text':  
        await q.message.reply_text("✍️ এখন ক্যাপশন লিখে পাঠান:", reply_markup=step_back_kb())  
    elif pname == 'awaiting_buttons_for_post_id':  
        pid = info.get('post_id')  
        await q.message.reply_text(f"✍️ এখন বাটন লাইন পাঠাও (পোস্ট আইডি: {pid})", reply_markup=step_back_kb())  
    elif pname == 'creating_multipost':  
        await q.message.reply_text(  
            "📝 নতুন পোস্ট তৈরি শুরু করো।\n\n"  
            "মিডিয়া (ছবি/ভিডিও/GIF) অথবা টেক্সট পাঠাও।\n"  
            "পোস্ট অটো সেভ হবে!",  
            parse_mode=ParseMode.MARKDOWN,  
            reply_markup=step_back_kb()  
        )  
    elif pname == 'awaiting_caption_choice_multipost':
        await q.message.reply_text("📝 আপনি কি ক্যাপশন যোগ করতে চান?", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✍️ Add Caption", callback_data="add_caption_multipost")],
            [InlineKeyboardButton("⏭️ Skip (no caption)", callback_data="skip_caption_multipost")],
            [InlineKeyboardButton("↩️ Back (one step)", callback_data="step_back")]
        ]))
    elif pname == 'awaiting_caption_text_multipost':
        await q.message.reply_text("✍️ এখন ক্যাপশন লিখে পাঠান:", reply_markup=step_back_kb())
    elif pname == 'awaiting_buttons_for_multipost':
        await q.message.reply_text(
            "✍️ এখন বাটন লাইন পাঠাও (উদাহরণ):\n"
            "`⎙ WATCH & DOWNLOAD ⎙ - https://t.me/fandub01 && 💬 GROUP - https://t.me/hindianime03`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=step_back_kb()
        )
    elif pname == 'editing_post':  
        pid = info.get('post_id')  
        await q.message.reply_text(f"✏️ নতুন টেক্সট বা বাটন লাইন পাঠাও (Edit Post {pid})", reply_markup=step_back_kb())  
    else:  
        await q.message.reply_text("↩️ পূর্বের ধাপে ফিরে এলাম।", reply_markup=main_menu_kb())

# -----------------------
# Delete flows
# -----------------------
async def menu_delete_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    kb = [
        [InlineKeyboardButton("🗑 Delete Post", callback_data="start_delete_post"),
         InlineKeyboardButton("🗑 Remove Channel", callback_data="start_delete_channel")],
        [InlineKeyboardButton("↩️ Back to Menu", callback_data="back_to_menu")]
    ]
    await q.message.reply_text("Delete options:", reply_markup=InlineKeyboardMarkup(kb))

async def start_delete_post_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    posts = load_json(POST_FILE)
    if not posts:
        await q.message.reply_text("No posts to delete.", reply_markup=back_to_menu_kb())
        return
    kb = [[InlineKeyboardButton(f"Del {p['id']}", callback_data=f"del_post_{p['id']}")] for p in posts]
    kb.append([InlineKeyboardButton("↩️ Back to Menu", callback_data="back_to_menu")])
    await q.message.reply_text("Choose post to delete:", reply_markup=InlineKeyboardMarkup(kb))

async def start_delete_channel_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    channels = load_json(CHANNEL_FILE)
    if not channels:
        await q.message.reply_text("No channels to remove.", reply_markup=back_to_menu_kb())
        return
    kb = [[InlineKeyboardButton(c['title'][:30], callback_data=f"remove_channel_{c['id']}")] for c in channels]
    kb.append([InlineKeyboardButton("↩️ Back to Menu", callback_data="back_to_menu")])
    await q.message.reply_text("Choose channel to remove:", reply_markup=InlineKeyboardMarkup(kb))

# -----------------------
# Handler registration
# -----------------------
def register_handlers(application):
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(menu_add_channel_cb, pattern="^menu_add_channel$"))
    application.add_handler(CallbackQueryHandler(menu_channel_list_cb, pattern="^menu_channel_list$"))
    application.add_handler(CallbackQueryHandler(menu_create_post_cb, pattern="^menu_create_post$"))
    application.add_handler(CallbackQueryHandler(menu_my_posts_cb, pattern="^menu_my_posts$"))
    application.add_handler(CallbackQueryHandler(menu_send_post_cb, pattern="^menu_send_post$"))
    application.add_handler(CallbackQueryHandler(menu_send_all_cb, pattern="^menu_send_all$"))
    application.add_handler(CallbackQueryHandler(menu_multipost_cb, pattern="^menu_multipost$"))
    application.add_handler(CallbackQueryHandler(menu_edit_post_cb, pattern="^menu_edit_post$"))
    application.add_handler(CallbackQueryHandler(menu_delete_cb, pattern="^menu_delete$"))
    application.add_handler(CallbackQueryHandler(menu_guide_cb, pattern="^menu_guide$"))
    application.add_handler(CallbackQueryHandler(back_to_menu_cb, pattern="^back_to_menu$"))
    application.add_handler(CallbackQueryHandler(view_channel_cb, pattern=r"^view_channel_"))
    application.add_handler(CallbackQueryHandler(remove_channel_cb, pattern=r"^remove_channel_"))
    application.add_handler(CallbackQueryHandler(view_post_cb, pattern=r"^view_post_"))
    application.add_handler(CallbackQueryHandler(del_post_cb, pattern=r"^del_post_"))
    application.add_handler(CallbackQueryHandler(choose_edit_post_cb, pattern=r"^edit_post_"))
    application.add_handler(CallbackQueryHandler(send_post_selected, pattern=r"^send_post_"))
    application.add_handler(CallbackQueryHandler(choose_all_cb, pattern=r"^choose_all_"))
    application.add_handler(CallbackQueryHandler(add_buttons_cb, pattern=r"^add_buttons_"))
    application.add_handler(CallbackQueryHandler(caption_choice_cb, pattern=r"^(add_caption|skip_caption)$"))
    application.add_handler(CallbackQueryHandler(start_delete_post_cb, pattern=r"^start_delete_post$"))
    application.add_handler(CallbackQueryHandler(start_delete_channel_cb, pattern=r"^start_delete_channel$"))
    application.add_handler(CallbackQueryHandler(generic_callback_cb, pattern=r"^(popup:|alert:|noop)"))
    application.add_handler(MessageHandler(filters.FORWARDED & filters.ChatType.PRIVATE, forward_handler))
    application.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.ANIMATION, media_handler))
    application.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, save_text_handler))
    application.add_handler(CallbackQueryHandler(step_back_cb, pattern=r"^step_back$"))
    application.add_handler(CallbackQueryHandler(send_all_posts_cb, pattern="^send_all_posts$"))
    application.add_handler(CallbackQueryHandler(caption_choice_multipost_cb, pattern=r"^(add_caption_multipost|skip_caption_multipost)$"))
    application.add_handler(CallbackQueryHandler(create_new_multipost_cb, pattern="^create_new_multipost$"))
    application.add_handler(CallbackQueryHandler(send_all_multipost_cb, pattern="^send_all_multipost$"))

# -----------------------
# Main
# -----------------------
def main():
    ensure_files()
    if not TOKEN:
        print("ERROR: BOT_TOKEN environment variable not set. Exiting.")
        return

    try:  
        application = Application.builder().token(TOKEN).build()  
        register_handlers(application)  
        print("✅ Bot started successfully!")  
        application.run_polling()  
    except Exception as e:  
        print(f"❌ Bot startup failed: {e}")  
        raise

if __name__ == "__main__":
    main()
