import random
import asyncio
from pyrogram import Client, filters
from helper.database import codeflixbots 
from config import Txt
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from config import Config

# Import the metadata function from the first code snippet
async def metadata(client, message):
    user_id = message.from_user.id

    # Fetch user metadata from the database
    current = await db.get_metadata(user_id)
    title = await db.get_title(user_id)
    author = await db.get_author(user_id)
    artist = await db.get_artist(user_id)
    video = await db.get_video(user_id)
    audio = await db.get_audio(user_id)
    subtitle = await db.get_subtitle(user_id)
    encoded_by = await db.get_encoded_by(user_id)
    custom_tag = await db.get_custom_tag(user_id)

    # Display the current metadata
    text = f"""
**㊋ Yᴏᴜʀ Mᴇᴛᴀᴅᴀᴛᴀ ɪꜱ ᴄᴜʀʀᴇɴᴛʟʏ: {current}**

**◈ Tɪᴛʟᴇ ▹** `{title if title else 'Nᴏᴛ ꜰᴏᴜɴᴅ'}`  
**◈ Aᴜᴛʜᴏʀ ▹** `{author if author else 'Nᴏᴛ ꜰᴏᴜɴᴅ'}`  
**◈ Aʀᴛɪꜱᴛ ▹** `{artist if artist else 'Nᴏᴛ ꜰᴏᴜɴᴅ'}`  
**◈ Aᴜᴅɪᴏ ▹** `{audio if audio else 'Nᴏᴛ ꜰᴏᴜɴᴅ'}`  
**◈ Sᴜʙᴛɪᴛʟᴇ ▹** `{subtitle if subtitle else 'Nᴏᴛ ꜰᴏᴜɴᴅ'}`  
**◈ Vɪᴅᴇᴏ ▹** `{video if video else 'Nᴏᴛ ꜰᴏᴜɴᴅ'}`  
**◈ Eɴᴄᴏᴅᴇᴅ Bʏ ▹** `{encoded_by if encoded_by else 'Nᴏᴛ ꜰᴏᴜɴᴅ'}`
**◈ Cᴜsᴛᴏᴍ Tᴀɢ ▹** `{custom_tag if custom_tag else 'Nᴏᴛ ꜰᴏᴜɴᴅ'}`
    """

    # Inline buttons to toggle metadata
    buttons = [
        [
            InlineKeyboardButton(f"On{' ✅' if current == 'On' else ''}", callback_data='on_metadata'),
            InlineKeyboardButton(f"Off{' ✅' if current == 'Off' else ''}", callback_data='off_metadata')
        ],
        [
            InlineKeyboardButton("How to Set Metadata", callback_data="metainfo")
        ]
    ]
    keyboard = InlineKeyboardMarkup(buttons)

    await message.reply_text(text=text, reply_markup=keyboard, disable_web_page_preview=True)
    
# Start Command Handler
@Client.on_message(filters.private & filters.command("start"))
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


Updated Callback Query Handler
@Client.on_callback_query()
async def cb_handler(client, query: CallbackQuery):
    data = query.data
    user_id = query.from_user.id

    # Debugging log (replace print with logging if needed)
    logger.info(f"Callback data received: {data}")

    if data == "home":
        await query.message.edit_text(
            text=Txt.START_TXT.format(query.from_user.mention),
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("My All Commands", callback_data='help')],
                [InlineKeyboardButton('About', callback_data='about'), InlineKeyboardButton('Developer', url='https://t.me/Animeworld_zone')]
            ])
        )
    elif data == "caption":
        await query.message.edit_text(
            text=Txt.CAPTION_TXT,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Support", url='https://t.me/Animeworld_zone'), InlineKeyboardButton("Back", callback_data="help")]
            ])
        )
    elif data == "help":
        await query.message.edit_text(
            text=Txt.HELP_TXT.format(client.mention),
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Auto Rename Format", callback_data='file_names')],
                [InlineKeyboardButton('Thumbnail', callback_data='thumbnail'), InlineKeyboardButton('Caption', callback_data='caption')],
                [InlineKeyboardButton('Metadata', callback_data='meta'), InlineKeyboardButton('Donate', callback_data='donate')],
                [InlineKeyboardButton('Home', callback_data='home')]
            ])
        )
    elif data == "meta":
        # Call the metadata function instead of editing with Txt.SEND_METADATA
        try:
            await metadata(client, query.message)
        except Exception as e:
            await query.message.edit_text("Error fetching metadata. Please try again later.")
            logger.error(f"Metadata error: {e}")
    elif data == "donate":
        await query.message.edit_text(
            text=Txt.DONATE_TXT,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Back", callback_data="help"), InlineKeyboardButton("Owner", url='https://t.me/Animeworld_zone')]
            ])
        )
    elif data == "file_names":
        try:
            format_template = await db.get_format_template(user_id)
            await query.message.edit_text(
                text=Txt.FILE_NAME_TXT.format(format_template=format_template),
                disable_web_page_preview=True,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Close", callback_data="close"), InlineKeyboardButton("Back", callback_data="help")]
                ])
            )
        except Exception as e:
            await query.message.edit_text("Error fetching format template. Please try again later.")
            logger.error(f"File names error: {e}")
    elif data == "thumbnail":
        # Handle case where message may not have a photo
        try:
            if query.message.photo:
                await query.message.edit_caption(
                    caption=Txt.THUMBNAIL_TXT,
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("Close", callback_data="close"), InlineKeyboardButton("Back", callback_data="help")]
                    ])
                )
            else:
                await query.message.edit_text(
                    text=Txt.THUMBNAIL_TXT,
                    disable_web_page_preview=True,
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("Close", callback_data="close"), InlineKeyboardButton("Back", callback_data="help")]
                    ])
                )
        except Exception as e:
            await query.message.edit_text("Error updating thumbnail info. Please try again later.")
            logger.error(f"Thumbnail error: {e}")
    elif data == "on_metadata" or data == "off_metadata":
        try:
            await db.set_metadata(user_id, "On" if data == "on_metadata" else "Off")
            await query.answer(f"Metadata turned {'On' if data == 'on_metadata' else 'Off'}")
            # Refresh metadata display
            await metadata(client, query.message)
        except Exception as e:
            await query.message.edit_text("Error updating metadata status. Please try again later.")
            logger.error(f"Metadata toggle error: {e}")
    elif data == "metainfo":
        await query.message.edit_text(
            text=Txt.META_TXT,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Home", callback_data="start"), InlineKeyboardButton("Back", callback_data="help")]
            ])
        )
    elif data == "about":
        await query.message.edit_text(
            text=Txt.ABOUT_TXT,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Close", callback_data="close"), InlineKeyboardButton("Back", callback_data="home")]
            ])
        )
    elif data == "close":
        try:
            await query.message.delete()
            if query.message.reply_to_message:
                await query.message.reply_to_message.delete()
        except Exception:
            pass
