import asyncio
import os
import math
import yt_dlp
import re
import threading
from flask import Flask

# --- 1. Python 3.12+ Asyncio Fix ---
try:
    asyncio.get_running_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

# --- 2. Pyrogram Imports ---
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- 3. Web Server (For Koyeb Health Check) ---
web_app = Flask(__name__)
@web_app.route('/')
def home(): return "Android Mode Bot is running!"
threading.Thread(target=lambda: web_app.run(host='0.0.0.0', port=8000), daemon=True).start()

# --- 4. Configuration ---
API_ID = 33140158
API_HASH = "936e6187972a97c9f9b616516f24b61c"
BOT_TOKEN = "8571685060:AAFJyzZ6CF150w51k0ft_PHXgUJPaaPJg6I"

app = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
user_data = {}

# --- 5. Handlers ---
@app.on_message(filters.text & filters.private)
async def main_handler(client, message):
    uid = message.from_user.id
    text = message.text

    if uid in user_data and user_data[uid].get('step') == 'wait_split':
        if text.isdigit() and 'line_count' in user_data[uid]:
            num = int(text)
            total = user_data[uid]['line_count']
            per_person = math.ceil(total / num)
            summary = f"🎬 **{user_data[uid]['title']}**\n\n"
            for i in range(num):
                start, end = (i * per_person) + 1, min((i + 1) * per_person, total)
                summary += f"({chr(97+i)}) {start} - {end}\n"
            await message.reply_text(summary)
            user_data[uid]['step'] = 'processing'
            await start_final_process(client, message, uid)
            return

    if text.startswith("http"):
        msg = await message.reply_text("🔎 Android Mode ဖြင့် စစ်ဆေးနေသည်...")
        try:
            # Android Player Client ကို အသုံးပြုရန် သတ်မှတ်ခြင်း
            ydl_opts = {
                'quiet': True,
                'extractor_args': {'youtube': {'player_client': ['android']}},
                'nocheckcertificate': True
            }
            info = await asyncio.to_thread(lambda: yt_dlp.YoutubeDL(ydl_opts).extract_info(text, download=False))
            user_data[uid] = {'url': text, 'title': info.get('title'), 'subs': info.get('subtitles', {})}
            buttons = [[InlineKeyboardButton(r, callback_data=f"res_{r}") for r in ["360", "720", "1080"]]]
            await msg.edit(f"🎬 **{user_data[uid]['title']}**\n\nResolution ရွေးပါ-", reply_markup=InlineKeyboardMarkup(buttons))
        except Exception as e:
            await msg.edit(f"❌ Error: {str(e)}")

@app.on_callback_query(filters.regex("^res_"))
async def choose_res(client, callback_query):
    await callback_query.answer()
    uid = callback_query.from_user.id
    if uid not in user_data:
        await callback_query.message.edit("❌ Session Expired. Link ပြန်ပို့ပါ။")
        return
    user_data[uid]['res'] = callback_query.data.split("_")[1]
    
    subs = user_data[uid]['subs']
    if 'en' in subs:
        user_data[uid]['selected_sub'] = 'en'
        await proceed_to_sub_split(callback_query.message, uid)
    else:
        sub_langs = list(subs.keys())[:10]
        if not sub_langs:
            user_data[uid]['selected_sub'] = None
            await proceed_to_sub_split(callback_query.message, uid)
        else:
            sub_buttons = [[InlineKeyboardButton(l, callback_data=f"sub_{l}")] for l in sub_langs]
            await callback_query.message.edit("Sub ရွေးပါ-", reply_markup=InlineKeyboardMarkup(sub_buttons))

async def proceed_to_sub_split(message, uid):
    data = user_data[uid]
    lang, line_count = data.get('selected_sub'), 0
    if lang:
        srt_name = f"{uid}_subs"
        ydl_opts = {
            'skip_download': True, 'writesubtitles': True, 'subtitleslangs': [lang],
            'outtmpl': srt_name,
            'extractor_args': {'youtube': {'player_client': ['android']}},
            'postprocessors': [{'key': 'FFmpegSubtitlesConvertor', 'format': 'srt'}]
        }
        try:
            await asyncio.to_thread(lambda: yt_dlp.YoutubeDL(ydl_opts).download([data['url']]))
            for f in os.listdir('.'):
                if f.startswith(srt_name) and f.endswith(".srt"):
                    with open(f, 'r', encoding='utf-8') as file:
                        line_count = len(re.findall(r'\d+\n\d{2}:\d{2}:\d{2}', file.read()))
                    user_data[uid].update({'line_count': line_count, 'srt_path': f})
                    break
        except: pass
    await message.edit(f"📊 **{data['title']}**\nစာကြောင်းရေ: ({line_count})\n\nခွဲမည့်လူအရေအတွက် ပို့ပါ-")
    user_data[uid]['step'] = 'wait_split'

async def start_final_process(client, message, uid):
    data = user_data[uid]
    status = await message.reply_text("📥 Android API ဖြင့် ဒေါင်းလုဒ်ဆွဲနေသည်...")
    ydl_opts = {
        'format': f'bestvideo[height<={data["res"]}][ext=mp4]+bestaudio[ext=m4a]/best[height<={data["res"]}][ext=mp4]/best',
        'outtmpl': f'downloads/{uid}.%(ext)s',
        'extractor_args': {'youtube': {'player_client': ['android']}},
        'merge_output_format': 'mp4'
    }
    try:
        if not os.path.exists('downloads'): os.makedirs('downloads')
        info = await asyncio.to_thread(lambda: yt_dlp.YoutubeDL(ydl_opts).extract_info(data['url'], download=True))
        video_path = yt_dlp.YoutubeDL(ydl_opts).prepare_filename(info)
        await status.edit("📤 Telegram သို့ တင်ပို့နေသည်...")
        await client.send_video(chat_id=message.chat.id, video=video_path, caption=data['title'], supports_streaming=True)
        if os.path.exists(video_path): os.remove(video_path)
        if 'srt_path' in data and os.path.exists(data['srt_path']): os.remove(data['srt_path'])
        await status.delete()
        del user_data[uid]
    except Exception as e:
        await status.edit(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    print("Bot is starting with Android Mode...")
    app.run()
