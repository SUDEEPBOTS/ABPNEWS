import asyncio
import os
from tools.queue import put_queue

# TV ke chunks save karne ke liye folder
TV_DIR = "tv_chunks"
os.makedirs(TV_DIR, exist_ok=True)

async def record_chunk(m3u8_url, duration_sec, filename):
    out_path = os.path.join(TV_DIR, f"{filename}.ts")
    print(f"🎥 [TV RECORDER] Recording {filename} ({duration_sec}s)...")
    
    cmd = [
        "ffmpeg", "-y", 
        "-headers", "Referer: https://aajtak.in/\r\n",
        "-user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
        "-i", m3u8_url,
        "-t", str(duration_sec),
        "-c", "copy",
        out_path
    ]
    
    process = await asyncio.create_subprocess_exec(
        *cmd, 
        stdout=asyncio.subprocess.PIPE, 
        stderr=asyncio.subprocess.PIPE
    )
    
    stdout, stderr = await process.communicate()
    
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        print(f"✅ [TV RECORDER] Ready: {out_path}")
        return out_path
    else:
        # 🔥 FIX: Ab dono logs (Output aur Error) capture honge!
        out_log = stdout.decode('utf-8', errors='ignore').strip()
        err_log = stderr.decode('utf-8', errors='ignore').strip()
        print(f"❌ [FFMPEG ERROR] Return Code: {process.returncode}")
        if out_log: print(f"👉 STDOUT: {out_log[-1000:]}") 
        if err_log: print(f"👉 STDERR: {err_log[-1000:]}")
        return None
        

async def continuous_tv_recorder(chat_id, m3u8_url, user_name):
    """Background loop jo har 5 minute mein chunk record karke queue me dalega"""
    chunk_names = ["chunk_A", "chunk_B"]
    toggle = 0
    segment_count = 1
    duration = 300 # 5 minutes (300 seconds)
    
    while True:
        # A aur B ke beech toggle karega
        current_filename = f"{chunk_names[toggle]}_{chat_id}"
        
        # 5 minute ka agla chunk record karo
        file_path = await record_chunk(m3u8_url, duration, current_filename)
        
        if file_path:
            # Record hone ke baad chup-chaap Queue mein daal do
            await put_queue(
                chat_id=chat_id, 
                file_path=file_path, 
                title=f"📺 Live TV Seg-{segment_count} (5 Mins)", 
                duration="05:00", 
                user=user_name, 
                link=m3u8_url, 
                thumbnail=None
            )
            print(f"📥 [QUEUE] Seg-{segment_count} Added to Queue!")
            segment_count += 1
            toggle = 1 if toggle == 0 else 0 # Flip A to B, B to A
        else:
            print("❌ [TV RECORDER] Stream record fail hui. Retrying in 5s...")
            await asyncio.sleep(5)
            
