import asyncio
import os
import math
import yt_dlp
import re
import threading
import time
def keep_alive():
    while True:
        time.sleep(600) # ၁၀ မိနစ် တစ်ခါ စစ်ဆေးသည်
from flask import Flask

# ---------- Asyncio fix (Python 3.12+) ----------
try:
    asyncio.get_running_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

# ---------- Pyrogram ----------
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ---------- Web server (Koyeb health check) ----------
web_app = Flask(__name__)

@web_app.route("/")
def home():
    return "Android Mode Bot is running!"

threading.Thread(
    target=lambda: web_app.run(host="0.0.0.0", port=8080),
    daemon=True
).start()

# ---------- Configuration (ENV ONLY) ----------
API_ID = int(os.getenv("33140158"))
API_HASH = os.getenv("936e6187972a97c9f9b616516f24b61c")
BOT_TOKEN = os.getenv("8571685060:AAEYF82CrIqSaVVIEVedNV-iKXJc0D70LmE")

app = Client(
    "android_mode_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

user_data = {}

# ---------- Helpers ----------
def ensure_dirs():
    os.makedirs("downloads", exist_ok=True)

# ---------- Message handler ----------
@app.on_message(filters.private & filters.text)
async def main_handler(client, message):
    uid = message.from_user.id
    text = message.text.strip()

    # waiting for split count
    if uid in user_data and user_data[uid].get("step") == "wait_split":
        if text.isdigit():
            num = int(text)
            total = user_data[uid]["line_count"]
            per = math.ceil(total / num)

            summary = f"🎬 **{user_data[uid]['title']}**\n\n"
            for i in range(num):
                s = i * per + 1
                e = min((i + 1) * per, total)
                summary += f"({chr(97+i)}) {s} - {e}\n"

            await message.reply_text(summary)
            await start_final_process(client, message, uid)
            return

    # youtube link
    if text.startswith("http"):
        msg = await message.reply_text("🔎 Android mode ဖြင့် စစ်ဆေးနေသည်...")

        try:
            ydl_opts = {
    "cookies": "cookies.txt",
    "outtmpl": "downloads/%(title)s.%(ext)s",
    "format": f"bestvideo[height<={res}]+bestaudio/best",
    "quiet": True,
    "extractor_args": {
        "youtube": {"player_client": ["ios"]}
    }
}

            info = await asyncio.to_thread(
                lambda: yt_dlp.YoutubeDL(ydl_opts).extract_info(text, download=False)
            )

            user_data[uid] = {
                "url": text,
                "title": info.get("title"),
                "subs": info.get("subtitles", {})
            }

            buttons = [[
                InlineKeyboardButton("360p", callback_data="res_360"),
                InlineKeyboardButton("720p", callback_data="res_720"),
                InlineKeyboardButton("1080p", callback_data="res_1080"),
            ]]

            await msg.edit(
                f"🎬 **{info.get('title')}**\n\nResolution ရွေးပါ ⬇️",
                reply_markup=InlineKeyboardMarkup(buttons)
            )

        except Exception as e:
            await msg.edit(f"❌ Error: {e}")

# ---------- Resolution ----------
@app.on_callback_query(filters.regex("^res_"))
async def choose_res(_, cq):
    await cq.answer()
    uid = cq.from_user.id

    if uid not in user_data:
        await cq.message.edit("❌ Session expired. Link ပြန်ပို့ပါ")
        return

    res = cq.data.split("_")[1]
    user_data[uid]["res"] = res

    subs = user_data[uid]["subs"]

    if "en" in subs:
        user_data[uid]["selected_sub"] = "en"
        await proceed_to_sub_split(cq.message, uid)
    elif subs:
        buttons = [[InlineKeyboardButton(l, callback_data=f"sub_{l}")]
                   for l in list(subs.keys())[:10]]
        await cq.message.edit("Sub ရွေးပါ ⬇️", reply_markup=InlineKeyboardMarkup(buttons))
    else:
        user_data[uid]["selected_sub"] = None
        await proceed_to_sub_split(cq.message, uid)

# ---------- Subtitle ----------
@app.on_callback_query(filters.regex("^sub_"))
async def choose_sub(_, cq):
    await cq.answer()
    uid = cq.from_user.id
    user_data[uid]["selected_sub"] = cq.data.split("_")[1]
    await proceed_to_sub_split(cq.message, uid)

async def proceed_to_sub_split(message, uid):
    data = user_data[uid]
    line_count = 0

    if data.get("selected_sub"):
        ensure_dirs()
        srt_prefix = f"downloads/{uid}_subs"

        ydl_opts = {
            "skip_download": True,
            "writesubtitles": True,
            "subtitleslangs": [data["selected_sub"]],
            "outtmpl": srt_prefix,
            "postprocessors": [{
                "key": "FFmpegSubtitlesConvertor",
                "format": "srt"
            }],
            "extractor_args": {
                "youtube": {"player_client": ["android"]}
            }
        }

        try:
            await asyncio.to_thread(
                lambda: yt_dlp.YoutubeDL(ydl_opts).download([data["url"]])
            )

            for f in os.listdir("downloads"):
                if f.startswith(f"{uid}_subs") and f.endswith(".srt"):
                    path = f"downloads/{f}"
                    with open(path, encoding="utf-8") as s:
                        content = s.read()
                        line_count = len(
                            re.findall(r"\n\d+\n\d{2}:\d{2}:\d{2},\d{3}", content)
                        )
                    data["srt_path"] = path
                    break
        except:
            pass

    data["line_count"] = line_count
    data["step"] = "wait_split"

    await message.edit(
        f"📊 **{data['title']}**\n"
        f"စာကြောင်းရေ: `{line_count}`\n\n"
        f"ခွဲမည့် လူအရေအတွက် ပို့ပါ"
    )

# ---------- Download & Send ----------
async def start_final_process(client, message, uid):
    data = user_data[uid]
    ensure_dirs()

    status = await message.reply_text("📥 Downloading (iOS client)...")

    res = data.get("res", "720")

    ydl_opts = {
        "outtmpl": "downloads/%(title)s.%(ext)s",
        "format": f"bestvideo[height<={res}]+bestaudio/best",
        "quiet": True,
        "extractor_args": {
            "youtube": {"player_client": ["ios"]}
        }
    }

    try:
        info = await asyncio.to_thread(
            lambda: yt_dlp.YoutubeDL(ydl_opts).extract_info(
                data["url"], download=True
            )
        )

        video_path = yt_dlp.YoutubeDL(ydl_opts).prepare_filename(info)

        await status.edit("📤 Telegram သို့ တင်ပို့နေသည်...")
        await client.send_video(
            message.chat.id,
            video=video_path,
            caption=data["title"],
            supports_streaming=True
        )

    finally:
        if os.path.exists(video_path):
            os.remove(video_path)
        if data.get("srt_path") and os.path.exists(data["srt_path"]):
            os.remove(data["srt_path"])
        user_data.pop(uid, None)
        await status.delete()

# ---------- Run ----------
if __name__ == "__main__":
    print("✅ Android Mode Bot started")
    app.run()

