import asyncio
import html
import urllib.parse 
import aiohttp # ✅ Naya import API call ke liye
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from telegram.constants import ParseMode, ChatAction
from telegram.error import TelegramError

# Pyrogram Errors for Assistant
from pyrogram.errors import InviteRequestSent, UserAlreadyParticipant, UserNotParticipant

# Imports
from tools.controller import process_stream
from tools.stream import stop_stream, skip_stream, pause_stream, resume_stream, worker_app, play_stream
from tools.stream import LAST_MSG_ID, QUEUE_MSG_ID
from config import OWNER_NAME, ASSISTANT_ID, INSTAGRAM_LINK

# Database se status check karne ke liye
from tools.database import get_music_status 

# 🔥 TERA API LINK (Agar Cloudflare restart ho toh ye link change kar lena)
API_URL = "https://helped-vegetables-implement-newbie.trycloudflare.com"

# --- HELPER: PROGRESS BAR ---
def get_progress_bar(duration):
    try:
        return "◉————————————"
    except:
        return "◉—————————"

# --- PLAY COMMAND (/play) ---
async def play_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    # 🔥🔥 1. GLOBAL MUSIC CHECK (SABSE PEHLE YAHAN AAYEGA) 🔥🔥
    is_active, reason = await get_music_status()
    if not is_active:
        if reason:
            msg = await update.message.reply_text(f"🚧 **ᴍᴜsɪᴄ ɪs ᴏꜰꜰ!**\nReason: `{reason}`")
            await asyncio.sleep(4)
            await msg.delete()
            return
        else:
            return 
    # 🔥🔥 CHECK END 🔥🔥

    # 2. Auto-Delete Command
    try: await update.message.delete()
    except: pass

    if not context.args:
        temp = await context.bot.send_message(chat.id, "<blockquote>❌ <b>Usage:</b> /play [Song Name]</blockquote>", parse_mode=ParseMode.HTML)
        await asyncio.sleep(5)
        try: await temp.delete()
        except: pass
        return

    query = " ".join(context.args)

    # 3. Searching Message
    status_msg = await context.bot.send_message(
        chat.id,
        f"🍭",
        parse_mode=ParseMode.HTML
    )
    await context.bot.send_chat_action(chat_id=chat.id, action=ChatAction.TYPING)

    # --- 🔥 ROBUST ASSISTANT JOIN LOGIC ---
    try:
        try:
            assistant_member = await chat.get_member(int(ASSISTANT_ID))
            if assistant_member.status in ["kicked", "banned"]:
                await status_msg.edit_text(
                    f"<blockquote>❌ <b>ᴀssɪsᴛᴀɴᴛ ʙᴀɴɴᴇᴅ</b></blockquote>\nAssistant is banned in {chat.title}.\nUnban it to play music.",
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🗑 ᴄʟᴏsᴇ", callback_data="force_close")]])
                )
                return
        except: pass

        try:
            try:
                invite_link = await context.bot.export_chat_invite_link(chat.id)
            except:
                await status_msg.edit_text("<blockquote>⚠️ <b>Admin Rights Needed!</b>\nI need 'Invite Users' permission to add Assistant.</blockquote>", parse_mode=ParseMode.HTML)
                return

            if "+" in invite_link:
                try:
                    link_hash = invite_link.split("+")[1]
                    invite_link = f"https://t.me/joinchat/{link_hash}"
                except: pass

            await worker_app.join_chat(invite_link)

        except UserAlreadyParticipant:
            pass 
        
        except InviteRequestSent:
            try:
                await context.bot.approve_chat_join_request(chat_id=chat.id, user_id=int(ASSISTANT_ID))
                await asyncio.sleep(2) 
            except Exception as e:
                await status_msg.edit_text(f"<blockquote>⚠️ <b>Join Request Pending</b>\nAccept the join request of Assistant manually.</blockquote>", parse_mode=ParseMode.HTML)
                return
        
        except Exception as e:
            print(f"⚠️ Join Error: {e}")

    except Exception as e:
        print(f"Main Join Logic Error: {e}")

    # --- CONTROLLER LOGIC ---
    error, data = await process_stream(chat.id, user.first_name, query)

    if error:
        await status_msg.edit_text(
            f"<blockquote>❌ <b>ᴇʀʀᴏʀ</b></blockquote>\n{error}",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🗑 ᴄʟᴏsᴇ", callback_data="force_close")]])
        )
        return

    # Data Extract
    raw_title = data["title"]
    safe_title = html.escape(raw_title[:30] + "..." if len(raw_title) > 30 else raw_title)
    safe_user = html.escape(data["user"])
    duration = data["duration"]
    link = data["link"]
    img_url = data.get("thumbnail", data.get("img_url"))

    bar_display = get_progress_bar(duration)

    # 🔥 BUTTONS
    buttons = [
        [InlineKeyboardButton(f"00:00 {bar_display} {duration}", callback_data="GetTimer")],
        [
            InlineKeyboardButton("II", callback_data="music_pause"),
            InlineKeyboardButton("▶", callback_data="music_resume"),
            InlineKeyboardButton("‣‣I", callback_data="music_skip"),
            InlineKeyboardButton("▢", callback_data="music_stop")
        ],
        [
            InlineKeyboardButton("🍫 ʏᴏᴜᴛᴜʙᴇ", url=link),
            InlineKeyboardButton(f"🍷 ꜱᴜᴘᴘᴏʀᴛ", url=INSTAGRAM_LINK)
        ],
        [InlineKeyboardButton("🗑 ᴄʟᴏsᴇ ᴘʟᴀʏᴇʀ", callback_data="force_close")]
    ]
    markup = InlineKeyboardMarkup(buttons)

    try: await status_msg.delete()
    except: pass

    # Caption Logic
    if data["status"] is True: 
        if chat.id in LAST_MSG_ID:
            try: await context.bot.delete_message(chat.id, LAST_MSG_ID[chat.id])
            except: pass
        
        caption = f"""
<blockquote><b>✅ sᴛᴀʀᴛᴇᴅ sᴛʀᴇᴀᴍɪɴɢ</b></blockquote>

<blockquote><b>🫀ᴛɪᴛʟᴇ :</b> <a href="{link}">{safe_title}</a>
<b>🍁 ᴅᴜʀᴀᴛɪᴏɴ :</b> <code>{duration}</code>
<b>🫧 ʀᴇǫᴜᴇsᴛᴇᴅ ʙʏ :</b> {safe_user}</blockquote>
<blockquote><b>🍫ᴘᴏᴡᴇʀᴇᴅ ʙʏ :</b> {OWNER_NAME}</blockquote>
"""
        try:
            msg = await context.bot.send_photo(chat.id, photo=img_url, caption=caption, has_spoiler=True, reply_markup=markup, parse_mode=ParseMode.HTML)
            LAST_MSG_ID[chat.id] = msg.message_id
        except: pass

    else: 
        caption = f"""
<blockquote><b>📝 ᴀᴅᴅᴇᴅ ᴛᴏ ǫᴜᴇᴜᴇ</b></blockquote>

<blockquote><b>🎸 ᴛɪᴛʟᴇ :</b> <a href="{link}">{safe_title}</a>
<b>🍫 ᴘᴏsɪᴛɪᴏɴ :</b> <code>#{data['position']}</code>
<b>🍁 ᴅᴜʀᴀᴛɪᴏɴ :</b> <code>{duration}</code>
<b>🫧 ʀᴇǫᴜᴇsᴛᴇᴅ ʙʏ :</b> {safe_user}</blockquote>
<blockquote><b>🍫ᴘᴏᴡᴇʀᴇᴅ ʙʏ :</b> {OWNER_NAME}</blockquote>
"""
        try:
            q_msg = await context.bot.send_photo(chat.id, photo=img_url, caption=caption, has_spoiler=True, reply_markup=markup, parse_mode=ParseMode.HTML)
            QUEUE_MSG_ID[f"{chat.id}-{safe_title}"] = q_msg.message_id
        except: pass

# --- UNBAN CALLBACK ---
async def unban_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat = update.effective_chat
    user = await chat.get_member(query.from_user.id)
    if user.status not in ["creator", "administrator"]:
        return await query.answer("❌ Only Admins can unban!", show_alert=True)
    try:
        await chat.unban_member(int(ASSISTANT_ID))
        await query.message.edit_text("<blockquote>✅ <b>Assistant Unbanned!</b></blockquote>", parse_mode=ParseMode.HTML)
    except Exception as e:
        await query.answer(f"Error: {e}", show_alert=True)

# --- COMMANDS ---
async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    command = update.message.text.split()[0].replace("/", "").lower()
    try: await update.message.delete()
    except: pass
    
    msg_text = ""
    if command in ["stop", "end"]:
        await stop_stream(chat_id)
        msg_text = "<blockquote>⏹ <b>sᴛʀᴇᴀᴍ sᴛᴏᴘᴘᴇᴅ</b></blockquote>"
    elif command in ["skip", "next"]:
        await skip_stream(chat_id)
        msg_text = "<blockquote>⏭ <b>sᴋɪᴘᴘᴇᴅ</b></blockquote>"
    elif command == "pause":
        await pause_stream(chat_id)
        msg_text = "<blockquote>II <b>sᴛʀᴇᴀᴍ ᴘᴀᴜsᴇᴅ</b></blockquote>"
    elif command == "resume":
        await resume_stream(chat_id)
        msg_text = "<blockquote>▶ <b>sᴛʀᴇᴀᴍ ʀᴇsᴜᴍᴇᴅ</b></blockquote>"

    if chat_id in LAST_MSG_ID:
        try: await context.bot.delete_message(chat_id, LAST_MSG_ID[chat_id])
        except: pass

    temp = await context.bot.send_message(chat_id, msg_text, parse_mode=ParseMode.HTML)
    await asyncio.sleep(4)
    try: await temp.delete()
    except: pass

# 🔥🔥 --- THE API TV COMMAND --- 🔥🔥
async def test_direct_tv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    try: await update.message.delete()
    except: pass

    status_msg = await context.bot.send_message(
        chat.id, 
        "<blockquote>🔄 <b>[1/2] API sᴇ Lɪᴠᴇ TV ᴍᴀɴɢᴡᴀ ʀᴀʜᴀ ʜᴜ... (Wᴀɪᴛ 2s)</b></blockquote>", 
        parse_mode=ParseMode.HTML
    )
    
    try:
        # Bot API se bolega: "Bhai TV ki file de!"
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{API_URL}/get_tv") as resp:
                data = await resp.json()
                
        if data.get("status") == "success":
            stream_url = data["url"]
            await status_msg.edit_text("<blockquote>✅ <b>[2/2] Fɪʟᴇ Mɪʟ Gᴀʏɪ! VC ᴍᴇɪɴ Pʟᴀʏ ᴋᴀʀ ʀᴀʜᴀ ʜᴜ...</b></blockquote>", parse_mode=ParseMode.HTML)
            
            # Bot us file ko VC mein baja dega
            status, position = await play_stream(
                chat_id=chat.id, 
                file_path=stream_url, 
                title="📺 Aaj Tak (API Mode)", 
                duration="Live API", 
                user=user.first_name, 
                link=API_URL, 
                thumbnail=None
            )
            
            if status:
                await status_msg.edit_text("<blockquote>✅ <b>API TV sᴛʀᴇᴀᴍ sᴛᴀʀᴛᴇᴅ!</b>\n\nAb ye khud Auto-Loop mein chalta rahega!</blockquote>", parse_mode=ParseMode.HTML)
            else:
                await status_msg.edit_text(f"<blockquote>❌ <b>Pʟᴀʏ Eʀʀᴏʀ:</b> {position}</blockquote>", parse_mode=ParseMode.HTML)
        else:
            await status_msg.edit_text(f"<blockquote>❌ <b>API Eʀʀᴏʀ:</b> {data.get('message')}</blockquote>", parse_mode=ParseMode.HTML)
            
    except Exception as e:
        await status_msg.edit_text(f"<blockquote>❌ <b>Bᴏᴛ Eʀʀᴏʀ:</b> <code>{e}</code></blockquote>", parse_mode=ParseMode.HTML)


def register_handlers(app):
    app.add_handler(CommandHandler(["play", "p"], play_command))
    app.add_handler(CommandHandler(["stop", "end", "skip", "next", "pause", "resume"], stop_command))
    app.add_handler(CommandHandler(["testtv"], test_direct_tv)) # ✅ REGISTERED THE API COMMAND
    app.add_handler(CallbackQueryHandler(unban_cb, pattern="unban_assistant"))
    print("  ✅ Music Module Loaded: Auto-Join & Anti-Ban & API Auto-Loop TV!")
            
