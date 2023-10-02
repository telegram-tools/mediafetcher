import os
import yt_dlp
import asyncio
import pyrogram  #upm package(pyrogram-repl)
import tempfile
import traceback
import threading
import subprocess
from PIL import Image
from pyrogram import enums  #upm package(pyrogram-repl)
from pyrogram import Client, filters  #upm package(pyrogram-repl)
from moviepy.video.io.VideoFileClip import VideoFileClip
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton  #upm package(pyrogram-repl)

api_id = os.environ["API_ID"]
api_hash = os.environ["API_HASH"]
bot_token = os.environ["TOKEN"]
temp_directory = tempfile.mkdtemp()
app = Client(
    "bot",
    api_id=api_id,
    api_hash=api_hash,
    bot_token=bot_token,
    in_memory=True,
    workers=8,
    max_concurrent_transmissions=8,
)

user_urls = {}
user_states = {}


def cleanup_temp_files():
  for filename in os.listdir(temp_directory):
    file_path = os.path.join(temp_directory, filename)
    try:
      if os.path.isfile(file_path):
        os.unlink(file_path)
    except Exception as e:
      print(f"Error cleaning up {file_path}: {e}")


cleanup_temp_files()


def download_media(choice, url, user_id):
  try:
    if choice == "video":
      ytdl_opts = {
          "format": "best[ext=mp4]",
          "outtmpl": f"{temp_directory}/video - %(title)s.%(ext)s",
          "addmetadata": True,
          "embedthumbnail": True,
          "writethumbnail": True,
          "quiet": True,
      }
    elif choice == "audio":
      ytdl_opts = {
          "format":
          "bestaudio/best",
          "outtmpl":
          f"{temp_directory}/audio - %(title)s.%(ext)s",
          "postprocessors": [{
              "key": "FFmpegExtractAudio",
              "preferredcodec": "mp3"
          }],
          "addmetadata":
          True,
          "embedthumbnail":
          True,
          "writethumbnail":
          True,
          "quiet":
          True,
      }

    ytdl = yt_dlp.YoutubeDL(ytdl_opts)
    video_info = ytdl.extract_info(url, download=False)
    ytdl.download([url])
    temp_file_path = ytdl.prepare_filename(video_info)
    if choice == "video":
      raw_thumbnail = None
      thumbnail = None
      if os.path.isfile(temp_file_path.rsplit(".", 1)[0] + ".webp"):
        raw_thumbnail = temp_file_path.rsplit(".", 1)[0] + ".webp"
        thumbnail = temp_file_path.rsplit(".", 1)[0] + ".jpg"
        image = Image.open(raw_thumbnail)
        image.save(thumbnail, "JPEG")
      elif os.path.isfile(temp_file_path.rsplit(".", 1)[0] + ".jpg"):
        thumbnail = temp_file_path.rsplit(".", 1)[0] + ".jpg"
      elif os.path.isfile(temp_file_path.rsplit(".", 1)[0] + ".png"):
        thumbnail = temp_file_path.rsplit(".", 1)[0] + ".png"
      else:
        outpath = thumbnail = temp_file_path.rsplit(".", 1)[0] + ".jpg"
        video = VideoFileClip(temp_file_path)
        video.save_frame(outpath, t=0)
        thumbnail = outpath

      if temp_file_path is not None:
        params = {}
        duration = video_info.get("duration")
        if duration is not None:
          params["duration"] = int(duration)
        width = video_info.get("width")
        if width is not None:
          params["width"] = int(width)
        height = video_info.get("height")
        if height is not None:
          params["height"] = int(height)

        with open(temp_file_path,
                  "rb") as video_file, open(thumbnail, "rb") as thumb_file:
          app.send_video(
              user_id,
              video=video_file,
              thumb=thumb_file,
              **params,
          )

        os.remove(temp_file_path)
        if raw_thumbnail:
          os.remove(raw_thumbnail)
        os.remove(thumbnail)
    elif choice == "audio":
      if temp_file_path is not None:
        params = {}
        duration = video_info.get("duration")
        if duration is not None:
          params["duration"] = int(duration)
        title = video_info.get("title")
        if title is not None:
          params["title"] = title
        performer = video_info.get("extractor_key")
        if performer is not None:
          params["performer"] = performer

      with open(temp_file_path.rsplit(".", 1)[0] + ".mp3", "rb") as audio_file:
        app.send_audio(
            user_id,
            audio=audio_file,
            **params,
        )

      os.remove(temp_file_path.rsplit(".", 1)[0] + ".mp3")

  except Exception as e:
    print(e)


@app.on_callback_query()
async def callback_handler(bot, update):
  user_id = update.from_user.id
  choice = update.data

  if choice not in ["video", "audio"]:
    await update.answer("Invalid choice.")
    return

  user_states[user_id] = choice
  url = user_urls[user_id]

  try:
    await update.message.delete()
    await update.answer(f"You chose to download {choice}...")
    download_thread = threading.Thread(target=download_media,
                                       args=(choice, url, user_id))
    download_thread.start()
  except Exception as e:
    print(e)

  del user_states[user_id]
  del user_urls[user_id]


@app.on_message(
    filters.regex(
        r"^(http(s):\/\/.)[-a-zA-Z0-9@:%._\+~#=]{2,256}\.[a-z]{2,6}\b([-a-zA-Z0-9@:%_\+.~#?&//=]*)$"
    ))
async def store_url_handler(bot, update):
  user_id = update.from_user.id
  url = update.text
  user_urls[user_id] = url
  message = update
  valid_message = await message.reply_text(
      "Validating URL and extracting formats...", quote=True)

  def validate_url(url, message):
    ytdl = yt_dlp.YoutubeDL()
    try:
      info = ytdl.extract_info(url, download=False)
      formats = info.get('formats', [info])
      available_formats = [f['ext'] for f in formats]
      if available_formats:
        if 'mp4' in available_formats:
          selection = InlineKeyboardMarkup([[
              InlineKeyboardButton("Video", callback_data="video"),
              InlineKeyboardButton("Audio", callback_data="audio")
          ]])
          message.reply_text(
              "Please use the buttons below to download the appropriate format.",
              reply_markup=selection,
              quote=True,
          )
          valid_message.delete()
        if 'mp4' not in available_formats and 'mp3' in available_formats:
          selection = InlineKeyboardMarkup(
              [[InlineKeyboardButton("Audio", callback_data="audio")]])
          message.reply_text(
              "Please use the buttons below to download the appropriate format.",
              reply_markup=selection,
              quote=True,
          )
          valid_message.delete()
    except:
      valid_message.edit_text("No valid formats found for the provided URL.")

  try:
    checkurl_thread = threading.Thread(target=validate_url,
                                       args=(url, message))
    checkurl_thread.start()
  except Exception as e:
    valid_message.edit_text("Error occured, please try again later.")
    print(e)


@app.on_message(filters.command("ping", prefixes="/"))
async def ping_command(client, message):
  start_time = message.date
  ping_msg = await message.reply("Pinging...")
  end_time = (await ping_msg.edit_text("Pong!")).date
  latency = (end_time - start_time).total_seconds() * 1000
  await ping_msg.edit_text(f"Pong! Latency: {latency:.2f} ms")


@app.on_message(filters.command("user", prefixes="/"))
async def userinfo_command(client, message):
  user = message.from_user
  user_id = user.id
  first_name = user.first_name
  last_name = user.last_name or "n/a"
  username = user.username or "n/a"
  is_bot = user.is_bot
  raw_status = str(user.status)
  status = " ".join(word.capitalize()
                    for word in raw_status.split(".")[-1].split("_"))

  user_info_message = (f"├── **User ID:** `{user_id}`\n"
                       f"├── **First Name:** `{first_name}`\n"
                       f"├── **Last Name:** `{last_name}`\n"
                       f"├── **Username:** @{username}\n"
                       f"├── **Type:** {'Bot' if is_bot else 'User'}\n"
                       f"└── **Last seen:** {status}")

  await message.reply_text(user_info_message,
                           parse_mode=enums.ParseMode.MARKDOWN,
                           quote=True)


@app.on_message(filters.command("start", prefixes="/"))
async def start_command(client, message):
  welcome_message = "Download and share medias more conviniently just by sending the URL of the content you want."
  await message.reply_text(welcome_message, quote=True)


if __name__ == "__main__":
  print("Bot is online.")
  app.run()
