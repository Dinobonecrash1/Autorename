import random
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from helper.database import Botskingdom
from config import *
from config import Config

# Start Command Handler
@Client.on_message(filters.private & filters.command("start"))
async def start(client, message: Message):
    user = message.from_user
    await Botskingdom.add_user(client, message)
    
    # Initial interactive text and sticker sequence
    m = await message.reply_text("Wᴇᴡ...Hᴏᴡ ᴀʀᴇ ʏᴏᴜ babe \nᴡᴀɪᴛ ᴀ ᴍᴏᴍᴇɴᴛ. . .")
    await asyncio.sleep(0.4)
    await m.edit_text("❤️")
    await asyncio.sleep(0.5)
    await m.edit_text("💋")
    await asyncio.sleep(0.5)
    await m.edit_text("**Iᴀᴍ sᴛᴀʀᴛɪɴɢ...!!**")
    await asyncio.sleep(0.4)
    await m.delete()
    
    # Send sticker after the text sequence
    await message.reply_sticker("CAACAgEAAx0Cf13_kwABAa9GaK9NXH7fWy5owht-mWlSnd0JwEsAAo8DAAJOqkhEbO-AaeBKHS82BA")
    
    # Define buttons for the start message
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("• ᴍʏ ᴀʟʟ ᴄᴏᴍᴍᴀɴᴅs •", callback_data='help')],
        [InlineKeyboardButton('• ᴀʙᴏᴜᴛ', callback_data='about'),
         InlineKeyboardButton('Dᴇᴠᴇʟᴏᴘᴇʀ•', url='https://t.me/Zenitsu_AF')]
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
    print(f"Callback data received: {data}")  # Debugging line
    
    try:
        if data == "home":
            await query.message.edit_text(
                text=Txt.START_TXT.format(query.from_user.mention),
                disable_web_page_preview=True,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("• ᴍʏ ᴀʟʟ ᴄᴏᴍᴍᴀɴᴅs •", callback_data='help')],
                    [InlineKeyboardButton('• ᴀʙᴏᴜᴛ', callback_data='about'), 
                     InlineKeyboardButton('Dᴇᴠᴇʟᴏᴘᴇʀ •', url='https://t.me/Zenitsu_AF')]
                ])
            )
        
        elif data == "caption":
            await query.message.edit_text(
                text=Txt.CAPTION_TXT,
                disable_web_page_preview=True,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("• sᴜᴘᴘᴏʀᴛ", url='https://t.me/Flame_Bots'), 
                     InlineKeyboardButton("ʙᴀᴄᴋ •", callback_data="help")]
                ])
            )
        
        elif data == "help":
            await query.message.edit_text(
                text=Txt.HELP_TXT.format(client.mention),
                disable_web_page_preview=True,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("• ᴀᴜᴛᴏ ʀᴇɴᴀᴍᴇ ғᴏʀᴍᴀᴛ •", callback_data='file_names')],
                    [InlineKeyboardButton('• ᴛʜᴜᴍʙɴᴀɪʟ', callback_data='thumbnail'), 
                     InlineKeyboardButton('ᴄᴀᴘᴛɪᴏɴ •', callback_data='caption')],
                    [InlineKeyboardButton('• ᴍᴇᴛᴀᴅᴀᴛᴀ', callback_data='meta'), 
                     InlineKeyboardButton('Premium•', callback_data='donate')],
                    [InlineKeyboardButton('• ʜᴏᴍᴇ', callback_data='home')]
                ])
            )
        
        elif data == "meta":
            await query.message.edit_text(
                text=Txt.SEND_METADATA,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("• ᴄʟᴏsᴇ", callback_data="close"), 
                     InlineKeyboardButton("ʙᴀᴄᴋ •", callback_data="help")]
                ])
            )
        
        elif data == "donate":
            await query.message.edit_text(
                text=Txt.DONATE_TXT,
                disable_web_page_preview=True,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("• ʙᴀᴄᴋ", callback_data="help"), 
                     InlineKeyboardButton("ᴏᴡɴᴇʀ •", url='https://t.me/Zenitsu_AF')]
                ])
            )
        
        elif data == "file_names":
            # Fixed: Added proper error handling and fallback for auto rename format
            try:
                format_template = await Botskingdom.get_format_template(user_id)
                if format_template is None:
                    format_template = "{filename}"  # Default format template
            except AttributeError:
                # Handle case where get_format_template method doesn't exist
                print("get_format_template method not found, using default")
                format_template = "{filename}"
            except Exception as e:
                print(f"Error getting format template: {e}")
                format_template = "{filename}"  # Fallback format template
            
            await query.message.edit_text(
                text=Txt.FILE_NAME_TXT.format(format_template=format_template),
                disable_web_page_preview=True,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("• ᴄʟᴏsᴇ", callback_data="close"), 
                     InlineKeyboardButton("ʙᴀᴄᴋ •", callback_data="help")]
                ])
            )
        
        elif data == "thumbnail":
            await query.message.edit_caption(
                caption=Txt.THUMBNAIL_TXT,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("• ᴄʟᴏsᴇ", callback_data="close"), 
                     InlineKeyboardButton("ʙᴀᴄᴋ •", callback_data="help")]
                ])
            )
        
        elif data == "metadatax":
            await query.message.edit_caption(
                caption=Txt.SEND_METADATA,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("• ᴄʟᴏsᴇ", callback_data="close"), 
                     InlineKeyboardButton("ʙᴀᴄᴋ •", callback_data="help")]
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
                if query.message.reply_to_message:
                    await query.message.reply_to_message.delete()
            except Exception as e:
                print(f"Error deleting message: {e}")
                try:
                    await query.message.delete()
                except:
                    pass
        
        # Answer the callback query to prevent timeout
        await query.answer()
        
    except Exception as e:
        print(f"Error in callback handler: {e}")
        await query.answer("Something went wrong! Please try again.", show_alert=True)
