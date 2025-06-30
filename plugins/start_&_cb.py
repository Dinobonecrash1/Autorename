
import random
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery

from helper.database import codeflixbots
from config import *
from config import Config
from functools import wraps


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


#Updated Callback Query Handler
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

    
    print(f"Callback data received: {data}")  # Debugging lin

    if data == "home":
        await query.message.edit_text(
            text=Txt.START_TXT.format(query.from_user.mention),
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("• ᴍʏ ᴀʟʟ ᴄᴏᴍᴍᴀɴᴅs •", callback_data='help')], [InlineKeyboardButton("Rename Mode ⚙️", callback_data='mode')],

                [InlineKeyboardButton('• ᴀʙᴏᴜᴛ', callback_data='about'), InlineKeyboardButton('Dᴇᴠᴇʟᴏᴘᴇʀ •', url='https://t.me/Animeworld_zone')]
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
                [InlineKeyboardButton("• ᴍʏ ᴀʟʟ ᴄᴏᴍᴍᴀɴᴅs •", callback_data='help')], [InlineKeyboardButton("Rename Mode ⚙️", callback_data='mode')
            ],
                [InlineKeyboardButton('• ᴀʙᴏᴜᴛ', callback_data='about'), InlineKeyboardButton('Dᴇᴠᴇʟᴏᴘᴇʀ •', url='https://t.me/Animeworld_zone')]
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
        await query.message.edit_caption(
            caption=Txt.THUMBNAIL_TXT,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("• ᴄʟᴏsᴇ", callback_data="close"), InlineKeyboardButton("ʙᴀᴄᴋ •", callback_data="help")]
            ])
       )
    
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
            await query.message.reply_to_message.delete()
            await query.message.continue_propagation()
        except:
            await query.message.delete()
            await query.message.continue_propagation()

   
