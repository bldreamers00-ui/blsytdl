import os
import math
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from yt_dlp import YoutubeDL

# ================= CONFIG =================
API_ID = 33140158
API_HASH = "936e6187972a97c9f9b616516f24b61c"
BOT_TOKEN = "8436731415:AAElimTsJtpW8sh6xtV2JDcC6k3Y_woRHtY"

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

app = Client(
    "bot3_session_clean",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ================= STATE =================
user_links = {}
subtitle_state = {}

# ================= UI =================
def resolution_kb():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("360p", callback_data="res_360"),
                InlineKeyboardButton("720p", callback_data="res_720"),
            ]
        ]
    )

def split_lines(lines, parts):
    total = len(lines)
    size = math.ceil(total / parts)
    result = []
    start = 0
    for _ in range(parts):
        end = min(start + size, total)
        result.append((start + 1, end))
        start = end
    return result

# ================= HANDLERS =================

@app.on_message(filters.command("start"))
async def start(_, msg):
    await msg.reply(
        "🎬 **BLSFLIX Downloader**\n\n"
        "YouTube link ပို့ပါ 👇"
    )

@app.on_message(filters.text)
async def text_handler(_, msg):
    user_id = msg.from_user.id
    text = msg.text.strip()

    # YouTube link
    if text.startswith("http"):
        user_links[user_id] = text
        await msg.reply("📺 Resolution ရွေးပါ 👇", reply_markup=resolution_kb())
        return

    # subtitle split number
    if text.isdigit() and user_id in subtitle_state:
        data = subtitle_state.pop(user_id)
        parts = int(text)
        ranges = split_lines(data["lines"], parts)

        out = f"🎬 {data['title']}\nTotal lines: {len(data['lines'])}\n\n"
        for i, (s, e) in enumerate(ranges, 1):
            out += f"{i}. {s} - {e}\n"

        await msg.reply(out)

@app.on_callback_query(filters.regex("^res_"))
async def resolution_handler(_, cq):
    user_id = cq.from_user.id
    res = cq.data.split("_")[1]
    url = user_links.get(user_id)

    if not url:
        await cq.answer("Link မတွေ့ပါ", show_alert=True)
        return

    await cq.answer()
    status = await cq.message.reply("📥 Downloading...")

    ydl_opts = {
        "outtmpl": f"{DOWNLOAD_DIR}/%(title)s.%(ext)s",
        "format": f"bestvideo[height<={res}]+bestaudio/best",
        "merge_output_format": "mp4",
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitlesformat": "srt",
        "noplaylist": True,
        "extractor_args": {
            "youtube": {
                "player_client": ["android_vr"]
            }
        }
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "video")
            video_path = ydl.prepare_filename(info).rsplit(".", 1)[0] + ".mp4"

        await status.edit("📤 Uploading...")

        await cq.message.reply_video(
            video=video_path,
            caption=f"🎬 {title}\n📺 {res}p",
            duration=info.get("duration", 0),
            width=info.get("width", 0),
            height=info.get("height", 0),
        )

        subs = info.get("requested_subtitles") or {}
        if subs:
            lang, data = list(subs.items())[0]
            srt_path = data["filepath"]

            await cq.message.reply_document(
                srt_path,
                caption=f"📄 Subtitle ({lang})"
            )

            with open(srt_path, encoding="utf-8", errors="ignore") as f:
                raw = f.read().splitlines()

            lines = [l for l in raw if l and "-->" not in l and not l.isdigit()]

            subtitle_state[user_id] = {
                "title": title,
                "lines": lines
            }

            await cq.message.reply(
                f"✅ Subtitle ရပါပြီ\n"
                f"Total lines: {len(lines)}\n"
                f"ဘယ်နှစ်ပိုင်း ခွဲမလဲ? (ဂဏန်းပို့ပါ)"
            )

        await status.delete()
        if os.path.exists(video_path):
            os.remove(video_path)

    except Exception as e:
        await status.edit(f"❌ Error:\n{e}")

# ================= RUN =================
print("🤖 Bot started…")
app.run()
