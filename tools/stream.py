import asyncio
import os
import subprocess # ✅ Naya import FIFO pipe ke FFmpeg ke liye
import html 
import aiohttp # ✅ API call ke liye
from pytgcalls import PyTgCalls, idle
from pytgcalls.types import AudioPiped, AudioVideoPiped, Update, HighQualityAudio, MediumQualityVideo
from telegram import Bot, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from pyrogram import Client

from config import API_ID, API_HASH, SESSION, BOT_TOKEN, OWNER_NAME, INSTAGRAM_LINK
from tools.queue import put_queue, pop_queue, clear_queue, get_queue
from tools.database import add_active_chat, remove_active_chat

LAST_MSG_ID = {}   
QUEUE_MSG_ID = {}
TV_CHATS = set() # ✅ Global TV Tracker

API_URL = "https://helped-vegetables-implement-newbie.trycloudflare.com"

print("🟡 [STREAM] Loading Music Module...")
worker_app = None
worker = None

try:
    if SESSION:
        worker_app = Client("MusicWorker", api_id=API_ID, api_hash=API_HASH, session_string=SESSION, in_memory=True)
        worker = PyTgCalls(worker_app)
        print("✅ [STREAM] Music Client Loaded Successfully!")
    else:
        print("⚠️ [STREAM] Session String Missing! Music will not work.")
except Exception as e:
    print(f"❌ [STREAM ERROR] Client Load Failed: {e}")

main_bot = Bot(token=BOT_TOKEN)

def get_progress_bar(duration):
    return "◉————————————"

async def send_now_playing(chat_id, song_data):
    try:
        if chat_id in LAST_MSG_ID:
            try: await main_bot.delete_message(chat_id, LAST_MSG_ID[chat_id])
            except: pass
        
        title = html.escape(str(song_data["title"]))
        user = html.escape(str(song_data["by"]))
        duration = str(song_data["duration"])
        link = song_data["link"]
        thumbnail = song_data.get("thumbnail")

        display_title = title[:30] + "..." if len(title) > 30 else title
        bar_display = get_progress_bar(duration)

        buttons = [
            [InlineKeyboardButton(f"⏳ {duration}", callback_data="GetTimer")],
            [
                InlineKeyboardButton("II", callback_data="music_pause"),
                InlineKeyboardButton("▶", callback_data="music_resume"),
                InlineKeyboardButton("‣‣I", callback_data="music_skip"),
                InlineKeyboardButton("▢", callback_data="music_stop")
            ],
            [
                InlineKeyboardButton("📺 ʏᴏᴜᴛᴜʙᴇ", url=link),
                InlineKeyboardButton("📸 ɪɴsᴛᴀɢʀᴀᴍ", url=INSTAGRAM_LINK)
            ],
            [InlineKeyboardButton("🗑 ᴄʟᴏsᴇ ᴘʟᴀʏᴇʀ", callback_data="force_close")]
        ]
        
        caption = f"""
<b>✅ sᴛᴀʀᴛᴇᴅ sᴛʀᴇᴀᴍɪɴɢ</b>
<blockquote><b>🎸 ᴛɪᴛʟᴇ :</b> <a href="{link}">{display_title}</a>
<b>⏳ ᴅᴜʀᴀᴛɪᴏɴ :</b> <code>{duration}</code>
<b>👤 ʀᴇǫᴜᴇsᴛᴇᴅ ʙʏ :</b> {user}</blockquote>
{bar_display}
<blockquote><b>⚡ ᴘᴏᴡᴇʀᴇᴅ ʙʏ :</b> {OWNER_NAME}</blockquote>
"""
        msg = await main_bot.send_photo(
            chat_id,
            photo=thumbnail if thumbnail else "https://telegra.ph/file/default_image.png",
            caption=caption,
            has_spoiler=True, 
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML
        )
        LAST_MSG_ID[chat_id] = msg.message_id
        return True
    except Exception as e:
        print(f"⚠️ [UI ERROR] Message nahi gaya: {e}")
        return False

async def start_music_worker():
    print("🔵 Starting Music Assistant...")
    if not worker: return
    try:
        if not worker_app.is_connected:
            await worker_app.start()
        try: await worker.start()
        except: pass
        print("✅ Assistant Started!")
    except Exception as e:
        print(f"❌ Assistant Error: {e}")

async def play_stream(chat_id, file_path, title, duration, user, link, thumbnail):
    if not worker: return None, "Music System Error"

    # ==========================================
    # 🔥 HELLFIREDEVS FIFO PIPE BYPASS 🔥
    # ==========================================
    if file_path == "test1":
        print("🧪 [TEST 1] Triggering Local Holographic Pipe (Gapless Live TV)...")
        pipe_path = "aajtak_live.ts"
        
        if os.path.exists(pipe_path):
            try: os.remove(pipe_path)
            except: pass
            
        os.mkfifo(pipe_path)
        
        master_url = "https://aajtaklive-amd.akamaized.net/hls/live/2014416/aajtak/aajtaklive/live_360p/chunks.m3u8"
        
        cmd = [
            "ffmpeg", "-y",
            "-headers", "Referer: https://aajtak.in/\r\nOrigin: https://aajtak.in/\r\n",
            "-user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
            "-i", master_url,
            "-c", "copy",
            "-f", "mpegts",
            pipe_path
        ]
        # FFmpeg background mein pipe mein video dalna shuru kar dega
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        file_path = pipe_path
        title = "🔴 Aaj Tak (FIFO Stream)"
        duration = "Live"
        link = "https://aajtak.in"
    # ==========================================

    # ✅ Check if it's TV Mode
    if "API Mode" in title:
        TV_CHATS.add(chat_id)
    else:
        if chat_id in TV_CHATS:
            TV_CHATS.remove(chat_id)

    stream = AudioVideoPiped(file_path, audio_parameters=HighQualityAudio(), video_parameters=MediumQualityVideo())

    try:
        position = await put_queue(chat_id, file_path, title, duration, user, link, thumbnail)
        
        is_active = False
        try:
            for call in worker.active_calls:
                if call.chat_id == chat_id:
                    is_active = True
                    break
        except: pass

        if is_active and chat_id in LAST_MSG_ID:
            return False, position

        elif is_active and chat_id not in LAST_MSG_ID:
            try:
                await worker.change_stream(int(chat_id), stream)
            except:
                try: await worker.leave_group_call(int(chat_id))
                except: pass
                await asyncio.sleep(0.5)
                await worker.join_group_call(int(chat_id), stream)
        else:
            try: await worker.leave_group_call(int(chat_id))
            except: pass
            await asyncio.sleep(0.5)
            await worker.join_group_call(int(chat_id), stream)
            await add_active_chat(chat_id)
            
        song_data = {"title": title, "duration": duration, "by": user, "link": link, "thumbnail": thumbnail}
        await send_now_playing(chat_id, song_data)
        return True, 0
    except Exception as e:
        print(f"❌ [PYTGCALLS ERROR] {e}")
        return None, str(e)

if worker:
    @worker.on_stream_end()
    async def stream_end_handler(client, update: Update):
        chat_id = update.chat_id
        
        await asyncio.sleep(1)
        await pop_queue(chat_id)
        queue = await get_queue(chat_id)
        
        if queue and len(queue) > 0:
            if chat_id in LAST_MSG_ID:
                try: await main_bot.delete_message(chat_id, LAST_MSG_ID[chat_id])
                except: pass 
                del LAST_MSG_ID[chat_id]

            next_song = queue[0]
            stream = AudioVideoPiped(next_song["file"], audio_parameters=HighQualityAudio(), video_parameters=MediumQualityVideo())
            try:
                await worker.change_stream(chat_id, stream)
            except:
                try: await worker.leave_group_call(chat_id)
                except: pass
                await asyncio.sleep(0.5)
                await worker.join_group_call(chat_id, stream)
            await send_now_playing(chat_id, next_song)
        else:
            # 🔥 THE API AUTO-LOOP MAGIC 🔥
            if chat_id in TV_CHATS:
                print(f"🔄 [BOT] TV File khatam! API se dusri mangwa raha hu... Chat: {chat_id}")
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(f"{API_URL}/get_tv") as resp:
                            data = await resp.json()
                            
                    if data.get("status") == "success":
                        stream_url = data["url"]
                        stream = AudioVideoPiped(stream_url, audio_parameters=HighQualityAudio(), video_parameters=MediumQualityVideo())
                        await worker.change_stream(chat_id, stream)
                        print("✅ [BOT] Nayi TV file chalu!")
                        return # Loop zinda rahega!
                except Exception as e:
                    print(f"❌ Next TV fetch fail: {e}")
            
            # Agar TV_CHATS mein nahi hai ya API fail ho gayi
            if chat_id in LAST_MSG_ID:
                try: await main_bot.delete_message(chat_id, LAST_MSG_ID[chat_id])
                except: pass 
                del LAST_MSG_ID[chat_id]
            print(f"✅ Queue Empty for {chat_id}, Leaving VC.")
            await stop_stream(chat_id)

async def skip_stream(chat_id):
    if not worker: return False
    if chat_id in LAST_MSG_ID:
        try: await main_bot.delete_message(chat_id, LAST_MSG_ID[chat_id])
        except: pass
        if chat_id in LAST_MSG_ID: del LAST_MSG_ID[chat_id]

    await pop_queue(chat_id)
    queue = await get_queue(chat_id)
    if queue and len(queue) > 0:
        next_song = queue[0]
        try:
            stream = AudioVideoPiped(next_song["file"], audio_parameters=HighQualityAudio(), video_parameters=MediumQualityVideo())
            await worker.change_stream(chat_id, stream)
            await send_now_playing(chat_id, next_song)
            return True 
        except Exception as e:
            await stop_stream(chat_id)
            return False
    else:
        await stop_stream(chat_id)
        return False

async def stop_stream(chat_id):
    if not worker: return False
    try:
        if chat_id in TV_CHATS:
            TV_CHATS.remove(chat_id)
            
        await worker.leave_group_call(int(chat_id))
        await remove_active_chat(chat_id)
        await clear_queue(chat_id)
        if chat_id in LAST_MSG_ID:
            try: await main_bot.delete_message(chat_id, LAST_MSG_ID[chat_id])
            except: pass
            del LAST_MSG_ID[chat_id]
        return True
    except: return False

async def pause_stream(chat_id):
    if not worker: return False
    try: await worker.pause_stream(chat_id); return True
    except: return False

async def resume_stream(chat_id):
    if not worker: return False
    try: await worker.resume_stream(chat_id); return True
    except: return False

async def get_current_playing(chat_id):
    queue = await get_queue(chat_id)
    if queue and len(queue) > 0: return queue[0]
    return None
    
