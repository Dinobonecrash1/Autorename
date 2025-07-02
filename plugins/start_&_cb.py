import random
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery

from helper.database import codeflixbots
from config import *
from config import Config
from functools import wraps
import humanize
from time import sleep

ADMIN_URL = Config.ADMIN_URL

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

# Start Command Handler
@Client.on_message(filters.private & filters.command("start"))
@check_ban
async def start(client, message: Message):
    user = message.from_user
    await codeflixbots.add_user(client, message)

    # Initial interactive text and sticker sequence
    m = await message.reply_text("Wᴇᴡ...Hᴏᴡ ᴀʀᴇ ʏᴏᴜ ᴅᴜᴅᴇ \nᴡᴀɪᴛ ᴀ ᴍᴏᴍᴇɴᴛ. . .")
    await asyncio.sleep(0.4)
    await m.edit_text("🎊")
    await asyncio.sleep(0.5)
    await m.edit_text("⚡")
    await asyncio.sleep(0.5)
    await m.edit_text("**Iᴀᴍ sᴛᴀʀᴛɪɴɢ...!!**")
    await asyncio.sleep(0.4)
    await m.delete()

    # Send sticker after the text sequence
    await message.reply_sticker("CAACAgUAAxkBAAEOzaBoX-Op03Qg8r9gLgYkdC4-cy_vUgACaxEAAkz3-Fd-hDy-se3CcTYE")

    # Define buttons for the start message
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("• ᴍʏ ᴀʟʟ ᴄᴏᴍᴍᴀɴᴅs •", callback_data='help')
        ], 
        [
            InlineKeyboardButton("Rename Mode ⚙️", callback_data='mode')
        ],
        [
            InlineKeyboardButton('• ᴀʙᴏᴜᴛ', callback_data='about'),
            InlineKeyboardButton('Dᴇᴠᴇʟᴏᴘᴇʀ•', url='https://t.me/Animeworld_zone')
        ]
    ])

    # Send start message with or without picture
    if Config.START_PIC:
        await message.reply_photo(
            Config.START_PIC,
            caption=Txt.START_TXT.format(user.mention),
            reply_markup=buttons
        )
    else:
        await message.reply_text(
            text=Txt.START_TXT.format(user.mention),
            reply_markup=buttons,
            disable_web_page_preview=True
        )

# Updated Callback Query Handler
@Client.on_callback_query()
async def cb_handler(client, query: CallbackQuery):
    data = query.data
    user_id = query.from_user.id

    user = await codeflixbots.col.find_one({"_id": user_id})
    if user and user.get("ban_status", {}).get("is_banned", False):
        await query.message.edit_text(
            "🚫 You are banned from using this bot.\n\nIf you think this is a mistake, contact the admin.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("📩 Contact Admin", url=ADMIN_URL)]]
            )
        )
        return

    # print(f"Callback data received: {data}")  # Debugging line

    if data == "home":
        await query.message.edit_text(
            text=Txt.START_TXT.format(query.from_user.mention),
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("• ᴍʏ ᴀʟʟ ᴄᴏᴍᴍᴀɴᴅs •", callback_data='help')],
                [InlineKeyboardButton("Rename Mode ⚙️", callback_data='mode')],
                [InlineKeyboardButton('• ᴀʙᴏᴜᴛ', callback_data='about'),
                 InlineKeyboardButton('Dᴇᴠᴇʟᴏᴘᴇʀ •', url='https://t.me/Animeworld_zone')]
            ])
        )

    if data == "mode":
        current_mode = await codeflixbots.get_rename_mode(user_id)
        auto_tick = "✅" if current_mode == "auto" else ""
        manual_tick = "✅" if current_mode == "manual" else ""

        await query.message.edit_text(
            "Choose your renaming mode:",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(f"Auto Rename {auto_tick}", callback_data="set_auto"),
                    InlineKeyboardButton(f"Manual Rename {manual_tick}", callback_data="set_manual")
                ],
                [InlineKeyboardButton("« Back", callback_data="help")]
             ])
         )
    
    elif data in ["set_auto", "set_manual"]:
        mode = "auto" if data == "set_auto" else "manual"
        await codeflixbots.set_rename_mode(user_id, mode)

        current_mode = await codeflixbots.get_rename_mode(user_id)
        auto_tick = "✅" if current_mode == "auto" else ""
        manual_tick = "✅" if current_mode == "manual" else ""

        await query.message.edit_text(
            f"Choose your renaming mode:\n\nCurrent Mode: **{current_mode.upper()}**",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(f"Auto Rename {auto_tick}", callback_data="set_auto"),
                    InlineKeyboardButton(f"Manual Rename {manual_tick}", callback_data="set_manual")
                ],
                [InlineKeyboardButton("« Back", callback_data="help")]
            ]) 
           )

    elif data == "caption":
        await query.message.edit_text(
            text=Txt.CAPTION_TXT,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("• sᴜᴘᴘᴏʀᴛ", url='https://t.me/Animeworld_zone'), InlineKeyboardButton("ʙᴀᴄᴋ •", callback_data="help")]
            ])
        )

    elif data == "help":
        await query.message.edit_text(
            text=Txt.HELP_TXT.format(client.mention),
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("• ᴀᴜᴛᴏ ʀᴇɴᴀᴍᴇ ғᴏʀᴍᴀᴛ •", callback_data='file_names')],
                [InlineKeyboardButton('• ᴛʜᴜᴍʙɴᴀɪʟ', callback_data='thumbnail'), InlineKeyboardButton('ᴄᴀᴘᴛɪᴏɴ •', callback_data='caption')],
                [InlineKeyboardButton('• ᴍᴇᴛᴀᴅᴀᴛᴀ', callback_data='metadata'), InlineKeyboardButton('ᴅᴏɴᴀᴛᴇ •', callback_data='donate')],
                [InlineKeyboardButton('• ʜᴏᴍᴇ', callback_data='home')]
            ])
        )

    elif data == "metadata":
        current = await codeflixbots.get_metadata(user_id)
        title = await codeflixbots.get_title(user_id)
        author = await codeflixbots.get_author(user_id)
        artist = await codeflixbots.get_artist(user_id)
        video = await codeflixbots.get_video(user_id)
        audio = await codeflixbots.get_audio(user_id)
        subtitle = await codeflixbots.get_subtitle(user_id)
        encoded_by = await codeflixbots.get_encoded_by(user_id)
        custom_tag = await codeflixbots.get_custom_tag(user_id)

        text = f"""
㊋ Yᴏᴜʀ Mᴇᴛᴀᴅᴀᴛᴀ ɪꜱ ᴄᴜʀʀᴇɴᴛʟʏ: {current}

◈ Tɪᴛʟᴇ ▹ {title or 'Nᴏᴛ ꜰᴏᴜɴᴅ'}  
◈ Aᴜᴛʜᴏʀ ▹ {author or 'Nᴏᴛ ꜰᴏᴜɴᴅ'}  
◈ Aʀᴛɪꜱᴛ ▹ {artist or 'Nᴏᴛ ꜰᴏᴜɴᴅ'}  
◈ Aᴜᴅɪᴏ ▹ {audio or 'Nᴏᴛ ꜰᴏᴜɴᴅ'}  
◈ Sᴜʙᴛɪᴛʟᴇ ▹ {subtitle or 'Nᴏᴛ ꜰᴏᴜɴᴅ'}  
◈ Vɪᴅᴇᴏ ▹ {video or 'Nᴏᴛ ꜰᴏᴜɴᴅ'}  
◈ Eɴᴄᴏᴅᴇᴅ Bʏ ▹ {encoded_by or 'Nᴏᴛ ꜰᴏᴜɴᴅ'}  
◈ Cᴜsᴛᴏᴍ Tᴀɢ ▹ {custom_tag or 'Nᴏᴛ ꜰᴏᴜɴᴅ'}
        """

        buttons = [
            [
                InlineKeyboardButton(f"On{' ✅' if current == 'On' else ''}", callback_data='on_metadata'),
                InlineKeyboardButton(f"Off{' ✅' if current == 'Off' else ''}", callback_data='off_metadata')
            ],
            [
                InlineKeyboardButton("How to Set Metadata", callback_data="metainfo"),
                InlineKeyboardButton("« Back", callback_data="help")
            ]
        ]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), disable_web_page_preview=True)

    elif data == "start":
        await query.answer()
        await query.message.edit_text(
            text=Txt.START_TXT.format(query.from_user.mention),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("• ᴍʏ ᴀʟʟ ᴄᴏᴍᴍᴀɴᴅs •", callback_data='help')],
                [InlineKeyboardButton("Rename Mode ⚙️", callback_data='mode')],
                [InlineKeyboardButton('• ᴀʙᴏᴜᴛ', callback_data='about'),
                 InlineKeyboardButton('Dᴇᴠᴇʟᴏᴘᴇʀ •', url='https://t.me/Animeworld_zone')]
            ]),
            disable_web_page_preview=True
        )

    elif data == "commands":
        await query.answer()
        await query.message.edit_text(
            text=Txt.HELP_TXT.format(client.mention),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("• ᴀᴜᴛᴏ ʀᴇɴᴀᴍᴇ ғᴏʀᴍᴀᴛ •", callback_data='file_names')],
                [InlineKeyboardButton('• ᴛʜᴜᴍʙɴᴀɪʟ', callback_data='thumbnail'), InlineKeyboardButton('ᴄᴀᴘᴛɪᴏɴ •', callback_data='caption')],
                [InlineKeyboardButton('• ᴍᴇᴛᴀᴅᴀᴛᴀ', callback_data='metadata'), InlineKeyboardButton('ᴅᴏɴᴀᴛᴇ •', callback_data='donate')],
                [InlineKeyboardButton('• ʜᴏᴍᴇ', callback_data='start')]
            ]),
            disable_web_page_preview=True
        )

    elif data == "donate":
        await query.message.edit_text(
            text=Txt.DONATE_TXT,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("• ʙᴀᴄᴋ", callback_data="help"), InlineKeyboardButton("ᴏᴡɴᴇʀ •", url='https://t.me/Animeworld_zone')]
            ])
        )
    elif data == "file_names":
        format_template = await codeflixbots.get_format_template(user_id)

        await query.message.edit_text(
            text=Txt.FILE_NAME_TXT.format(format_template=format_template),
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("• ᴄʟᴏsᴇ", callback_data="close"), InlineKeyboardButton("ʙᴀᴄᴋ •", callback_data="help")]
            ])
        )
    elif data == "thumbnail":
        try:
            await query.message.edit_caption(
                caption=Txt.THUMBNAIL_TXT,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("• ᴄʟᴏsᴇ", callback_data="close"), InlineKeyboardButton("ʙᴀᴄᴋ •", callback_data="help")]
                ])
            )
        except Exception:
            await query.message.edit_text(
                text=Txt.THUMBNAIL_TXT,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("• ᴄʟᴏsᴇ", callback_data="close"), InlineKeyboardButton("ʙᴀᴄᴋ •", callback_data="help")]
                ])
            )
        return
    
    elif data == "about":
        await query.message.edit_text(
            text=Txt.ABOUT_TXT,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("ᴄʟᴏsᴇ", callback_data="close"),
                InlineKeyboardButton("ʙᴀᴄᴋ", callback_data="home")
            ]])          
        )
    
    elif data == "close":
        try:
            await query.message.delete()
            if query.message.reply_to_message:
                await query.message.reply_to_message.delete()
        except Exception as e:
            pass  # Optionally log e
        return

from pyrogram import Client, filters
from pyrogram.types import (
    Message, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup, 
    CallbackQuery, 
    ForceReply
)
from helper.database import codeflixbots
import humanize

# FILE: manual_rename_flow.py

@Client.on_message(filters.private & (filters.document | filters.audio | filters.video))
async def rename_start(client, message: Message):
    user_id = message.from_user.id
    mode = await codeflixbots.get_rename_mode(user_id)
    if mode != "manual":
        return  # Only prompt in manual mode

    file = getattr(message, message.media.value)
    filename = file.file_name
    filesize = humanize.naturalsize(file.file_size)

    if file.file_size > 2000 * 1024 * 1024:
        return await message.reply_text(
            "Sorry, this bot doesn't support files larger than 2GB."
        )

    text = (
        f"**__What do you want me to do with this file?__**\n\n"
        f"**File Name** :- `{filename}`\n"
        f"**File Size** :- `{filesize}`"
    )
    buttons = [
        [InlineKeyboardButton("📝 Start Rename", callback_data="rename")],
        [InlineKeyboardButton("✖️ Cancel", callback_data="close")]
    ]
    await message.reply_text(
        text=text,
        reply_to_message_id=message.id,
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@Client.on_callback_query(filters.regex("^rename$"))
async def manual_rename_ask_name(client, query: CallbackQuery):
    user_id = query.from_user.id
    mode = await codeflixbots.get_rename_mode(user_id)
    if mode != "manual":
        return await query.answer("Manual renaming is only available in manual mode.", show_alert=True)
    await query.message.delete()
    await query.message.reply_text(
        "__Please enter new file name...__",
        reply_to_message_id=query.message.reply_to_message.id if query.message.reply_to_message else None,
        reply_markup=ForceReply(True)
    )

@Client.on_message(filters.private & filters.reply)
async def manual_rename_receive_name(client, message: Message):
    reply_message = message.reply_to_message
    if not isinstance(reply_message.reply_markup, ForceReply):
        return  # Only handle replies to ForceReply
    user_id = message.from_user.id
    mode = await codeflixbots.get_rename_mode(user_id)
    if mode != "manual":
        return await message.reply("Manual renaming is only available in manual mode.\nSwitch to manual mode first.")

    new_name = message.text
    await message.delete()
    msg = await client.get_messages(message.chat.id, reply_message.id)
    file = msg.reply_to_message
    media = getattr(file, file.media.value)
    if '.' not in new_name:
        extn = media.file_name.rsplit('.', 1)[-1] if '.' in media.file_name else "mkv"
        new_name += '.' + extn
    await reply_message.delete()

    buttons = [
        [InlineKeyboardButton("📁 Document", callback_data="upload_document")]
    ]
    from pyrogram.enums import MessageMediaType
    if file.media in [MessageMediaType.VIDEO, MessageMediaType.DOCUMENT]:
        buttons.append([InlineKeyboardButton("🎥 Video", callback_data="upload_video")])
    elif file.media == MessageMediaType.AUDIO:
        buttons.append([InlineKeyboardButton("🎵 Audio", callback_data="upload_audio")])

    await message.reply(
        text=f"**Select the output file type**\n**• File Name :-**  `{new_name}`",
        reply_to_message_id=file.id,
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# (You must have your upload handler for "upload_document", "upload_video", etc., elsewhere)
