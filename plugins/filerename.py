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

ADMIN_URL = Config.ADMIN_URL

pending_manual_rename = {}  # Store pending manual rename requests
renaming_operations = {}

# --- Semaphore for concurrent operations ---
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

@Client.on_message(filters.private & (filters.document | filters.video | filters.audio))
@check_ban
async def initiate_manual_rename(client, message):
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
        "message": message
    }
    pending_manual_rename[user_id] = file_info
    await message.reply_text(
        f"File '{file_name}' received! Click 'START RENAME' to set a new name.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("START RENAME", callback_data="start_manual_rename")],
            [InlineKeyboardButton("CANCEL", callback_data="cancel_manual")]
        ])
    )

@Client.on_callback_query(filters.regex("^start_manual_rename"))
async def start_manual_rename(client, callback_query):
    user_id = callback_query.from_user.id
    if user_id not in pending_manual_rename:
        await callback_query.answer("No file is pending for renaming.", show_alert=True)
        return
    
    file_info = pending_manual_rename[user_id]
    await callback_query.message.edit_text(
        f"Current file: {file_info['file_name']}\nPlease enter the new file name:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("CANCEL", callback_data="cancel_manual")]
        ])
    )

@Client.on_message(filters.private & filters.text & filters.reply)
@check_ban
async def manual_rename_reply(client, message):
    user_id = message.from_user.id
    if user_id not in pending_manual_rename:
        return

    new_name = message.text.strip()
    if not new_name:
        await message.reply_text("Please provide a valid file name.")
        return

    file_info = pending_manual_rename.pop(user_id)
    await manual_rename_file(client, message, file_info, new_name)

@Client.on_callback_query(filters.regex("^cancel_manual"))
async def cancel_manual_rename(client, callback_query):
    user_id = callback_query.from_user.id
    if user_id in pending_manual_rename:
        del pending_manual_rename[user_id]
        await callback_query.message.edit_text("Manual rename cancelled.")
    else:
        await callback_query.answer("No pending manual rename to cancel.", show_alert=True)

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
        renamed_file_name = f"{new_name}{file_extension}"
        renamed_file_path = f"downloads/{renamed_file_name}"
        metadata_file_path = f"Metadata/{renamed_file_name}"
        os.makedirs(os.path.dirname(renamed_file_path), exist_ok=True)
        os.makedirs(os.path.dirname(metadata_file_path), exist_ok=True)

        download_msg = await message.reply_text("Downloading your file...!!")

        ph_path = None

        async with download_semaphore:
            try:
                path = await client.download_media(
                    message,
                    file_name=renamed_file_path,
                    progress=progress_for_pyrogram,
                    progress_args=("Download started dude....!!", download_msg, time.time()),
                )
            except Exception as e:
                del renaming_operations[file_id]
                return await download_msg.edit(str(e))

        await download_msg.edit("Adding metadata dude...!!")

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
            
            upload_msg = await download_msg.edit("Uploading your file...!!")

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
                def _resize_thumb(path):
                    img = Image.open(path).convert("RGB")
                    img = img.resize((320, 320))
                    img.save(path, "JPEG")
                await asyncio.to_thread(_resize_thumb, ph_path)

            async with upload_semaphore:
                try:
                    if media_type == "document":
                        await client.send_document(
                            message.chat.id,
                            document=path,
                            thumb=ph_path,
                            caption=caption,
                            progress=progress_for_pyrogram,
                            progress_args=("Upload started dude...!!", upload_msg, time.time()),
                        )
                    elif media_type == "video":
                        await client.send_video(
                            message.chat.id,
                            video=path,
                            caption=caption,
                            thumb=ph_path,
                            duration=0,
                            progress=progress_for_pyrogram,
                            progress_args=("Upload started dude...!!", upload_msg, time.time()),
                        )
                    elif media_type == "audio":
                        await client.send_audio(
                            message.chat.id,
                            audio=path,
                            caption=caption,
                            thumb=ph_path,
                            duration=0,
                            progress=progress_for_pyrogram,
                            progress_args=("Upload started dude...!!", upload_msg, time.time()),
                        )
                except Exception as e:
                    if os.path.exists(renamed_file_path):
                        os.remove(renamed_file_path)
                    if ph_path and os.path.exists(ph_path):
                        os.remove(ph_path)
                    del renaming_operations[file_id]
                    return await upload_msg.edit(str(e))

            await download_msg.delete()

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