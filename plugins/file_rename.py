import os
import re
import time
import shutil
import asyncio
from datetime import datetime
from PIL import Image
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from plugins.antinsfw import check_anti_nsfw
from helper.utils import progress_for_pyrogram, humanbytes, convert
from helper.database import codeflixbots
from config import Config

# Shared state for rename operations
download_semaphore = asyncio.Semaphore(5)
upload_semaphore = asyncio.Semaphore(3)
renaming_operations = {}

def extract_episode_number(filename):
    # Add your logic as before (regex etc)
    pattern = re.compile(r'S(\d+)(?:E|EP)(\d+)')
    match = pattern.search(filename)
    if match:
        return int(match.groups()[-1])
    return 999

def extract_season_number(filename):
    pattern = re.compile(r"S(\d+)", re.IGNORECASE)
    match = pattern.search(filename)
    if match:
        return int(match.group(1))
    return 1

def extract_quality(filename):
    quality_patterns = [
        (r'480p', "480p"),
        (r'720p', "720p"),
        (r'1080p', "1080p"),
        (r'4k', "4k"),
        (r'2k', "2k"),
        (r'HdRip', "HdRip")
    ]
    for pat, val in quality_patterns:
        if re.search(pat, filename, re.IGNORECASE):
            return val
    return "Unknown"

def extract_audio_type(filename):
    lower = filename.lower()
    if "multi audio" in lower:
        return "Multi Audio"
    if "dual audio" in lower:
        return "Dual Audio"
    langs = ['japanese', 'english', 'hindi', 'tamil', 'telugu']
    found = [lang for lang in langs if lang in lower]
    if len(found) >= 3:
        return "Multi Audio"
    elif len(found) == 2:
        return "Dual Audio"
    elif len(found) == 1:
        return "Single Audio"
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
                progress_args=("Download started...", progress_msg, time.time()),
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
                    progress_args=("Upload started...", progress_msg, time.time()),
                )
            elif media_type == "video":
                await client.send_video(
                    message.chat.id,
                    video=path,
                    caption=caption,
                    thumb=ph_path,
                    duration=0,
                    progress=progress_for_pyrogram,
                    progress_args=("Upload started...", progress_msg, time.time()),
                )
            elif media_type == "audio":
                await client.send_audio(
                    message.chat.id,
                    audio=path,
                    caption=caption,
                    thumb=ph_path,
                    duration=0,
                    progress=progress_for_pyrogram,
                    progress_args=("Upload started...", progress_msg, time.time()),
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
            error_msg = "Please set an auto rename format first using /autorename"
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
        quality = extract_quality(file_name)
        audio_type = extract_audio_type(file_name)

        template = format_template
        template = template.replace("{episode}", str(episode_number))
        template = template.replace("{season}", f"{season_number:02d}")
        template = template.replace("{quality}", quality)
        template = template.replace("{audio}", audio_type)

        _, file_extension = os.path.splitext(file_name)
        renamed_file_name = f"{template}{file_extension}"
        renamed_file_path = f"downloads/{renamed_file_name}"
        metadata_file_path = f"Metadata/{renamed_file_name}"

        os.makedirs(os.path.dirname(renamed_file_path), exist_ok=True)
        os.makedirs(os.path.dirname(metadata_file_path), exist_ok=True)

        if status_msg:
            download_msg = status_msg
            await download_msg.edit("Downloading your file...")
        else:
            download_msg = await message.reply_text("Downloading your file...")

        ph_path = None

        try:
            path = await concurrent_download(client, message, renamed_file_path, download_msg)
        except Exception as e:
            del renaming_operations[file_id]
            return await download_msg.edit(str(e))

        await download_msg.edit("Adding metadata...")

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

            upload_msg = await download_msg.edit("Uploading your file...")

            c_caption = await codeflixbots.get_caption(message.chat.id)
            c_thumb = await codeflixbots.get_thumbnail(message.chat.id)

            caption = (
                c_caption.format(
                    filename=renamed_file_name,
                    filesize=humanbytes(getattr(message.document, 'file_size', 0)),
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
                await download_msg.edit(f"✅ Completed: {renamed_file_name}")

            # Clean up
            for f in [path, ph_path, renamed_file_path, metadata_file_path]:
                if f and os.path.exists(f):
                    os.remove(f)
            if file_id in renaming_operations:
                del renaming_operations[file_id]

        except Exception as e:
            del renaming_operations[file_id]
            return await download_msg.edit(f"Metadata/Processing Error: {e}")

    except Exception as e:
        if 'file_id' in locals() and file_id in renaming_operations:
            del renaming_operations[file_id]
        raise

async def manual_rename_file(client, message, file_info, new_name):
    try:
        user_id = message.from_user.id
        file_id = file_info["file_id"]
        file_name = file_info["file_name"]
        media_preference = await codeflixbots.get_media_preference(user_id)

        if await check_anti_nsfw(file_name, message):
            return await message.reply_text("NSFW content detected. File upload rejected.")

        if file_id in renaming_operations:
            elapsed_time = (datetime.now() - renaming_operations[file_id]).seconds
            if elapsed_time < 10:
                return

        renaming_operations[file_id] = datetime.now()

        media_type = media_preference or "document"
        if file_name.endswith(".mp4"):
            media_type = "video"
        elif file_name.endswith(".mp3"):
            media_type = "audio"

        _, file_extension = os.path.splitext(file_name)
        if new_name.endswith(file_extension):
            renamed_file_name = new_name
        else:
            renamed_file_name = f"{new_name}{file_extension}"
        renamed_file_path = f"downloads/{renamed_file_name}"
        metadata_file_path = f"Metadata/{renamed_file_name}"
        os.makedirs(os.path.dirname(renamed_file_path), exist_ok=True)
        os.makedirs(os.path.dirname(metadata_file_path), exist_ok=True)

        download_msg = await message.reply_text("Downloading your file...")

        ph_path = None

        async with download_semaphore:
            try:
                path = await client.download_media(
                    message,
                    file_name=renamed_file_path,
                    progress=progress_for_pyrogram,
                    progress_args=("Download started...", download_msg, time.time()),
                )
            except Exception as e:
                del renaming_operations[file_id]
                return await download_msg.edit(str(e))

        await download_msg.edit("Adding metadata...")

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

            upload_msg = await download_msg.edit("Uploading your file...")

            c_caption = await codeflixbots.get_caption(message.chat.id)
            c_thumb = await codeflixbots.get_thumbnail(message.chat.id)

            caption = (
                c_caption.format(
                    filename=renamed_file_name,
                    filesize=humanbytes(getattr(message.document, 'file_size', 0)),
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

            async with upload_semaphore:
                try:
                    if media_type == "document":
                        await client.send_document(
                            message.chat.id,
                            document=path,
                            thumb=ph_path,
                            caption=caption,
                            progress=progress_for_pyrogram,
                            progress_args=("Upload started...", upload_msg, time.time()),
                        )
                    elif media_type == "video":
                        await client.send_video(
                            message.chat.id,
                            video=path,
                            caption=caption,
                            thumb=ph_path,
                            duration=0,
                            progress=progress_for_pyrogram,
                            progress_args=("Upload started...", upload_msg, time.time()),
                        )
                    elif media_type == "audio":
                        await client.send_audio(
                            message.chat.id,
                            audio=path,
                            caption=caption,
                            thumb=ph_path,
                            duration=0,
                            progress=progress_for_pyrogram,
                            progress_args=("Upload started...", upload_msg, time.time()),
                        )
                except Exception as e:
                    if os.path.exists(renamed_file_path):
                        os.remove(renamed_file_path)
                    if ph_path and os.path.exists(ph_path):
                        os.remove(ph_path)
                    del renaming_operations[file_id]
                    return await upload_msg.edit(str(e))

            await download_msg.delete()

            for f in [path, ph_path, renamed_file_path, metadata_file_path]:
                if f and os.path.exists(f):
                    os.remove(f)
            if file_id in renaming_operations:
                del renaming_operations[file_id]

        except Exception as e:
            del renaming_operations[file_id]
            return await download_msg.edit(f"Metadata/Processing Error: {e}")

    except Exception as e:
        if 'file_id' in locals() and file_id in renaming_operations:
            del renaming_operations[file_id]
        raise
