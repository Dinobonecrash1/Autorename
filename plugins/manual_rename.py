from pyrogram import Client, filters
from pyrogram.types import Message
from helper.database import codeflixbots

from .file_rename import auto_rename_file, check_ban  # assuming file_rename.py is in the same directory

@Client.on_message(filters.private & filters.command("rename"))
@check_ban
async def manual_rename_command(client, message: Message):
    # Must be a reply to a file
    if not message.reply_to_message:
        await message.reply_text("Please reply to the file you want to rename with:\n`/rename NewFileName.ext`")
        return

    command_parts = message.text.split(maxsplit=1)
    if len(command_parts) < 2 or not command_parts[1].strip():
        await message.reply_text("Please provide the new file name! Example: `/rename MyVideo.mp4`")
        return
    new_file_name = command_parts[1].strip()

    reply = message.reply_to_message
    if reply.document:
        file_id = reply.document.file_id
        orig_file_name = reply.document.file_name or "Unknown"
    elif reply.video:
        file_id = reply.video.file_id
        orig_file_name = reply.video.file_name or "Unknown"
    elif reply.audio:
        file_id = reply.audio.file_id
        orig_file_name = reply.audio.file_name or "Unknown"
    else:
        await message.reply_text("Please reply to a document, video, or audio file!")
        return

    file_info = {
        "file_id": file_id,
        "file_name": orig_file_name,
        "message": reply,
        "manual_new_name": new_file_name  # pass new name down
    }
    await auto_rename_file(client, message, file_info, is_sequence=False, status_msg=None, manual_rename=True)