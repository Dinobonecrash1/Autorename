import re, os, time

id_pattern = re.compile(r'^.\d+$')

class Config(object):
    # pyro client config
    API_ID = os.environ.get("API_ID", "21518327")
    API_HASH = os.environ.get("API_HASH", "e72f588b3e4763f01eecfc3c4aa7e8ac")
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "7012541014:AAFI2an6FRSqyZSYrXqyHuxYxSYeNNgNBiU")

    # Premium Configuration
    FREE_USER_DAILY_LIMIT = int(os.environ.get("FREE_USER_DAILY_LIMIT", "100"))
    PREMIUM_MONTHLY_PRICE = float(os.environ.get("PREMIUM_MONTHLY_PRICE", "9.99"))
    PREMIUM_YEARLY_PRICE = float(os.environ.get("PREMIUM_YEARLY_PRICE", "99.99"))
    
    # Payment Configuration - Update these with your actual details
    ADMIN_UPI_ID = os.environ.get("ADMIN_UPI_ID", "aryanchoudhary2ty@oksbi")  # Put your real UPI ID here
    ADMIN_PAYPAL = os.environ.get("ADMIN_PAYPAL", "Not Available")  # Since you don't have PayPal
    CRYPTO_WALLET = os.environ.get("CRYPTO_WALLET", "Not Available")  # Since you don't have crypto
    ADMIN_CONTACT = os.environ.get("ADMIN_CONTACT", "https://t.me/Zenitsu_AF")  # Your actual Telegram
    SUPPORT_CHANNEL = os.environ.get("SUPPORT_CHANNEL", "https://t.me/the_Reaperss")  # Your channel

    # database config
    DB_NAME = os.environ.get("DB_NAME","Autorename")
    DB_URL = os.environ.get("DB_URL","mongodb+srv://vinayjaat698:vinayjaat@autorename.6whzjfb.mongodb.net/?retryWrites=true&w=majority&appName=Autorename")

    # other configs
    BOT_UPTIME = time.time()
    START_PIC = os.environ.get("START_PIC", "https://envs.sh/2Gj.jpg")
    ADMIN = [int(admin) if id_pattern.search(admin) else admin for admin in os.environ.get('ADMIN', '5817124748').split()]
    FORCE_SUB = os.environ.get("FORCE_SUB", "0")
    LOG_CHANNEL = int(os.environ.get("LOG_CHANNEL", "-1003083608382"))
    FSUB_PIC = os.environ.get("FSUB_PIC", "https://envs.sh/2Gj.jpg")
    BOT_USERNAME = os.environ.get("BOT_USERNAME", "Raiden_Musicbot")
    # web response configuration
    WEBHOOK = bool(os.environ.get("WEBHOOK", "True"))


class Txt(object):
    # part of text configuration
    
    START_TXT = """ʜᴇʏ! {{}}

» ɪ ᴀᴍ ᴀᴅᴠᴀɴᴄᴇᴅ ʀᴇɴᴀᴍᴇ ʙᴏᴛ! ᴡʜɪᴄʜ ᴄᴀɴ ᴀᴜᴛᴏʀᴇɴᴀᴍᴇ ʏᴏᴜʀ ғɪʟᴇs ᴡɪᴛʜ ᴄᴜsᴛᴏᴍ ᴄᴀᴘᴛɪᴏɴ ᴀɴᴅ ᴛʜᴜᴍʙɴᴀɪʟ ᴀɴᴅ ᴀʟsᴏ sᴇǫᴜᴇɴᴄᴇ ᴛʜᴇᴍ ᴘᴇʀғᴇᴄᴛʟʏ

🆓 **Free Users:** 100 files per day
🌟 **Premium Users:** Unlimited files"""

    FILE_NAME_TXT = """» sᴇᴛᴜᴘ ᴀᴜᴛᴏ ʀᴇɴᴀᴍᴇ ғᴏʀᴍᴀᴛ

ᴠᴀʀɪᴀʙʟᴇꜱ :
➲ ᴇᴘɪꜱᴏᴅᴇ - ᴛᴏ ʀᴇᴘʟᴀᴄᴇ ᴇᴘɪꜱᴏᴅᴇ ɴᴜᴍʙᴇʀ
➲ ǫᴜᴀʟɪᴛʏ - ᴛᴏ ʀᴇᴘʟᴀᴄᴇ ǫᴜᴀʟɪᴛʏ

‣ ꜰᴏʀ ᴇx:- /autorename Your Anime Name Here [S01 - EPepisode - [Quality] [Dual] @Animeworld_zone

‣ /Autorename: ʀᴇɴᴀᴍᴇ ʏᴏᴜʀ ᴍᴇᴅɪᴀ ꜰɪʟᴇꜱ ʙʏ ɪɴᴄʟᴜᴅɪɴɢ 'ᴇᴘɪꜱᴏᴅᴇ' ᴀɴᴅ 'ǫᴜᴀʟɪᴛʏ' ᴠᴀʀɪᴀʙʟᴇꜱ ɪɴ ʏᴏᴜʀ ᴛᴇxᴛ, ᴛᴏ ᴇxᴛʀᴀᴄᴛ ᴇᴘɪꜱᴏᴅᴇ ᴀɴᴅ ǫᴜᴀʟɪᴛʏ ᴘʀᴇꜱᴇɴᴛ ɪɴ ᴛʜᴇ ᴏʀɪɢɪɴᴀʟ ꜰɪʟᴇɴᴀᴍᴇ."""

    ABOUT_TXT = f"""❍ ᴍʏ ɴᴀᴍᴇ : ᴀᴜᴛᴏ ʀᴇɴᴀᴍᴇ
❍ ᴅᴇᴠᴇʟᴏᴩᴇʀ : Bot
❍ ʟᴀɴɢᴜᴀɢᴇ : ᴘʏᴛʜᴏɴ
❍ ᴅᴀᴛᴀʙᴀꜱᴇ : ᴍᴏɴɢᴏ ᴅʙ
❍ ʜᴏꜱᴛᴇᴅ ᴏɴ : error...Not found...
❍ ᴍᴀɪɴ ᴄʜᴀɴɴᴇʟ : ANIME ZONE

🆓 **Free:** 100 files/day
🌟 **Premium:** Unlimited files

➻ ᴄʟɪᴄᴋ ᴏɴ ᴛʜᴇ ʙᴜᴛᴛᴏɴs ɢɪᴠᴇɴ ʙᴇʟᴏᴡ ғᴏʀ ɢᴇᴛᴛɪɴɢ ʙᴀsɪᴄ ʜᴇʟᴩ ᴀɴᴅ ɪɴғᴏ ᴀʙᴏᴜᴛ ᴍᴇ."""

    THUMBNAIL_TXT = """» ᴛᴏ ꜱᴇᴛ ᴄᴜꜱᴛᴏᴍ ᴛʜᴜᴍʙɴᴀɪʟ

➲ /start: ꜱᴇɴᴅ ᴀɴʏ ᴘʜᴏᴛᴏ ᴛᴏ ᴀᴜᴛᴏᴍᴀᴛɪᴄᴀʟʟʏ ꜱᴇᴛ ɪᴛ ᴀꜱ ᴀ ᴛʜᴜᴍʙɴᴀɪʟ..
➲ /del_thumb: ᴜꜱᴇ ᴛʜɪꜱ ᴄᴏᴍᴍᴀɴᴅ ᴛᴏ ᴅᴇʟᴇᴛᴇ ʏᴏᴜʀ ᴏʟᴅ ᴛʜᴜᴍʙɴᴀɪʟ.
➲ /view_thumb: ᴜꜱᴇ ᴛʜɪꜱ ᴄᴏᴍᴍᴀɴᴅ ᴛᴏ ᴠɪᴇᴡ ʏᴏᴜʀ ᴄᴜʀʀᴇɴᴛ ᴛʜᴜᴍʙɴᴀɪʟ.

ɴᴏᴛᴇ: ɪꜰ ɴᴏ ᴛʜᴜᴍʙɴᴀɪʟ ꜱᴀᴠᴇᴅ ɪɴ ʙᴏᴛ ᴛʜᴇɴ, ɪᴛ ᴡɪʟʟ ᴜꜱᴇ ᴛʜᴜᴍʙɴᴀɪʟ ᴏꜰ ᴛʜᴇ ᴏʀɪɢɪɴᴀʟ ꜰɪʟᴇ ᴛᴏ ꜱᴇᴛ ɪɴ ʀᴇɴᴀᴍᴇᴅ ꜰɪʟᴇ"""

    CAPTION_TXT = """» ᴛᴏ ꜱᴇᴛ ᴄᴜꜱᴛᴏᴍ ᴄᴀᴘᴛɪᴏɴ ᴀɴᴅ ᴍᴇᴅɪᴀ ᴛʏᴘᴇ

ᴠᴀʀɪᴀʙʟᴇꜱ :
ꜱɪᴢᴇ: {{ꜰɪʟᴇꜱɪᴢᴇ}}
ᴅᴜʀᴀᴛɪᴏɴ: {{duration}}
ꜰɪʟᴇɴᴀᴍᴇ: {{ꜰɪʟᴇɴᴀᴍᴇ}}

➲ /set_caption: ᴛᴏ ꜱᴇᴛ ᴀ ᴄᴜꜱᴛᴏᴍ ᴄᴀᴘᴛɪᴏɴ.
➲ /see_caption: ᴛᴏ ᴠɪᴇᴡ ʏᴏᴜʀ ᴄᴜꜱᴛᴏᴍ ᴄᴀᴘᴛɪᴏɴ.
➲ /del_caption: ᴛᴏ ᴅᴇʟᴇᴛᴇ ʏᴏᴜʀ ᴄᴜꜱᴛᴏᴍ ᴄᴀᴘᴛɪᴏɴ.

» ꜰᴏʀ ᴇx:- /set_caption ꜰɪʟᴇ ɴᴀᴍᴇ: {{ꜰɪʟᴇɴᴀᴍᴇ}}"""

    PROGRESS_BAR = """\\n
📁 Size : {{1}} | {{2}}
⏳️ Done : {{0}}%
🚀 Speed : {{3}}/s
⏰️ ETA : {{4}}"""

    DONATE_TXT = """
ᴛʜᴀɴᴋs ғᴏʀ sʜᴏᴡɪɴɢ ɪɴᴛᴇʀᴇsᴛ ɪɴ ᴅᴏɴᴀᴛɪᴏɴ

💞 ɪꜰ ʏᴏᴜ ʟɪᴋᴇ ᴏᴜʀ ʙᴏᴛ ꜰᴇᴇʟ ꜰʀᴇᴇ ᴛᴏ ᴅᴏɴᴀᴛᴇ ᴀɴʏ ᴀᴍᴏᴜɴᴛ ₹𝟷𝟶, ₹𝟸𝟶, ₹𝟻𝟶, ₹𝟷𝟶𝟶, ᴇᴛᴄ.

ᴅᴏɴᴀᴛɪᴏɴs ᴀʀᴇ ʀᴇᴀʟʟʏ ᴀᴘᴘʀᴇᴄɪᴀᴛᴇᴅ ɪᴛ ʜᴇʟᴘs ɪɴ ʙᴏᴛ ᴅᴇᴠᴇʟᴏᴘᴍᴇɴᴛ

ʏᴏᴜ ᴄᴀɴ ᴀʟsᴏ ᴅᴏɴᴀᴛᴇ ᴛʜʀᴏᴜɢʜ ᴜᴘɪ

ᴜᴘɪ ɪᴅ : {Config.ADMIN_UPI_ID}

ɪғ ʏᴏᴜ ᴡɪsʜ ʏᴏᴜ ᴄᴀɴ sᴇɴᴅ ᴜs ss
ᴏɴ - {Config.ADMIN_CONTACT}"""

    HELP_TXT = f"""ʜᴇʀᴇ ɪꜱ ʜᴇʟᴘ ᴍᴇɴᴜ ɪᴍᴘᴏʀᴛᴀɴᴛ ᴄᴏᴍᴍᴀɴᴅꜱ:

ᴀᴡᴇsᴏᴍᴇ ғᴇᴀᴛᴜʀᴇs🫧

ʀᴇɴᴀᴍᴇ ʙᴏᴛ ɪꜱ ᴀ ʜᴀɴᴅʏ ᴛᴏᴏʟ ᴛʜᴀᴛ ʜᴇʟᴘꜱ ʏᴏᴜ ʀᴇɴᴀᴍᴇ ᴀɴᴅ ᴍᴀɴᴀɢᴇ ʏᴏᴜʀ ꜰɪʟᴇꜱ ᴇꜰꜰᴏʀᴛʟᴇꜱꜱʟʏ.

➲ /autorename: ᴀᴜᴛᴏ ʀᴇɴᴀᴍᴇ ʏᴏᴜʀ ꜰɪʟᴇꜱ.
➲ /premium: ᴄʜᴇᴄᴋ ᴘʀᴇᴍɪᴜᴍ ꜱᴛᴀᴛᴜꜱ ᴀɴᴅ ᴜᴘɢʀᴀᴅᴇ.
➲ /usage: ᴄʜᴇᴄᴋ ʏᴏᴜʀ ᴅᴀɪʟʏ ᴜꜱᴀɢᴇ ꜱᴛᴀᴛɪꜱᴛɪᴄꜱ.
➲ /metadata: ᴄᴏᴍᴍᴀɴᴅꜱ ᴛᴏ ᴛᴜʀɴ ᴏɴ ᴏғғ ᴍᴇᴛᴀᴅᴀᴛᴀ.
➲ /help: ɢᴇᴛ ǫᴜɪᴄᴋ ᴀꜱꜱɪꜱᴛᴀɴᴄᴇ.

🆓 **Free Users:** 100 files per day
🌟 **Premium Users:** Unlimited files + Priority processing"""

    SEND_METADATA = """
--Metadata Settings:--

➜ /metadata: Turn on or off metadata.

Description : Metadata will change MKV video files including all audio, streams, and subtitle titles."""

    META_TXT = """
**ᴍᴀɴᴀɢɪɴɢ ᴍᴇᴛᴀᴅᴀᴛᴀ ғᴏʀ ʏᴏᴜʀ ᴠɪᴅᴇᴏs ᴀɴᴅ ғɪʟᴇs**

**ᴠᴀʀɪᴏᴜꜱ ᴍᴇᴛᴀᴅᴀᴛᴀ:**

- **ᴛɪᴛʟᴇ**: Descriptive title of the media.
- **ᴀᴜᴛʜᴏʀ**: The creator or owner of the media.
- **ᴀʀᴛɪsᴛ**: The artist associated with the media.
- **ᴀᴜᴅɪᴏ**: Title or description of audio content.
- **ꜱᴜʙᴛɪᴛʟᴇ**: Title of subtitle content.
- **ᴠɪᴅᴇᴏ**: Title or description of video content.

**ᴄᴏᴍᴍᴀɴᴅꜱ ᴛᴏ ᴛᴜʀɴ ᴏɴ ᴏғғ ᴍᴇᴛᴀᴅᴀᴛᴀ:**
➜ /metadata: Turn on or off metadata.

**ᴄᴏᴍᴍᴀɴᴅꜱ ᴛᴏ ꜱᴇᴛ ᴍᴇᴛᴀᴅᴀᴛᴀ:**

➜ /settitle: Set a custom title of media.
➜ /setauthor: Set the author.
➜ /setartist: Set the artist.
➜ /setaudio: Set audio title.
➜ /setsubtitle: Set subtitle title.
➜ /setvideo: Set video title.
➜ /setencoded_by: Set encoded by title.
➜ /setcustom_tag: Set custom tag title.

**ᴇxᴀᴍᴘʟᴇ:** /settitle Your Title Here

**ᴜꜱᴇ ᴛʜᴇꜱᴇ ᴄᴏᴍᴍᴀɴᴅꜱ ᴛᴏ ᴇɴʀɪᴄʜ ʏᴏᴜʀ ᴍᴇᴅɪᴀ ᴡɪᴛʜ ᴀᴅᴅɪᴛɪᴏɴᴀʟ ᴍᴇᴛᴀᴅᴀᴛᴀ ɪɴғᴏʀᴍᴀᴛɪᴏɴ!**
"""

    # Premium-specific texts - Only showing available payment method (UPI)
    PREMIUM_TXT = f"""
🌟 **Premium Subscription Plans**

**Monthly Plan:** ₹{Config.PREMIUM_MONTHLY_PRICE * 83}/month
• Unlimited file renames
• Priority processing
• Advanced features
• 24/7 support

**Yearly Plan:** ₹{Config.PREMIUM_YEARLY_PRICE * 83}/year (Save 17%!)
• All monthly benefits
• Best value for money
• Extended support

**Payment Method:**
💳 **UPI:** {Config.ADMIN_UPI_ID}

**How to Pay:**
1️⃣ Send money to the UPI ID above
2️⃣ Take screenshot of payment
3️⃣ Send screenshot to admin: {Config.ADMIN_CONTACT}
4️⃣ Get instant premium activation!

💬 **Need Help?** Contact: {Config.ADMIN_CONTACT}
📢 **Support:** {Config.SUPPORT_CHANNEL}
"""

    USAGE_TXT = f"""
📊 **Usage Statistics**

**Free Users:**
• Daily limit: 100 files
• Resets every day at 12:00 AM UTC
• Get upgrade prompts when approaching limit

**Premium Users:**
• Unlimited daily renames
• Priority processing
• No restrictions on sequences
• Advanced features

Use /premium to upgrade your account!
"""

    SEQUENCE_TXT = """
🔄 **File Sequence Feature**

**Commands:**
• /start_sequence - Start collecting files
• /end_sequence - Process files in episode order

**Requirements:**
🆓 **Free Users:** Need at least 5 remaining files
🌟 **Premium Users:** No restrictions

**Note:** Files will be automatically sorted by episode number and sent back in correct sequence order.
"""

    ADMIN_TXT = """
👑 **Admin Commands**

**Premium Management:**
• /addpremium <user_id> <plan> - Activate premium
• /removepremium <user_id> - Remove premium
• /premiumusers - List all premium users
• /premiumstats - View premium statistics

**Bot Management:**
• /restart - Restart the bot
• /broadcast - Send broadcast message
• /status - Check bot status

**Plans:** monthly, yearly
"""

# Jishu Developer 
# Don't Remove Credit 🥺
# Telegram Channel @Madflix_Bots
# Developer @JishuDeveloper
