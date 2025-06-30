import os
import re
import time
import shutil
import asyncio
from datetime import datetime
from PIL import Image
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from plugins.antinsfw import check_anti_nsfw
from helper.utils import progress_for_pyrogram, humanbytes, convert
from helper.database import codeflixbots
from config import Config
from functools import wraps
from pyrogram.enums import MessageMediaType

try:
    from filerename import initiate_manual_rename  # Try to import manual rename handler
except ImportError:
    print("Warning: filerename.py not found. Manual rename functionality will be disabled.")
    initiate_manual_rename = None  # Fallback if import fails

ADMIN_URL = Config.ADMIN_URL

active_sequences = {}
message_ids = {}
renaming_operations = {}

# --- Semaphores for concurrent operations ---
download_semaphore = asyncio.Semaphore(5)  # Allow 5 concurrent downloads
upload_semaphore = asyncio.Semaphore(3)    # Allow 3 concurrent uploads

def check_ban(func):
    @wraps(func)
    async def wrapper(client, message, *args, **kwargs):
        user_id = message.from_user.id
        user = await codeflixbots.col.find_one({"_id": user_id})
        if user and user.get("ban_status", {}).get("is_banned", False):
            keyboard = InlineKeyboardMarkup(
                [[InlineKeyboardButton("📩 Contact Admin", url=ADMIN_URL)]]
            )
            return await message.reply_text(
                "🚫 You are banned from using this bot.\n\nIf you think this is a mistake, contact the admin.",
                reply_markup=keyboard
            )
        return await func(client, message, *args, **kwargs)
    return wrapper

def detect_quality(file_name):
    quality_order = {"480p": 1, "720p": 2, "1080p": 3}
    match = re.search(r"(480p|720p|1080p)", file_name)
    return quality_order.get(match.group(1), 4) if match else 4  # Default priority = 4

def extract_season_number(filename):
    patterns = [
        re.compile(r"S(\d+)", re.IGNORECASE),
        re.compile(r"Season[_\s-]?(\d+)", re.IGNORECASE),
    ]
    for pattern in patterns:
        match = re.search(pattern, filename)
        if match:
            return int(match.group(1))
    return 1  # Default to season 1 if not found

def extract_audio_type(filename: str) -> str:
    if not filename or not isinstance(filename, str):
        return "Unknown"
    
    lower = filename.lower()
    
    if "multi audio" in lower:
        return "Multi Audio"
    if "dual audio" in lower:
        return "Dual Audio"
    
    specific_languages = {'japanese', 'english', 'hindi', 'tamil', 'telugu'}
    
    found_languages = set()
    for lang in specific_languages:
        if lang in lower:
            found_languages.add(lang)
    
    lang_count = len(found_languages)
    
    if lang_count >= 3:
        return "Multi Audio"
    elif lang_count == 2:
        return "Dual Audio"
    elif lang_count == 1:
        return "Single Audio"
    
    match = re.search(r"\{([^\}]*)\}", lower)
    if not match or not match.group(1).strip():
        return "Unknown"
    
    lang_text = match.group(1)
    langs = [lang.strip() for lang in lang_text.split("-") if lang.strip()]
    lang_count = len(set(langs))
    
    if lang_count >= 3:
        return "Multi Audio"
    elif lang_count == 2:
        return "Dual Audio"
    elif lang_count == 1:
        return "Single Audio"
    else:
        return "Unknown"

def extract_episode_number(filename):
    pattern1 = re.compile(r'S(\d+)(?:E|EP)(\d+)')
    pattern2 = re.compile(r'S(\d+)\s*(?:E|EP|-\s*EP)(\d+)')
    pattern3 = re.compile(r'(?:[([<{]?\s*(?:E|EP)\s*(\d+)\s*[)\]>}]?)')
    pattern3_2 = re.compile(r'(?:\s*-\s*(\d+)\s*)')
    pattern4 = re.compile(r'S(\d+)[^\d]*(\d+)', re.IGNORECASE)
    patternX = re.compile(r'(\d+)')
    
    for pattern in [pattern1, pattern2, pattern3, pattern3_2, pattern4]:
        match = re.search(pattern, filename)
        if match:
            return int(match.groups()[-1])
    
    match = re.search(patternX, filename)
    if match:
        return int(match.group(1))
    
    return 999

@Client.on_message(filters.command("start_sequence") & filters.private)
@check_ban
async def start_sequence(client, message: Message):
    user_id = message.from_user.id
    if user_id in active_sequences:
        await message.reply_text(
            "Hᴇʏ ᴅᴜᴅᴇ...!! A sᴇǫᴜᴇɴᴄᴇ ɪs ᴀʟʀᴇᴀᴅʏ ᴀᴄᴛɪᴠᴇ! Usᴇ /end_sequence ᴛᴏ ᴇɴᴅ ɪᴛ."
        )
    else:
        active_sequences[user_id] = []
        message_ids[user_id] = []
        msg = await message.reply_text(
            "Sᴇǫᴜᴇɴᴄᴇ sᴛᴀʀᴛᴇᴅ! Sᴇɴᴅ ʏᴏᴜʀ ғɪʟᴇs ɴᴏᴡ ʙʀᴏ....Fᴀsᴛ"
        )
        message_ids[user_id].append(msg.message_id)

@Client.on_message(filters.private & (filters.document | filters.video | filters.audio))
@check_ban
async def auto_rename_files(client, message):
    user_id = message.from_user.id
    file_id = (
        message.document.file_id if message.document else
        message.video.file_id if message.video else
        message.audio.file_id
    )
    file_name = (
        message.document.file_name if message.document else
        message.video.file_name if message.video else
        message.audio.file_name
    )
    file_info = {
        "file_id": file_id,
        "file_name": file_name if file_name else "Unknown",
        "message": message,
        "episode_num": extract_episode_number(file_name if file_name else "Unknown")
    }

    rename_mode = await codeflixbots.get_rename_mode(user_id)
    
    if user_id in active_sequences:
        active_sequences[user_id].append(file_info)
        reply_msg = await message.reply_text("Wᴇᴡ...ғɪʟᴇs ʀᴇᴄᴇɪᴠᴇᴅ ɴᴏᴡ ᴜsᴇ /end_sequence ᴛᴏ ɢᴇᴛ ʏᴏᴜʀ ғɪʟᴇs...!!")
        message_ids[user_id].append(reply_msg.message_id)
        return

    if rename_mode == "manual" and initiate_manual_rename:
        # Delegate to filerename.py for manual handling
        await initiate_manual_rename(client, message)
        return

    asyncio.create_task(auto_rename_file(client, message, file_info))

@Client.on_message(filters.command("end_sequence") & filters.private)
@check_ban
async def end_sequence(client, message: Message):
    user_id = message.from_user.id
    if user_id not in active_sequences:
        await message.reply_text("Wʜᴀᴛ ᴀʀᴇ ʏᴏᴜ ᴅᴏɪɴɢ ɴᴏ ᴀᴄᴛɪᴠᴇ sᴇǫᴜᴇɴᴄᴇ ғᴏᴜɴᴅ...!!")
        return

    file_list = active_sequences.pop(user_id, [])
    delete_messages = message_ids.pop(user_id, [])
    count = len(file_list)

    if not file_list:
        await message.reply_text("Nᴏ ғɪʟᴇs ᴡᴇʀᴇ sᴇɴᴛ ɪɴ ᴛʜɪs sᴇǫᴜᴇɴᴄᴇ....ʙʀᴏ...!!")
    else:
        file_list.sort(key=lambda x: x["episode_num"])
        await message.reply_text(f"Sᴇǫᴜᴇɴᴄᴇ ᴇɴᴅᴇᴅ. Nᴏᴡ sᴇɴᴅɪɴɢ ʏᴏᴜʀ {count} ғɪʟᴇ(s) ʙᴀᴄᴋ ɪɴ sᴇǫᴜᴇɴᴄᴇ...!!")
        
        rename_mode = await codeflixbots.get_rename_mode(user_id)
        
        for index, file_info in enumerate(file_list, 1):
            try:
                await asyncio.sleep(0.5)
                
                if rename_mode == "manual" and initiate_manual_rename:
                    # Delegate to filerename.py for manual handling
                    await initiate_manual_rename(client, file_info["message"])
                else:
                    await client.send_document(
                        message.chat.id,
                        file_info["file_id"],
                        caption=f"{file_info['file_name']}"
                    )
                
            except Exception as e:
                await message.reply_text(f"Fᴀɪʟᴇᴅ ᴛᴏ sᴇɴᴅ ғɪʟᴇ: {file_info.get('file_name', '')}\n{e}")
        
        if rename_mode != "manual":
            await message.reply_text(f"✅ Aʟʟ {count} ғɪʟᴇs sᴇɴᴛ sᴜᴄᴄᴇssғᴜʟʟʏ ɪɴ sᴇǫᴜᴇɴᴄᴇ!")

    try:
        await client.delete_messages(chat_id=message.chat.id, message_ids=delete_messages)
    except Exception as e:
        print(f"Error deleting messages: {e}")

# Regex patterns for filename parsing
pattern1 = re.compile(r'S(\d+)(?:E|EP)(\d+)')
pattern2 = re.compile(r'S(\d+)\s*(?:E|EP|-\s*EP)(\d+)')
pattern3 = re.compile(r'(?:[([<{]?\s*(?:E|EP)\s*(\d+)\s*[)\]>}]?)')
pattern3_2 = re.compile(r'(?:\s*-\s*(\d+)\s*)')
pattern4 = re.compile(r'S(\d+)[^\d]*(\d+)', re.IGNORECASE)
patternX = re.compile(r'(\d+)')
pattern5 = re.compile(r'\b(?:.*?(\d{3,4}[^\dp]*p).*?|.*?(\d{3,4}p))\b', re.IGNORECASE)
pattern6 = re.compile(r'[([<{]?\s*4k\s*[)\]>}]?', re.IGNORECASE)
pattern7 = re.compile(r'[([<{]?\s*2k\s*[)\]>}]?', re.IGNORECASE)
pattern8 = re.compile(r'[([<{]?\s*HdRip\s*[)\]>}]?|\bHdRip\b', re.IGNORECASE)
pattern9 = re.compile(r'[([<{]?\s*4kX264\s*[)\]>}]?', re.IGNORECASE)
pattern10 = re.compile(r'[([<{]?\s*4kx265\s*[)\]>}]?', re.IGNORECASE)

def extract_quality(filename):
    match5 = re.search(pattern5, filename) 
    if match5:
        return match5.group(1) or match5.group(2)
    match6 = re.search(pattern6, filename)
    if match6:
        return "4k"
    match7 = re.search(pattern7, filename)
    if match7:
        return "2k"
    match8 = re.search(pattern8, filename)
    if match8:
        return "HdRip"
    match9 = re.search(pattern9, filename)
    if match9:
        return "4kX264"
    match10 = re.search(pattern10, filename)
    if match10:
        return "4kx265"
    return "Unknown"

async def get_audio_track_type(file_path):
    ffprobe_cmd = shutil.which('ffprobe')
    if not ffprobe_cmd:
        return "Unknown"

    command = [
        ffprobe_cmd,
        "-v", "error",
        "-select_streams", "a",
        "-show_entries", "stream=index",
        "-of", "csv=p=0",
        file_path
    ]

    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await process.communicate()
        audio_tracks = stdout.decode().strip().splitlines()
        count = len(audio_tracks)

        if count == 1:
            return "Single Audio"
        elif count == 2:
            return "Dual Audio"
        elif count >= 3:
            return "Multi Audio"
        return "Unknown"
    except Exception as e:
        print(f"Audio detection error: {e}")
        return "Unknown"

async def process_thumb(ph_path):
    def _resize_thumb(path):
        img = Image.open(path).convert("RGB")
        img = img.resize((320, 320))
        img.save(path, "JPEG")
    await asyncio.to_thread(_resize_thumb, ph_path)

async def concurrent_download(client, message, renamed_file_path, progress_msg):
    async with download_semaphore:
        try:
            path = await client.download_media(
                message,
                file_name=renamed_file_path,
                progress=progress_for_pyrogram,
                progress_args=("Dᴏᴡɴʟᴏᴀᴅ sᴛᴀʀᴛᴇᴅ ᴅᴜᴅᴇ....!!", progress_msg, time.time()),
            )
            return path
        except Exception as e:
            raise Exception(f"Download Error: {e}")

async def concurrent_upload(client, message, path, media_type, caption, ph_path, progress_msg):
    async with upload_semaphore:
        try:
            if media_type == "document":
                await client.send_document(
                    message.chat.id,
                    document=path,
                    thumb=ph_path,
                    caption=caption,
                    progress=progress_for_pyrogram,
                    progress_args=("Uᴘʟᴏᴀᴅ sᴛᴀʀᴛᴇᴅ ᴅᴜᴅᴇ...!!", progress_msg, time.time()),
                )
            elif media_type == "video":
                await client.send_video(
                    message.chat.id,
                    video=path,
                    caption=caption,
                    thumb=ph_path,
                    duration=0,
                    progress=progress_for_pyrogram,
                    progress_args=("Uᴘʟᴏᴀᴅ sᴛᴀʀᴛᴇᴅ ᴅᴜᴅᴇ...!!", progress_msg, time.time()),
                )
            elif media_type == "audio":
                await client.send_audio(
                    message.chat.id,
                    audio=path,
                    caption=caption,
                    thumb=ph_path,
                    duration=0,
                    progress=progress_for_pyrogram,
                    progress_args=("Uᴘʟᴏᴀᴅ sᴛᴀʀᴛᴇᴅ ᴅᴜᴅᴇ...!!", progress_msg, time.time()),
                )
        except Exception as e:
            raise Exception(f"Upload Error: {e}")

async def auto_rename_file(client, message, file_info, is_sequence=False, status_msg=None):
    try:
        user_id = message.from_user.id
        file_id = file_info["file_id"]
        file_name = file_info["file_name"]

        format_template = await codeflixbots.get_format_template(user_id)
        media_preference = await codeflixbots.get_media_preference(user_id)

        if not format_template:
            error_msg = "Please Set An Auto Rename Format First Using /autorename"
            if status_msg:
                return await status_msg.edit(error_msg)
            else:
                return await message.reply_text(error_msg)

        media_type = media_preference or "document"
        if file_name.endswith(".mp4"):
            media_type = "video"
        elif file_name.endswith(".mp3"):
            media_type = "audio"

        if await check_anti_nsfw(file_name, message):
            error_msg = "NSFW content detected. File upload rejected."
            if status_msg:
                return await status_msg.edit(error_msg)
            else:
                return await message.reply_text(error_msg)

        if file_id in renaming_operations:
            elapsed_time = (datetime.now() - renaming_operations[file_id]).seconds
            if elapsed_time < 10:
                return

        renaming_operations[file_id] = datetime.now()

        episode_number = extract_episode_number(file_name)
        season_number = extract_season_number(file_name)
        print(f"Extracted Season: {season_number}, Episode: {episode_number}")

        template = format_template
        if episode_number:
            placeholders = ["episode", "Episode", "EPISODE", "{episode}"]
            for placeholder in placeholders:
                template = template.replace(placeholder, str(episode_number), 1)
            season_placeholders = ["season", "Season", "SEASON", "{season}"]
            for season_placeholder in season_placeholders:
                template = template.replace(season_placeholder, f"{season_number:02d}", 1)
            quality_placeholders = ["quality", "Quality", "QUALITY", "{quality}"]
            for quality_placeholder in quality_placeholders:
                if quality_placeholder in template:
                    extracted_qualities = extract_quality(file_name)
                    if extracted_qualities == "Unknown":
                        error_msg = "I Was Not Able To Extract The Quality Properly. Renaming As 'Unknown'..."
                        if status_msg:
                            await status_msg.edit(error_msg)
                        else:
                            await message.reply_text(error_msg)
                        del renaming_operations[file_id]
                        return
                    template = template.replace(quality_placeholder, "".join(extracted_qualities))
            audio_type = extract_audio_type(file_name)
            template = template.replace("{audio}", audio_type)

        _, file_extension = os.path.splitext(file_name)
        renamed_file_name = f"{template}{file_extension}"
        renamed_file_path = f"downloads/{renamed_file_name}"
        metadata_file_path = f"Metadata/{renamed_file_name}"
        os.makedirs(os.path.dirname(renamed_file_path), exist_ok=True)
        os.makedirs(os.path.dirname(metadata_file_path), exist_ok=True)

        if status_msg:
            download_msg = status_msg
            await download_msg.edit("Wᴇᴡ... Iᴀᴍ ᴅᴏᴡɴʟᴏᴀᴅɪɴɢ ʏᴏᴜʀ ғɪʟᴇ...!!")
        else:
            download_msg = await message.reply_text("Wᴇᴡ... Iᴀᴍ ᴅᴏᴡɴʟᴏᴀᴅɪɴɢ ʏᴏᴜʀ ғɪʟᴇ...!!")

        ph_path = None

        try:
            path = await concurrent_download(client, message, renamed_file_path, download_msg)
        except Exception as e:
            del renaming_operations[file_id]
            return await download_msg.edit(str(e))

        await download_msg.edit("Nᴏᴡ ᴀᴅᴅɪɴɢ ᴍᴇᴛᴀᴅᴀᴛᴀ ᴅᴜᴅᴇ...!!")

        ffmpeg_cmd = shutil.which('ffmpeg')
        metadata_command = [
            ffmpeg_cmd,
            '-i', path,
            '-metadata', f'title={await codeflixbots.get_title(user_id)}',
            '-metadata', f'artist={await codeflixbots.get_artist(user_id)}',
            '-metadata', f'author={await codeflixbots.get_author(user_id)}',
            '-metadata:s:v', f'title={await codeflixbots.get_video(user_id)}',
            '-metadata:s:a', f'title={await codeflixbots.get_audio(user_id)}',
            '-metadata:s:s', f'title={await codeflixbots.get_subtitle(user_id)}',
            '-metadata', f'encoded_by={await codeflixbots.get_encoded_by(user_id)}',
            '-metadata', f'custom_tag={await codeflixbots.get_custom_tag(user_id)}',
            '-map', '0',
            '-c', 'copy',
            '-loglevel', 'error',
            metadata_file_path
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *metadata_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            if process.returncode != 0:
                error_message = stderr.decode()
                await download_msg.edit(f"Metadata Error:\n{error_message}")
                del renaming_operations[file_id]
                return

            path = metadata_file_path
            
            upload_msg = await download_msg.edit("Wᴇᴡ... Iᴀᴍ Uᴘʟᴏᴀᴅɪɴɢ ʏᴏᴜʀ ғɪʟᴇ...!!")

            c_caption = await codeflixbots.get_caption(message.chat.id)
            c_thumb = await codeflixbots.get_thumbnail(message.chat.id)

            caption = (
                c_caption.format(
                    filename=renamed_file_name,
                    filesize=humanbytes(message.document.file_size) if message.document else "Unknown",
                    duration=convert(0),
                )
                if c_caption
                else f"{renamed_file_name}"
            )

            if c_thumb:
                ph_path = await client.download_media(c_thumb)
            elif media_type == "video" and getattr(message.video, "thumbs", None):
                ph_path = await client.download_media(message.video.thumbs[0].file_id)

            if ph_path:
                await process_thumb(ph_path)

            try:
                await concurrent_upload(client, message, path, media_type, caption, ph_path, upload_msg)
            except Exception as e:
                if os.path.exists(renamed_file_path):
                    os.remove(renamed_file_path)
                if ph_path and os.path.exists(ph_path):
                    os.remove(ph_path)
                del renaming_operations[file_id]
                return await upload_msg.edit(str(e))

            if not is_sequence:
                await download_msg.delete()
            else:
                await download_msg.edit(f"✅ Cᴏᴍᴘʟᴇᴛᴇᴅ: {renamed_file_name}")

            if os.path.exists(path):
                os.remove(path)
            if ph_path and os.path.exists(ph_path):
                os.remove(ph_path)
            if os.path.exists(renamed_file_path):
                os.remove(renamed_file_path)
            if os.path.exists(metadata_file_path):
                os.remove(metadata_file_path)
            if file_id in renaming_operations:
                del renaming_operations[file_id]

        except Exception as e:
            del renaming_operations[file_id]
            return await download_msg.edit(f"Metadata/Processing Error: {e}")

    except Exception as e:
        if 'file_id' in locals() and file_id in renaming_operations:
            del renaming_operations[file_id]
        raise
