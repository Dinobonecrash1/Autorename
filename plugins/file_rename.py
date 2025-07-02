import os
import re
import time
import shutil
import asyncio
from datetime import datetime
from PIL import Image
from pyrogram import Client, filters
from pyrogram.types import Message, ForceReply, InlineKeyboardMarkup, InlineKeyboardButton
from plugins.antinsfw import check_anti_nsfw
from helper.utils import progress_for_pyrogram, humanbytes, convert
from helper.database import codeflixbots  # Use codeflixbots for all db calls
from config import Config
from functools import wraps
from pyrogram.enums import MessageMediaType

ADMIN_URL = Config.ADMIN_URL

active_sequences = {}
message_ids = {}
renaming_operations = {}

download_semaphore = asyncio.Semaphore(5)
upload_semaphore = asyncio.Semaphore(3)

# ========== Decorators ==========

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

# ========== Helper Functions ==========

def detect_quality(file_name):
    quality_order = {"480p": 1, "720p": 2, "1080p": 3}
    match = re.search(r"(480p|720p|1080p)", file_name)
    return quality_order.get(match.group(1), 4) if match else 4

def extract_season_number(filename):
    patterns = [
        re.compile(r"S(\d+)", re.IGNORECASE),
        re.compile(r"Season[_\s-]?(\d+)", re.IGNORECASE),
    ]
    for pattern in patterns:
        match = re.search(pattern, filename)
        if match:
            return int(match.group(1))
    return 1

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
    patterns = [
        re.compile(r'S(\d+)(?:E|EP)(\d+)'),
        re.compile(r'S(\d+)\s*(?:E|EP|-\s*EP)(\d+)'),
        re.compile(r'(?:[([<{]?\s*(?:E|EP)\s*(\d+)\s*[)\]>}]?)'),
        re.compile(r'(?:\s*-\s*(\d+)\s*)'),
        re.compile(r'S(\d+)[^\d]*(\d+)', re.IGNORECASE)
    ]
    for pattern in patterns:
        match = re.search(pattern, filename)
        if match:
            return int(match.groups()[-1])
    match = re.search(r'(\d+)', filename)
    if match:
        return int(match.group(1))
    return 999

def extract_quality(filename):
    pattern5 = re.compile(r'\b(?:.*?(\d{3,4}[^\dp]*p).*?|.*?(\d{3,4}p))\b', re.IGNORECASE)
    pattern6 = re.compile(r'[([<{]?\s*4k\s*[)\]>}]?', re.IGNORECASE)
    pattern7 = re.compile(r'[([<{]?\s*2k\s*[)\]>}]?', re.IGNORECASE)
    pattern8 = re.compile(r'[([<{]?\s*HdRip\s*[)\]>}]?|\bHdRip\b', re.IGNORECASE)
    pattern9 = re.compile(r'[([<{]?\s*4kX264\s*[)\]>}]?', re.IGNORECASE)
    pattern10 = re.compile(r'[([<{]?\s*4kx265\s*[)\]>}]?', re.IGNORECASE)
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

            for file_to_remove in [path, ph_path, renamed_file_path, metadata_file_path]:
                if file_to_remove and os.path.exists(file_to_remove):
                    os.remove(file_to_remove)
            if file_id in renaming_operations:
                del renaming_operations[file_id]

        except Exception as e:
            del renaming_operations[file_id]
            return await download_msg.edit(f"Metadata/Processing Error: {e}")

    except Exception as e:
        if 'file_id' in locals() and file_id in renaming_operations:
            del renaming_operations[file_id]
        raise

# ========== Handlers ==========

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

@Client.on_callback_query(filters.regex('manual_rename'))
async def manual_rename_handler(bot, update):
    user_id = update.from_user.id
    mode = await codeflixbots.get_rename_mode(user_id)
    if mode != "manual":
        return await update.answer("Manual renaming is only available in manual mode.\nSwitch to manual mode first.", show_alert=True)
    await update.message.delete()
    await update.message.reply_text(
        "__ᴘʟᴇᴀsᴇ ᴇɴᴛᴇʀ ɴᴇᴡ ғɪʟᴇ ɴᴀᴍᴇ..__",
        reply_to_message_id=update.message.reply_to_message.id,
        reply_markup=ForceReply(True)
    )

@Client.on_message(filters.private & filters.reply)
async def handle_manual_rename(client, message):
    reply_message = message.reply_to_message
    if isinstance(reply_message.reply_markup, ForceReply):
        user_id = message.from_user.id
        mode = await codeflixbots.get_rename_mode(user_id)
        if mode != "manual":
            return await message.reply("Manual renaming is only available in manual mode.\nSwitch to manual mode first.")
        new_name = message.text
        await message.delete()
        msg = await client.get_messages(message.chat.id, reply_message.id)
        file = msg.reply_to_message
        media = getattr(file, file.media.value)
        if "." not in new_name:
            extn = media.file_name.rsplit('.', 1)[-1] if "." in media.file_name else "mkv"
            new_name += "." + extn
        await reply_message.delete()
        buttons = [
            [InlineKeyboardButton("📁 Dᴏᴄᴜᴍᴇɴᴛ", callback_data="upload_document")]
        ]
        if file.media in [MessageMediaType.VIDEO, MessageMediaType.DOCUMENT]:
            buttons.append([InlineKeyboardButton("🎥 Vɪᴅᴇᴏ", callback_data="upload_video")])
        elif file.media == MessageMediaType.AUDIO:
            buttons.append([InlineKeyboardButton("🎵 Aᴜᴅɪᴏ", callback_data="upload_audio")])
        await message.reply(
            text=f"**Sᴇʟᴇᴄᴛ Tʜᴇ Oᴜᴛᴩᴜᴛ Fɪʟᴇ Tyᴩᴇ**\n**• Fɪʟᴇ Nᴀᴍᴇ :-**  `{new_name}`",
            reply_to_message_id=file.id,
            reply_markup=InlineKeyboardMarkup(buttons)
        )

@Client.on_callback_query(filters.regex("upload"))
async def doc(bot, update):
    if not os.path.isdir("Metadata"):
        os.mkdir("Metadata")
    prefix = await codeflixbots.get_prefix(update.message.chat.id)
    suffix = await codeflixbots.get_suffix(update.message.chat.id)
    new_name = update.message.text
    new_filename_ = new_name.split(":-")[1]
    try:
        new_filename = f"{prefix or ''}{new_filename_}{suffix or ''}"
    except Exception as e:
        return await update.message.edit(f"⚠️ Something went wrong can't able to set Prefix or Suffix ☹️ \n\n❄️ Contact My Creator -> @sewxiy\nError: {e}")
    file_path = f"downloads/{new_filename}"
    file = update.message.reply_to_message
    ms = await update.message.edit("Tʀyɪɴɢ Tᴏ Dᴏᴡɴʟᴏᴀᴅɪɴɢ")
    try:
        path = await bot.download_media(
            message=file, file_name=file_path,
            progress=progress_for_pyrogram,
            progress_args=("\n⚠️ __**Please wait...**__\n\n❄️ **Dᴏᴡɴʟᴏᴀᴅ Sᴛᴀʀᴛᴇᴅ....**", ms, time.time())
        )
    except Exception as e:
        return await ms.edit(str(e))
    _bool_metadata = await codeflixbots.get_metadata(update.message.chat.id)
    metadata_path = None
    if _bool_metadata:
        metadata_path = f"Metadata/{new_filename}"
        metadata = await codeflixbots.get_metadata_code(update.message.chat.id)
        if metadata:
            await ms.edit("I Fᴏᴜɴᴅ Yᴏᴜʀ Mᴇᴛᴀᴅᴀᴛᴀ\n\n__**Aᴅᴅɪɴɢ Mᴇᴛᴀᴅᴀᴛᴀ Tᴏ Fɪʟᴇ....**")
            cmd = f"""ffmpeg -i "{path}" {metadata} "{metadata_path}" """
            process = await asyncio.create_subprocess_shell(
                cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            er = stderr.decode()
            if er:
                return await ms.edit(str(er) + "\n\n**Error**")
        await ms.edit("**Metadata added to the file successfully ✅**\n\n⚠️ __**Tʀyɪɴɢ Tᴏ Uᴩʟᴏᴀᴅɪɴɢ....**")
    else:
        await ms.edit("⚠️  __**Please wait...**__\n\n\n**Tʀyɪɴɢ Tᴏ Uᴩʟᴏᴀᴅɪɴɢ....**")
    duration = 0
    try:
        from helper.utils import createParser, extractMetadata
        parser = createParser(file_path)
        metadata = extractMetadata(parser)
        if metadata and metadata.has("duration"):
            duration = metadata.get('duration').seconds
        parser.close()
    except Exception:
        pass
    ph_path = None
    media = getattr(file, file.media.value)
    c_caption = await codeflixbots.get_caption(update.message.chat.id)
    c_thumb = await codeflixbots.get_thumbnail(update.message.chat.id)
    if c_caption:
        try:
            caption = c_caption.format(filename=new_filename, filesize=humanbytes(media.file_size), duration=convert(duration))
        except Exception as e:
            return await ms.edit(text=f"Yᴏᴜʀ Cᴀᴩᴛɪᴏɴ Eʀʀᴏʀ Exᴄᴇᴩᴛ Kᴇyᴡᴏʀᴅ Aʀɢᴜᴍᴇɴᴛ ●> ({e})")
    else:
        caption = f"**{new_filename}**"
    width = height = None
    if (getattr(media, "thumbs", None) or c_thumb):
        if c_thumb:
            ph_path = await bot.download_media(c_thumb)
            from helper.utils import fix_thumb
            width, height, ph_path = await fix_thumb(ph_path)
        else:
            try:
                from helper.utils import take_screen_shot, fix_thumb
                ph_path_ = await take_screen_shot(
                    file_path, os.path.dirname(os.path.abspath(file_path)),
                    random.randint(0, max(duration - 1, 0))
                )
                width, height, ph_path = await fix_thumb(ph_path_)
            except Exception as e:
                ph_path = None
                print(e)
    type = update.data.split("_")[1]
    big_file = getattr(media, "file_size", 0) > 2000 * 1024 * 1024
    try:
        send_fn = None
        send_kwargs = dict(
            caption=caption,
            thumb=ph_path,
            progress=progress_for_pyrogram,
            progress_args=("⚠️ __**Please wait...**__\n\n🌨️ **Uᴩʟᴏᴅ Sᴛᴀʀᴛᴇᴅ....**", ms, time.time())
        )
        send_target = update.message.chat.id
        file_to_send = metadata_path if _bool_metadata else file_path
        if type == "document":
            send_fn = bot.send_document
            send_kwargs["document"] = file_to_send
        elif type == "video":
            send_fn = bot.send_video
            send_kwargs["video"] = file_to_send
            send_kwargs["width"] = width
            send_kwargs["height"] = height
            send_kwargs["duration"] = duration
        elif type == "audio":
            send_fn = bot.send_audio
            send_kwargs["audio"] = file_to_send
            send_kwargs["duration"] = duration
        if send_fn:
            await send_fn(send_target, **send_kwargs)
    except Exception as e:
        for f in [file_path, ph_path, metadata_path]:
            if f and os.path.exists(f):
                os.remove(f)
        return await ms.edit(f" Eʀʀᴏʀ {e}")
    await ms.delete()
    for f in [file_path, ph_path, metadata_path]:
        if f and os.path.exists(f):
            os.remove(f)

@Client.on_message(filters.private & (filters.document | filters.video | filters.audio))
@check_ban
async def auto_rename_files(client, message):
    user_id = message.from_user.id
    user_mode = await codeflixbots.get_rename_mode(user_id)
    if user_mode != "auto":
        return
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
    if user_id in active_sequences:
        active_sequences[user_id].append(file_info)
        reply_msg = await message.reply_text("Wᴇᴡ...ғɪʟᴇs ʀᴇᴄᴇɪᴠᴇᴅ ɴᴏᴡ ᴜsᴇ /end_sequence ᴛᴏ ɢᴇᴛ ʏᴏᴜʀ ғɪʟᴇs...!!")
        message_ids[user_id].append(reply_msg.message_id)
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
        for index, file_info in enumerate(file_list, 1):
            try:
                await asyncio.sleep(0.5)
                if file_info["message"].document:
                    await client.send_document(
                        message.chat.id,
                        file_info["file_id"],
                        caption=f"{file_info['file_name']}"
                    )
                elif file_info["message"].video:
                    await client.send_video(
                        message.chat.id,
                        file_info["file_id"],
                        caption=f"{file_info['file_name']}"
                    )
                elif file_info["message"].audio:
                    await client.send_audio(
                        message.chat.id,
                        file_info["file_id"],
                        caption=f"{file_info['file_name']}"
                    )
            except Exception as e:
                await message.reply_text(f"Fᴀɪʟᴇᴅ ᴛᴏ sᴇɴᴅ ғɪʟᴇ: {file_info.get('file_name', '')}\n{e}")
        await message.reply_text(f"✅ Aʟʟ {count} ғɪʟᴇs sᴇɴᴛ sᴜᴄᴄᴇssғᴜʟʟʏ ɪɴ sᴇǫᴜᴇɴᴄᴇ!")
    try:
        await client.delete_messages(chat_id=message.chat.id, message_ids=delete_messages)
    except Exception as e:
        print(f"Error deleting messages: {e}")
