import logging
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from helper.database import codeflixbots as db
from config import Txt, Config

# Set up logging
logging.basicConfig(level=logging.INFO, handlers=[logging.FileHandler('bot.log'), logging.StreamHandler()])
logger = logging.getLogger(__name__)

async def get_metadata_text_and_buttons(user_id):
    try:
        current = await db.get_metadata(user_id)
        title = await db.get_title(user_id)
        author = await db.get_author(user_id)
        artist = await db.get_artist(user_id)
        video = await db.get_video(user_id)
        audio = await db.get_audio(user_id)
        subtitle = await db.get_subtitle(user_id)
        encoded_by = await db.get_encoded_by(user_id)
        custom_tag = await db.get_custom_tag(user_id)
    except Exception as e:
        logger.error(f"Error fetching metadata for user {user_id}: {e}")
        current = "Off"
        title = author = artist = video = audio = subtitle = encoded_by = custom_tag = None

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
    buttons = [
        [
            InlineKeyboardButton(f"On{' ✅' if current == 'On' else ''}", callback_data='on_metadata'),
            InlineKeyboardButton(f"Off{' ✅' if current == 'Off' else ''}", callback_data='off_metadata')
        ],
        [
            InlineKeyboardButton("How to Set Metadata", callback_data="metainfo")
        ]
    ]
    return text, InlineKeyboardMarkup(buttons)

@Client.on_message(filters.command("metadata"))
async def metadata(client, message):
    user_id = message.from_user.id
    try:
        text, keyboard = await get_metadata_text_and_buttons(user_id)
        await message.reply_text(text=text, reply_markup=keyboard, disable_web_page_preview=True)
    except Exception as e:
        logger.error(f"Error in metadata command for user {user_id}: {e}")
        await message.reply_text("An error occurred while retrieving metadata settings.")

@Client.on_callback_query(filters.regex(r"on_metadata|off_metadata|metainfo"))
async def metadata_callback(client, query: CallbackQuery):
    user_id = query.from_user.id
    data = query.data

    try:
        if data == "on_metadata":
            await db.set_metadata(user_id, "On")
        elif data == "off_metadata":
            await db.set_metadata(user_id, "Off")
        elif data == "metainfo":
            await query.message.edit_text(
                text=Txt.META_TXT,
                disable_web_page_preview=True,
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("Hᴏᴍᴇ", callback_data="home"),
                        InlineKeyboardButton("Bᴀᴄᴋ", callback_data="help")
                    ]
                ])
            )
            return

        text, keyboard = await get_metadata_text_and_buttons(user_id)
        await query.message.edit_text(text=text, reply_markup=keyboard, disable_web_page_preview=True)
    except Exception as e:
        logger.error(f"Error handling callback {data} for user {user_id}: {e}")
        await query.message.reply_text("An error occurred while updating metadata settings.")

@Client.on_message(filters.private & filters.command('settitle'))
async def title(client, message):
    if len(message.command) == 1:
        return await message.reply_text(
            "**Gɪᴠᴇ Tʜᴇ Tɪᴛʟᴇ\n\nExᴀᴍᴩʟᴇ:- /settitle Encoded By @Animeworld_zone**")
    title = message.text.split(" ", 1)[1]
    try:
        await db.set_title(message.from_user.id, title=title)
        await message.reply_text("**✅ Tɪᴛʟᴇ Sᴀᴠᴇᴅ**")
    except Exception as e:
        logger.error(f"Error setting title for user {message.from_user.id}: {e}")
        await message.reply_text("An error occurred while saving the title.")

@Client.on_message(filters.private & filters.command('setauthor'))
async def author(client, message):
    if len(message.command) == 1:
        return await message.reply_text(
            "**Gɪᴠᴇ Tʜᴇ Aᴜᴛʜᴏʀ\n\nExᴀᴍᴩʟᴇ:- /setauthor @Animeworld_zone**")
    author = message.text.split(" ", 1)[1]
    try:
        await db.set_author(message.from_user.id, author=author)
        await message.reply_text("**✅ Aᴜᴛʜᴏʀ Sᴀᴠᴇᴅ**")
    except Exception as e:
        logger.error(f"Error setting author for user {message.from_user.id}: {e}")
        await message.reply_text("An error occurred while saving the author.")

@Client.on_message(filters.private & filters.command('setartist'))
async def artist(client, message):
    if len(message.command) == 1:
        return await message.reply_text(
            "**Gɪᴠᴇ Tʜᴇ Aʀᴛɪꜱᴛ\n\nExᴀᴍᴩʟᴇ:- /setartist @Animeworld_zone**")
    artist = message.text.split(" ", 1)[1]
    try:
        await db.set_artist(message.from_user.id, artist=artist)
        await message.reply_text("**✅ Aʀᴛɪꜱᴛ Sᴀᴠᴇᴅ**")
    except Exception as e:
        logger.error(f"Error setting artist for user {message.from_user.id}: {e}")
        await message.reply_text("An error occurred while saving the artist.")

@Client.on_message(filters.private & filters.command('setaudio'))
async def audio(client, message):
    if len(message.command) == 1:
        return await message.reply_text(
            "**Gɪᴠᴇ Tʜᴇ Aᴜᴅɪᴏ Tɪᴛʟᴇ\n\nExᴀᴍᴩʟᴇ:- /setaudio @Animeworld_zone**")
    audio = message.text.split(" ", 1)[1]
    try:
        await db.set_audio(message.from_user.id, audio=audio)
        await message.reply_text("**✅ Aᴜᴅɪᴏ Sᴀᴠᴇᴅ**")
    except Exception as e:
        logger.error(f"Error setting audio for user {message.from_user.id}: {e}")
        await message.reply_text("An error occurred while saving the audio.")

@Client.on_message(filters.private & filters.command('setsubtitle'))
async def subtitle(client, message):
    if len(message.command) == 1:
        return await message.reply_text(
            "**Gɪᴠᴇ Tʜᴇ Sᴜʙᴛɪᴛʟᴇ Tɪᴛʟᴇ\n\nExᴀᴍᴩʟᴇ:- /setsubtitle @Animeworld_zone**")
    subtitle = message.text.split(" ", 1)[1]
    try:
        await db.set_subtitle(message.from_user.id, subtitle=subtitle)
        await message.reply_text("**✅ Sᴜʙᴛɪᴛʟᴇ Sᴀᴠᴇᴅ**")
    except Exception as e:
        logger.error(f"Error setting subtitle for user {message.from_user.id}: {e}")
        await message.reply_text("An error occurred while saving the subtitle.")

@Client.on_message(filters.private & filters.command('setvideo'))
async def video(client, message):
    if len(message.command) == 1:
        return await message.reply_text(
            "**Gɪᴠᴇ Tʜᴇ Vɪᴅᴇᴏ Tɪᴛʟᴇ\n\nExᴀᴍᴩʟᴇ:- /setvideo Encoded by @Animeworld_zone**")
    video = message.text.split(" ", 1)[1]
    try:
        await db.set_video(message.from_user.id, video=video)
        await message.reply_text("**✅ Vɪᴅᴇᴏ Sᴀᴠᴇᴅ**")
    except Exception as e:
        logger.error(f"Error setting video for user {message.from_user.id}: {e}")
        await message.reply_text("An error occurred while saving the video.")

@Client.on_message(filters.private & filters.command('setencoded_by'))
async def encoded_by(client, message):
    if len(message.command) == 1:
        return await message.reply_text(
            "**Gɪᴠᴇ Tʜᴇ Eɴᴄᴏᴅᴇᴅ Bʏ Tɪᴛʟᴇ\n\nExᴀᴍᴩʟᴇ:- /setencoded_by Animeworld_zone**")
    encoded_by = message.text.split(" ", 1)[1]
    try:
        await db.set_encoded_by(message.from_user.id, encoded_by=encoded_by)
        await message.reply_text("**✅ Eɴᴄᴏᴅᴇᴅ Bʏ Sᴀᴠᴇᴅ**")
    except Exception as e:
        logger.error(f"Error setting encoded_by for user {message.from_user.id}: {e}")
        await message.reply_text("An error occurred while saving the encoded_by.")

@Client.on_message(filters.private & filters.command('setcustom_tag'))
async def custom_tag(client, message):
    if len(message.command) == 1:
        return await message.reply_text(
            "**Gɪᴠᴇ Tʜᴇ Cᴜsᴛᴏᴍ Tᴀɢ Tɪᴛʟᴇ\n\nExᴀᴍᴩʟᴇ:- /setcustom_tag @Animeworld_zone**")
    custom_tag = message.text.split(" ", 1)[1]
    try:
        await db.set_custom_tag(message.from_user.id, custom_tag=custom_tag)
        await message.reply_text("**✅ Cᴜsᴛᴏᴍ Tᴀɢ Sᴀᴠᴇᴅ**")
    except Exception as e:
        logger.error(f"Error setting custom tag for user {message.from_user.id}: {e}")
        await message.reply_text("An error occurred while saving the custom tag.")
