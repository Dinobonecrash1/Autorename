import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from helper.database import codeflixbots
from functools import wraps
from filerename import pending_manual_rename, manual_rename_file 
from file_rename import auto_rename_file


pending_manual_rename = {} 



def check_ban(func):
    @wraps(func)
    async def wrapper(client, message, *args, **kwargs):
        user_id = message.from_user.id
        user = await codeflixbots.col.find_one({"_id": user_id})
        if user and user.get("ban_status", {}).get("is_banned", False):
            return await message.reply_text("🚫 You are banned from using this bot.")
        return await func(client, message, *args, **kwargs)
    return wrapper


@Client.on_message(filters.private & filters.command("autorename"))
@check_ban
async def auto_rename_command(client, message):
    user_id = message.from_user.id

    # Extract and validate the format from the command
    command_parts = message.text.split(maxsplit=1)
    if len(command_parts) < 2 or not command_parts[1].strip():
        await message.reply_text(
            "**Please provide a new name after the command /autorename**\n\n"
            "Here's how to use it:\n"
            "**Example format:** `Naruto S[season]E[episode][quality][{audio}]`"
        )
        return

    format_template = command_parts[1].strip()

    # Save the format template in the database
    await codeflixbots.set_format_template(user_id, format_template)

    # Send confirmation message with the template in monospaced font
    await message.reply_text(
        f"**🌟 Fantastic! You're ready to auto-rename your files.**\n\n"
        "📩 Simply send the file(s) you want to rename.\n\n"
        f"**Your saved template:** `{format_template}`\n\n"
        "Remember, it might take some time, but I'll ensure your files are renamed perfectly!✨"
    )
    pass

@Client.on_message(filters.private & filters.command("setmedia"))
@check_ban
async def set_media_command(client, message):
    # Define inline keyboard buttons for media type selection
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📄 Document", callback_data="setmedia_document")],
        [InlineKeyboardButton("🎥 Video", callback_data="setmedia_video")]
    ])

    # Send a message with the inline buttons
    await message.reply_text(
        "**Please select the media type you want to set:**",
        reply_markup=keyboard
    )

@Client.on_callback_query(filters.regex("^setmedia_"))
async def handle_media_selection(client, callback_query):
    user_id = callback_query.from_user.id
    # 🔒 Ban check
    user = await codeflixbots.col.find_one({"_id": user_id})
    if user and user.get("ban_status", {}).get("is_banned", False):
        await callback_query.answer("🚫 You are banned from using this bot.", show_alert=True)
        return
        
    media_type = callback_query.data.split("_", 1)[1]  # Extract media type from callback data

    # Save the preferred media type in the database
    await codeflixbots.set_media_preference(user_id, media_type)

    # Acknowledge the callback and send confirmation
    await callback_query.answer(f"Media preference set to: {media_type} ✅")
    await callback_query.message.edit_text(f"**Media preference set to:** {media_type} ✅")

@Client.on_message(filters.private & (filters.document | filters.video | filters.audio))
@check_ban
async def handle_file(client, message):
    user_id = message.from_user.id
    mode = await codeflixbots.get_rename_mode(user_id)

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

    if mode == "manual":
        pending_manual_rename[user_id] = file_info
        await message.reply_text(
            f"File '{file_name}' received! Click 'START RENAME' to set a new name.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("START RENAME", callback_data="start_manual_rename")],
                [InlineKeyboardButton("CANCEL", callback_data="cancel_manual")]
            ])
        )
        return

    else:  # mode == "auto"
        asyncio.create_task(auto_rename_file(client, message, file_info))

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



