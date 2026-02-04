import os
import math
import asyncio
import threading
import re
from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from yt_dlp import YoutubeDL

# --- 1. Asyncio Loop Fix ---
try:
    asyncio.get_running_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

# --- 2. Configuration ---
API_ID = 33140158
API_HASH = "936e6187972a97c9f9b616516f24b61c"
BOT_TOKEN = "8436731415:AAElimTsJtpW8sh6xtV2JDcC6k3Y_woRHtY"

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

app = Client("blsflix_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
user_links = {}
subtitle_state = {}

# --- 3. Health Check Section ---
web_app = Flask(__name__)
@web_app.route('/')
def home(): return "Bot is Alive!"

def run_flask():
    # Koyeb ရဲ့ PORT ကို သုံးဖို့ သေချာပြင်ထားပါတယ်
    port = int(os.environ.get("PORT", 8000))
    web_app.run(host='0.0.0.0', port=port)

# --- 4. Handlers (မပြောင်းလဲပါ) ---
@app.on_message(filters.command("start"))
async def start(_, msg):
    await msg.reply("🎬 **BLSFLIX Downloader**\n\nYouTube link ပို့ပေးပါဗျ 👇")

@app.on_message(filters.text & filters.private)
async def text_handler(_, msg):
    user_id = msg.from_user.id
    text = msg.text.strip()
    if text.startswith("http"):
        user_links[user_id] = text
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("360p", callback_data="res_360"),
            InlineKeyboardButton("720p", callback_data="res_720"),
            InlineKeyboardButton("1080p", callback_data="res_1080")
        ]])
        await msg.reply("📺 Resolution ရွေးပေးပါ 👇", reply_markup=kb)
    elif text.isdigit() and user_id in subtitle_state:
        data = subtitle_state.pop(user_id)
        parts = int(text)
        total = len(data["lines"])
        size = math.ceil(total / parts)
        out = f"🎬 **{data['title']}**\nစုစုပေါင်းစာကြောင်း: ({total})\n\n"
        for i in range(parts):
            start, end = (i * size) + 1, min((i + 1) * size, total)
            out += f"({chr(97+i)}) {start} - {end}\n"
        await msg.reply(out)

@app.on_callback_query(filters.regex("^res_"))
async def resolution_handler(_, cq):
    user_id = cq.from_user.id
    res = cq.data.split("_")[1]
    url = user_links.get(user_id)
    if not url: return await cq.answer("❌ Link မတွေ့ပါ", show_alert=True)
    await cq.answer()
    status = await cq.message.reply(f"📥 {res}p ဖြင့် ဒေါင်းလုဒ်ဆွဲနေသည်...")
    ydl_opts = {
        "outtmpl": f"{DOWNLOAD_DIR}/%(title)s.%(ext)s",
        "format": f"bestvideo[height<={res}][ext=mp4]+bestaudio[ext=m4a]/best[height<={res}][ext=mp4]/best",
        "merge_output_format": "mp4", "writesubtitles": True, "subtitlesformat": "srt",
        "quiet": True, "extractor_args": {"youtube": {"player_client": ["android_vr"]}},
        "nocheckcertificate": True
    }
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = await asyncio.to_thread(lambda: ydl.extract_info(url, download=True))
            video_path = ydl.prepare_filename(info)
        await status.edit("📤 Telegram သို့ တင်ပို့နေသည်...")
        await cq.message.reply_video(video=video_path, caption=f"🎬 **{info.get('title')}**\n📺 {res}p", supports_streaming=True)
        # Subtitle logic
        subs = info.get("requested_subtitles") or {}
        if subs:
            lang = list(subs.keys())[0]
            srt_path = subs[lang]["filepath"]
            with open(srt_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = re.findall(r'\d+\n\d{2}:\d{2}:\d{2}', f.read())
            subtitle_state[user_id] = {"title": info.get('title'), "lines": lines}
            await cq.message.reply_document(srt_path, caption=f"📄 Subtitle ({lang})")
            await cq.message.reply(f"✅ စာကြောင်းရေ: ({len(lines)})\nဘယ်နှစ်ပိုင်း ခွဲမလဲ? (ဂဏန်းပို့ပါ)")
        await status.delete()
        if os.path.exists(video_path): os.remove(video_path)
    except Exception as e: await status.edit(f"❌ Error: {str(e)}")

# --- 5. Main Execution (Koyeb Fix) ---
if __name__ == "__main__":
    # Flask ကို background မှာ run ပါမယ်
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()
    
    # Bot ကို main thread မှာ run ပါမယ်
    print("🚀 Bot is starting...")
    app.run()
