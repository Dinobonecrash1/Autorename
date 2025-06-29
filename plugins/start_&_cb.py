import random
import asyncio
import logging
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from helper.database import codeflixbots
from config import Config, Txt
from metadata import metadata  # Import metadata function

# Set up logging
logging.basicConfig(level=logging.INFO, handlers=[logging.FileHandler('bot.log'), logging.StreamHandler()])
logger = logging.getLogger(__name__)

async def edit_message_safely(query, text, reply_markup):
    try:
        if query.message.photo:
            await query.message.edit_caption(caption=text, reply_markup=reply_markup)
        else:
            await query.message.edit_text(text=text, disable_web_page_preview=True, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Error editing message: {e}")
        await query.message.reply_text("An error occurred while updating the message.")

# Start Command Handler
@Client.on_message(filters.private & filters.command("start"))
async def start(client, message: Message):
    user = message.from_user
    try:
        await codeflixbots.add_user(client, message)
    except Exception as e:
        logger.error(f"Error adding user {user.id}: {e}")

    states = ["Wᴇᴡ...Hᴏᴡ ᴀʀᴇ ʏᴏᴜ ᴅᴜᴅᴇ \nᴡᴀɪᴛ ᴀ ᴍᴏᴍᴇɴᴛ. . .", "🎊", "⚡", "**Iᴀᴍ sᴛᴀʀᴛɪɴɢ...!!**"]
    m = await message.reply_text(states[0])
    for state in states[1:]:
        await asyncio.sleep(0.4)
        await m.edit_text(state)
    await asyncio.sleep(0.4)
    await m.delete()

    try:
        await message.reply_sticker("CAACAgUAAxkBAAEOzaBoX-Op03Qg8r9gLgYkdC4-cy_vUgACaxEAAkz3-Fd-hDy-se3CcTYE")
    except Exception as e:
        logger.error(f"Error sending sticker: {e}")

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("• ᴍʏ ᴀʟʟ ᴄᴏᴍᴍᴀɴᴅs •", callback_data='help')],
        [InlineKeyboardButton('• ᴀʙᴏᴜᴛ', callback_data='about'),
         InlineKeyboardButton('Dᴇᴠᴇʟᴏᴘᴇʀ•', url=Config.SUPPORT_URL)]
    ])

    try:
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
    except Exception as e:
        logger.error(f"Error sending start message: {e}")
        await message.reply_text("An error occurred while starting the bot.")

# Callback Query Handler
@Client.on_callback_query()
async def cb_handler(client, query: CallbackQuery):
    data = query.data
    user_id = query.from_user.id
    
    logger.info(f"Callback data received: {data}")

    try:
        if data == "home":
            await edit_message_safely(
                query,
                text=Txt.START_TXT.format(query.from_user.mention),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("• ᴍʏ ᴀʟʟ ᴄᴏᴍᴍᴀɴᴅs •", callback_data='help')],
                    [InlineKeyboardButton('• ᴀʙᴏᴜᴛ', callback_data='about'), 
                     InlineKeyboardButton('Dᴇᴠᴇʟᴏᴘᴇʀ •', url=Config.SUPPORT_URL)]
                ])
            )
        elif data == "caption":
            await edit_message_safely(
                query,
                text=Txt.CAPTION_TXT,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("• sᴜᴘᴘᴏʀᴛ", url=Config.SUPPORT_URL), 
                     InlineKeyboardButton("ʙᴀᴄᴋ •", callback_data="help")]
                ])
            )
        elif data == "help":
            await edit_message_safely(
                query,
                text=Txt.HELP_TXT.format(client.mention),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("• ᴀᴜᴛᴏ ʀᴇɴᴀᴍᴇ ғᴏʀᴍᴀᴛ •", callback_data='file_names')],
                    [InlineKeyboardButton('• ᴛʜᴜᴍʙɴᴀɪʟ', callback_data='thumbnail'), 
                     InlineKeyboardButton('ᴄᴀᴘᴛɪᴏɴ •', callback_data='caption')],
                    [InlineKeyboardButton('• ᴍᴇᴛᴀᴅᴀᴛᴀ', callback_data='metadata'), 
                     InlineKeyboardButton('ᴅᴏɴᴀᴛᴇ •', callback_data='donate')],
                    [InlineKeyboardButton('• ʜᴏᴍᴇ', callback_data='home')]
                ])
            )
        elif data == "metadata":
            await metadata(client, query.message)
        elif data == "donate":
            await edit_message_safely(
                query,
                text=Txt.DONATE_TXT,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("• ʙᴀᴄᴋ", callback_data="help"), 
                     InlineKeyboardButton("ᴏᴡɴᴇʀ •", url=Config.SUPPORT_URL)]
                ])
            )
        elif data == "file_names":
            try:
                format_template = await codeflixbots.get_format_template(user_id)
                await edit_message_safely(
                    query,
                    text=Txt.FILE_NAME_TXT.format(format_template=format_template),
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("• ᴄʟᴏsᴇ", callback_data="close"), 
                         InlineKeyboardButton("ʙᴀᴄᴋ •", callback_data="help")]
                    ])
                )
            except Exception as e:
                logger.error(f"Error fetching format template for user {user_id}: {e}")
                await query.message.reply_text("An error occurred while retrieving file name settings.")
        elif data == "thumbnail":
            await edit_message_safely(
                query,
                text=Txt.THUMBNAIL_TXT,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("• ᴄʟᴏsᴇ", callback_data="close"), 
                     InlineKeyboardButton("ʙᴀᴄᴋ •", callback_data="help")]
                ])
            )
        elif data == "about":
            await edit_message_safely(
                query,
                text=Txt.ABOUT_TXT,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("ᴄʟᴏsᴇ", callback_data="close"),
                     InlineKeyboardButton("ʙᴀᴄᴋ", callback_data="home")]
                ])
            )
        elif data == "close":
            try:
                await query.message.delete()
                if query.message.reply_to_message:
                    await query.message.reply_to_message.delete()
            except Exception as e:
                logger.error(f"Error in close callback: {e}")
                await query.message.reply_text("An error occurred while closing the message.")
    except Exception as e:
        logger.error(f"Error handling callback {data}: {e}")
        await query.message.reply_text("An error occurred while processing your request.")
