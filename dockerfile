FROM python:3.9-slim

# FFmpeg နဲ့ လိုအပ်တာတွေ သွင်းခြင်း
RUN apt-get update && apt-get install -y ffmpeg

WORKDIR /app
COPY . .

RUN pip install --no-cache-dir -r requirements.txt

# ဒေါင်းလုဒ်ဆွဲမယ့် folder ဆောက်ထားခြင်း
RUN mkdir downloads

CMD ["python", "bot.py"]