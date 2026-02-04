import os
import asyncio
import math
import yt_dlp
import re
import threading
from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- Health Check Section (For Koyeb) ---
web_app = Flask(__name__)
@web_app.route('/')
def home(): return "Bot is running!"

def run_web():
    web_app.run(host='0.0.0.0', port=8000)

threading.Thread(target=run_web, daemon=True).start()

# --- Telegram Bot Section ---
API_ID = 33140158
API_HASH = "936e6187972a97c9f9b616516f24b61c"
BOT_TOKEN = "8571685060:AAFJyzZ6CF150w51k0ft_PHXgUJPaaPJg6I"

app = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
user_data = {}

def get_video_info(url):
    with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
        return ydl.extract_info(url, download=False)

@app.on_message(filters.text & filters.private)
async def main_handler(client, message):
    uid = message.from_user.id
    text = message.text

    # Step စစ်ဆေးခြင်း (လူခွဲဖို့ နံပါတ်စောင့်နေချိန်)
    if uid in user_data and user_data[uid].get('step') == 'wait_split':
        try:
            num = int(text)
            total = user_data[uid]['line_count']
            per_person = math.ceil(total / num)
            
            summary = f"🎬 **{user_data[uid]['title']}**\nစုစုပေါင်း စာကြောင်းရေ ({total})\n\n"
            for i in range(num):
                start = (i * per_person) + 1
                end = min((i + 1) * per_person, total)
                summary += f"({chr(97+i)}) {start} - {end}\n"
            
            await message.reply_text(summary)
            await start_final_process(client, message, uid)
        except ValueError:
            await message.reply_text("❌ ကျေးဇူးပြု၍ ကိန်းဂဏန်း (နံပါတ်) ပဲ ရိုက်ထည့်ပါ။")
        return

    # Link အသစ်စစ်ဆေးခြင်း
    if text.startswith("http"):
        msg = await message.reply_text("🔎 ဗီဒီယိုအချက်အလက်များကို စစ်ဆေးနေသည်...")
        try:
            info = await asyncio.to_thread(get_video_info, text)
            title = info.get('title', 'Video')
            subs = info.get('subtitles', {})
            
            user_data[uid] = {'url': text, 'title': title, 'subs': subs}
            
            buttons = [[
                InlineKeyboardButton("360p", callback_data="res_360"),
                InlineKeyboardButton("720p", callback_data="res_720"),
                InlineKeyboardButton("1080p", callback_data="res_1080")
            ]]
            await msg.edit(f"🎬 **{title}**\n\nResolution ရွေးချယ်ပေးပါ-", reply_markup=InlineKeyboardMarkup(buttons))
        except Exception as e:
            await msg.edit(f"❌ Error: {str(e)}")

@app.on_callback_query(filters.regex("^res_"))
async def choose_res(client, callback_query):
    res = callback_query.data.split("_")[1]
    uid = callback_query.from_user.id
    user_data[uid]['res'] = res
    
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
            await callback_query.message.edit("English Sub မတွေ့ပါ။ ရှိတဲ့ထဲမှ ရွေးပါ-", reply_markup=InlineKeyboardMarkup(sub_buttons))

@app.on_callback_query(filters.regex("^sub_"))
async def choose_sub(client, callback_query):
    lang = callback_query.data.split("_")[1]
    uid = callback_query.from_user.id
    user_data[uid]['selected_sub'] = lang
    await proceed_to_sub_split(callback_query.message, uid)

async def proceed_to_sub_split(message, uid):
    data = user_data[uid]
    lang = data.get('selected_sub')
    line_count = 0
    
    if lang:
        srt_name = f"{uid}_subs"
        ydl_opts = {'skip_download': True, 'writesubtitles': True, 'subtitleslangs': [lang], 'outtmpl': srt_name}
        try:
            await asyncio.to_thread(lambda: yt_dlp.YoutubeDL(ydl_opts).download([data['url']]))
            # SRT ဖိုင်အမည် အတိအကျရှာခြင်း
            for f in os.listdir('.'):
                if f.startswith(srt_name) and f.endswith(".srt"):
                    with open(f, 'r', encoding='utf-8') as file:
                        content = file.read()
                        line_count = len(re.findall(r'\d+\n\d{2}:\d{2}:\d{2}', content))
                    user_data[uid]['line_count'] = line_count
                    user_data[uid]['srt_path'] = f
                    break
        except: pass

    await message.edit(f"📊 **{data['title']}**\nစုစုပေါင်း စာကြောင်းရေ: ({line_count})\n\nလူဘယ်နှစ်ယောက် ခွဲမလဲ? (နံပါတ်တစ်ခုတည်း ရိုက်ပို့ပေးပါ)")
    user_data[uid]['step'] = 'wait_split'

async def start_final_process(client, message, uid):
    data = user_data[uid]
    status = await message.reply_text("📥 ဒေါင်းလုဒ်စတင်နေပါပြီ... (ခဏစောင့်ပေးပါ)")

    ydl_opts = {
        'format': f'bestvideo[height<={data["res"]}][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]',
        'outtmpl': f'downloads/{uid}_video.%(ext)s',
    }

    try:
        # Downloads folder မရှိရင် ဆောက်မယ်
        if not os.path.exists('downloads'): os.makedirs('downloads')
        
        info = await asyncio.to_thread(lambda: yt_dlp.YoutubeDL(ydl_opts).extract_info(data['url'], download=True))
        video_path = yt_dlp.YoutubeDL(ydl_opts).prepare_filename(info)
        
        await status.edit("📤 Telegram သို့ တင်ပို့နေသည်...")
        await client.send_video(chat_id=message.chat.id, video=video_path, caption=data['title'], supports_streaming=True)
        
        # Cleaning
        if os.path.exists(video_path): os.remove(video_path)
        if 'srt_path' in data and os.path.exists(data['srt_path']): os.remove(data['srt_path'])
        await status.delete()
        del user_data[uid]
    except Exception as e:
        await status.edit(f"❌ အမှားရှိခဲ့သည်: {str(e)}")

app.run()

