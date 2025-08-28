import os
import re
import time
import shutil
import asyncio
import logging
import uuid
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from plugins.antinsfw import check_anti_nsfw
from helper.utils import progress_for_pyrogram, humanbytes, convert
from helper.database import Botskingdom
from config import Config
from functools import wraps

# ==== COMPLETELY REWRITTEN FOR TRUE MULTI-USER CONCURRENCY ====

# Track active auto-sequences per user (user-isolated)
active_sequences = {}

# Track temporary status/notification message IDs per user
message_ids = {}

# Track recent renaming operations by user_id + file_id to avoid double-processing
renaming_operations = {}

# MASSIVELY INCREASED thread pool for CPU-bound tasks
thread_pool = ThreadPoolExecutor(max_workers=(os.cpu_count() or 4) * 4)

# REMOVED user-specific semaphores - they were causing the bottleneck!
# Instead, we'll use global semaphores for different operations

# Global semaphores for different types of operations (much higher limits)
GLOBAL_DOWNLOAD_SEMAPHORE = asyncio.Semaphore(500000)  # Allow 50 concurrent downloads
GLOBAL_UPLOAD_SEMAPHORE = asyncio.Semaphore(500000)    # Allow 50 concurrent uploads
GLOBAL_FFMPEG_SEMAPHORE = asyncio.Semaphore(20000)    # Allow 20 concurrent FFmpeg operations

# Add premium check decorator (unchanged but optimized)
def premium_check():
    def decorator(func):
        @wraps(func)
        async def wrapper(client, message, *args, **kwargs):
            user_id = message.from_user.id
            can_rename, status_msg = await Botskingdom.can_rename_file(user_id)
            
            if not can_rename:
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🌟 Upgrade to Premium", callback_data="premium_info")],
                    [InlineKeyboardButton("📊 Check Usage", callback_data="usage_stats")]
                ])
                await message.reply_text(
                    f"❌ **{status_msg}**\n\n"
                    "🌟 **Premium Benefits:**\n"
                    "• Unlimited file renames\n"
                    "• Priority processing\n",
                    reply_markup=keyboard
                )
                return
                
            is_premium = await Botskingdom.is_premium_user(user_id)
            if not is_premium:
                await Botskingdom.increment_file_count(user_id)
                
            if not is_premium:
                remaining_files = Config.FREE_USER_DAILY_LIMIT - await Botskingdom.get_user_usage_today(user_id)
                if remaining_files <= 10:
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("🌟 Upgrade to Premium", callback_data="premium_info")]
                    ])
                    await message.reply_text(
                        f"⚠️ **Warning:** Only {remaining_files} renames left today!\n"
                        "Ohh Sweetie Upgrade to Premium for unlimited renames! 🚀",
                        reply_markup=keyboard
                    )
            
            return await func(client, message, *args, **kwargs)
        return wrapper
    return decorator

async def send_log(client, message, orig_name, new_name, path, media_type, ph_path):
    """Send the renamed file to the log channel with details - runs concurrently"""
    try:
        user = message.from_user
        caption = (
            f"🧾 **Rename Log**\n"
            f"👤 User: `{user.id}` ({user.first_name})\n"
            f"📄 Original: `{orig_name}`\n"
            f"🆕 New: `{new_name}`"
        )
        
        log_chat = getattr(Config, "LOG_CHANNEL", None)
        if not log_chat:
            return
            
        # Send log concurrently without blocking main process
        if media_type == "document":
            await client.send_document(
                log_chat, document=path, thumb=ph_path, caption=caption
            )
        elif media_type == "video":
            await client.send_video(
                log_chat, video=path, thumb=ph_path, caption=caption, duration=0
            )
        elif media_type == "audio":
            await client.send_audio(
                log_chat, audio=path, thumb=ph_path, caption=caption, duration=0
            )
        else:
            await client.send_document(
                log_chat, document=path, thumb=ph_path, caption=caption
            )
            
    except Exception as e:
        print(f"Logging failed: {e}")

def detect_quality(file_name):
    """Detects quality for sorting, not for direct filename replacement."""
    quality_order = {"360p": 0, "480p": 1, "720p": 2, "1080p": 3, "1440p": 4, "2160p": 5, "4k": 6}
    match = re.search(r"(360p|480p|720p|1080p|1440p|2160p|4k)\b", file_name, re.IGNORECASE)
    return quality_order.get(match.group(1).lower(), 7) if match else 7

def extract_episode_number(filename):
    """Enhanced episode extraction with better pattern matching and validation."""
    if not filename:
        return None
        
    print(f"DEBUG: Extracting episode from: '{filename}')")
    
    quality_and_year_indicators = [
        r'\d{2,4}[pP]', r'\dK', r'HD(?:RIP)?', r'WEB(?:-)?DL',
        r'BLURAY', r'X264', r'X265', r'HEVC', r'FHD', r'UHD',
        r'HDR', r'H\.264', r'H\.265', r'(?:19|20)\d{2}',
        r'Multi(?:audio)?', r'Dual(?:audio)?'
    ]
    
    quality_pattern_for_exclusion = r'(?:' + '|'.join([f'(?:[\s._-]*{ind})' for ind in quality_and_year_indicators]) + r')'
    
    patterns = [
        re.compile(r'S\d+[.-_]?E(\d+)', re.IGNORECASE),
        re.compile(r'(?:Episode|EP)[\s._-]*(\d+)', re.IGNORECASE),
        re.compile(r'\bE(\d+)\b', re.IGNORECASE),
        re.compile(r'[\[\(]E(\d+)[\]\)]', re.IGNORECASE),
        re.compile(r'\b(\d+)\s*of\s*\d+\b', re.IGNORECASE),
        re.compile(
            r'(?:^|[^0-9A-Z])'
            r'(\d{1,4})'
            r'(?:[^0-9A-Z]|$)'
            r'(?!' + quality_pattern_for_exclusion + r')',
            re.IGNORECASE
        ),
    ]
    
    for i, pattern in enumerate(patterns):
        matches = pattern.findall(filename)
        if matches:
            for match in matches:
                try:
                    if isinstance(match, tuple):
                        episode_str = match[0]
                    else:
                        episode_str = match
                    episode_num = int(episode_str)
                    
                    if 1 <= episode_num <= 9999:
                        if episode_num in [360, 480, 720, 1080, 1440, 2160, 2020, 2021, 2022, 2023, 2024, 2025]:
                            if re.search(r'\b' + str(episode_num) + r'(?:p|K|HD|WEB|BLURAY|X264|X265|HEVC|Multi|Dual)\b', filename, re.IGNORECASE) or \
                               re.search(r'\b(?:19|20)\d{2}\b', filename, re.IGNORECASE) and len(str(episode_num)) == 4:
                                print(f"DEBUG: Skipping {episode_num} as it is a common quality/year number.")
                                continue
                        
                        print(f"DEBUG: Episode Pattern {i+1} found episode: {episode_num}")
                        return episode_num
                except ValueError:
                    continue
                    
    print(f"DEBUG: No episode number found in: '{filename}'")
    return None

def extract_season_number(filename):
    """Enhanced season extraction with better pattern matching and validation."""
    if not filename:
        return None
        
    print(f"DEBUG: Extracting season from: '{filename}')")
    
    quality_and_year_indicators = [
        r'\d{2,4}[pP]', r'\dK', r'HD(?:RIP)?', r'WEB(?:-)?DL',
        r'BLURAY', r'X264', r'X265', r'HEVC', r'FHD', r'UHD',
        r'HDR', r'H\.264', r'H\.265', r'(?:19|20)\d{2}',
        r'Multi(?:audio)?', r'Dual(?:audio)?'
    ]
    
    quality_pattern_for_exclusion = r'(?:' + '|'.join([f'(?:[\s._-]*{ind})' for ind in quality_and_year_indicators]) + r')'
    
    patterns = [
        re.compile(r'S(\d+)[._-]?E\d+', re.IGNORECASE),
        re.compile(r'(?:Season|SEASON|season)[\s._-]*(\d+)', re.IGNORECASE),
        re.compile(r'\bS(\d+)\b(?!E\d|' + quality_pattern_for_exclusion + r')', re.IGNORECASE),
        re.compile(r'[\[\(]S(\d+)[\]\)]', re.IGNORECASE),
        re.compile(r'[._-]S(\d+)(?:[._-]|$)', re.IGNORECASE),
        re.compile(r'(?:season|SEASON|Season)[\s._-]*(\d+)', re.IGNORECASE),
        re.compile(r'(?:^|[\s._-])(?:season|SEASON|Season)[\s._-]*(\d+)(?:[\s._-]|$)', re.IGNORECASE),
        re.compile(r'[\[\(](?:season|SEASON|Season)[\s._-]*(\d+)[\]\)]', re.IGNORECASE),
        re.compile(r'(?:season|SEASON|Season)[._\s-]+(\d+)', re.IGNORECASE),
        re.compile(r'(?:^season|season$)[\s._-]*(\d+)', re.IGNORECASE),
    ]
    
    for i, pattern in enumerate(patterns):
        match = pattern.search(filename)
        if match:
            try:
                season_num = int(match.group(1))
                if 1 <= season_num <= 99:
                    print(f"DEBUG: Season Pattern {i+1} found season: {season_num}")
                    return season_num
            except ValueError:
                continue
                
    print(f"DEBUG: No season number found in: '{filename}'")
    return None

def extract_audio_info(filename):
    """Extract audio information from filename, including languages and 'dual'/'multi'."""
    audio_keywords = {
        'Hindi': re.compile(r'Hindi', re.IGNORECASE),
        'English': re.compile(r'English', re.IGNORECASE),
        'Multi': re.compile(r'Multi(?:audio)?', re.IGNORECASE),
        'Telugu': re.compile(r'Telugu', re.IGNORECASE),
        'Tamil': re.compile(r'Tamil', re.IGNORECASE),
        'Dual': re.compile(r'Dual(?:audio)?', re.IGNORECASE),
        'Dual_Enhanced': re.compile(r'(?:DUAL(?:[\s._-]?AUDIO)?|\[DUAL\])', re.IGNORECASE),
        'AAC': re.compile(r'AAC', re.IGNORECASE),
        'AC3': re.compile(r'AC3', re.IGNORECASE),
        'DTS': re.compile(r'DTS', re.IGNORECASE),
        'MP3': re.compile(r'MP3', re.IGNORECASE),
        '5.1': re.compile(r'5\.1', re.IGNORECASE),
        '2.0': re.compile(r'2\.0', re.IGNORECASE),
    }
    
    detected_audio = []
    
    if re.search(r'\bMulti(?:audio)?\b', filename, re.IGNORECASE):
        detected_audio.append("Multi")
    if re.search(r'\bDual(?:audio)?\b', filename, re.IGNORECASE):
        detected_audio.append("Dual")
        
    priority_keywords = ['Hindi', 'English', 'Telugu', 'Tamil']
    for keyword in priority_keywords:
        if audio_keywords[keyword].search(filename):
            if keyword not in detected_audio:
                detected_audio.append(keyword)
                
    for keyword in ['AAC', 'AC3', 'DTS', 'MP3', '5.1', '2.0']:
        if audio_keywords[keyword].search(filename):
            if keyword not in detected_audio:
                detected_audio.append(keyword)
                
    detected_audio = list(dict.fromkeys(detected_audio))
    
    if detected_audio:
        return ' '.join(detected_audio)
    return None

def extract_quality(filename):
    """Extract video quality from filename."""
    patterns = [
        re.compile(r'\b(4K|2K|2160p|1440p|1080p|720p|480p|360p)\b', re.IGNORECASE),
        re.compile(r'\b(HD(?:RIP)?|WEB(?:-)?DL|BLURAY)\b', re.IGNORECASE),
        re.compile(r'\b(X264|X265|HEVC)\b', re.IGNORECASE),
    ]
    
    for pattern in patterns:
        match = re.search(pattern, filename)
        if match:
            found_quality = match.group(1)
            if found_quality.lower() in ["4k", "2k", "hdrip", "web-dl", "bluray"]:
                return found_quality.upper() if found_quality.upper() in ["4K", "2K"] else found_quality.capitalize()
            return found_quality
    return None

def generate_unique_paths(renamed_file_name, user_id):
    """Generate file paths with user isolation for better concurrency"""
    base_name, ext = os.path.splitext(renamed_file_name)
    if not ext.startswith('.'):
        ext = '.' + ext if ext else ''
    
    # Add timestamp and user_id for better uniqueness in concurrent operations
    timestamp = int(time.time() * 1000)  # milliseconds
    unique_id = f"{user_id}_{timestamp}_{uuid.uuid4().hex[:8]}"
    unique_file_name_for_storage = f"{base_name}_{unique_id}{ext}"
    
    # Create user-specific directories for better organization
    user_download_dir = os.path.join("downloads", str(user_id))
    user_metadata_dir = os.path.join("Metadata", str(user_id))
    
    renamed_file_path = os.path.join(user_download_dir, unique_file_name_for_storage)
    metadata_file_path = os.path.join(user_metadata_dir, unique_file_name_for_storage)
    
    os.makedirs(os.path.dirname(renamed_file_path), exist_ok=True)
    os.makedirs(os.path.dirname(metadata_file_path), exist_ok=True)
    
    return renamed_file_path, metadata_file_path, renamed_file_name  # Return original name for final upload

@Client.on_message(filters.command("start_sequence") & filters.private)
async def start_sequence(client, message: Message):
    user_id = message.from_user.id
    
    is_premium = await Botskingdom.is_premium_user(user_id)
    if not is_premium:
        files_today = await Botskingdom.get_user_usage_today(user_id)
        remaining = Config.FREE_USER_DAILY_LIMIT - files_today
        if remaining < 5:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🌟 Upgrade to Premium", callback_data="premium_info")]
            ])
            await message.reply_text(
                f"⚠️ **Sequence requires at least 5 remaining files!**\n\n"
                f"You have only {remaining} files left today.\n"
                "Upgrade to Premium for unlimited sequences! 🚀",
                reply_markup=keyboard
            )
            return
    
    if user_id in active_sequences:
        await message.reply_text("Hᴇʏ Cutie pie A sᴇǫᴜᴇɴᴄᴇ ɪs ᴀʟʀᴇᴀᴅʏ ᴀᴄᴛɪᴠᴇ! Usᴇ /end_sequence ᴛᴏ ᴇɴᴅ ɪᴛ.")
    else:
        active_sequences[user_id] = []
        message_ids[user_id] = []
        
        status = "🌟 Premium" if is_premium else f"👤 Free ({remaining} left)"
        msg = await message.reply_text(f"Sᴇǫᴜᴇɴᴄᴇ sᴛᴀʀᴛᴇᴅ! ({status})\nSᴇɴᴅ ʏᴏᴜʀ ғɪʟᴇs ɴᴏᴡ ʙʀᴏ....Fᴀsᴛ")
        message_ids[user_id].append(msg.id)

async def delete_message_after_delay(message, delay):
    """Helper function to delete message after delay"""
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except:
        pass

@Client.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def auto_rename_files(client, message):
    """COMPLETELY REDESIGNED for true multi-user concurrent processing"""
    user_id = message.from_user.id
    
    # Check premium status and usage limits before processing
    can_rename, status_msg = await Botskingdom.can_rename_file(user_id)
    if not can_rename:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🌟 Upgrade to Premium", callback_data="premium_info")],
            [InlineKeyboardButton("📊 Check Usage", callback_data="usage_stats")]
        ])
        await message.reply_text(
            f"❌ **{status_msg}**\n\n"
            "🌟 **Premium Benefits:**\n"
            "• Unlimited file renames\n"
            "• Priority processing\n"
            "• Advanced features\n\n"
            "💳 Upgrade now to continue renaming!",
            reply_markup=keyboard
        )
        return
    
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
    
    # Create unique operation key for this user+file combination
    operation_key = f"{user_id}_{file_id}"
    
    # Check for duplicate processing
    if operation_key in renaming_operations:
        elapsed_time = (datetime.now() - renaming_operations[operation_key]).seconds
        if elapsed_time < 3:  # Further reduced to 3 seconds
            return
    
    renaming_operations[operation_key] = datetime.now()
    
    file_info = {
        "file_id": file_id,
        "file_name": file_name if file_name else "Unknown",
        "message": message,
        "episode_num": extract_episode_number(file_name if file_name else "Unknown"),
        "operation_key": operation_key
    }
    
    # Show user status
    is_premium = await Botskingdom.is_premium_user(user_id)
    if not is_premium:
        await Botskingdom.increment_file_count(user_id)
        files_today = await Botskingdom.get_user_usage_today(user_id)
        remaining = Config.FREE_USER_DAILY_LIMIT - files_today
        
        status_msg = await message.reply_text(
            f"🔄 **Processing file...** ({remaining} renames left today)"
        )
        asyncio.create_task(delete_message_after_delay(status_msg, 2))  # Faster deletion
    
    # Handle sequence mode
    if user_id in active_sequences:
        active_sequences[user_id].append(file_info)
        reply_msg = await message.reply_text("Wait cutie ғɪʟᴇs ʀᴇᴄᴇɪᴠᴇᴅ ɴᴏᴡ ᴜsᴇ /end_sequence ᴛᴏ ɢᴇᴛ ʏᴏᴜʀ ғɪʟᴇs...!!")
        message_ids[user_id].append(reply_msg.id)
        return
    
    # Process file immediately - NO SEMAPHORE BLOCKING HERE!
    asyncio.create_task(auto_rename_file_concurrent(client, message, file_info))

@Client.on_message(filters.command("end_sequence") & filters.private)
async def end_sequence(client, message: Message):
    """Enhanced sequence ending with massive concurrency"""
    user_id = message.from_user.id
    
    if user_id not in active_sequences:
        await message.reply_text("Wʜᴀᴛ ᴀʀᴇ ʏᴏᴜ ᴅᴏɪɴɢ ɴᴏ ᴀᴄᴛɪᴠᴇ sᴇǫᴜᴇɴᴄᴇ ғᴏᴜɴᴅ...!!")
        return
    
    file_list = active_sequences.pop(user_id, [])
    delete_messages = message_ids.pop(user_id, [])
    count = len(file_list)
    
    is_premium = await Botskingdom.is_premium_user(user_id)
    if not is_premium:
        files_today = await Botskingdom.get_user_usage_today(user_id)
        remaining = Config.FREE_USER_DAILY_LIMIT - files_today
        if count > remaining:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🌟 Upgrade to Premium", callback_data="premium_info")]
            ])
            await message.reply_text(
                f"❌ **Not enough renames left!**\n\n"
                f"Files in sequence: {count}\n"
                f"Remaining today: {remaining}\n\n"
                "Upgrade to Premium for unlimited renames! 🚀",
                reply_markup=keyboard
            )
            return
    
    if not file_list:
        await message.reply_text("Nᴏ ғɪʟᴇs ᴡᴇʀᴇ sᴇɴᴛ ɪɴ ᴛʜɪs sᴇǫᴜᴇɴᴄᴇ....ʙʀᴏ...!!")
        return
    
    # Sort files by episode number
    file_list.sort(key=lambda x: x["episode_num"] if x["episode_num"] is not None else float('inf'))
    
    status = "🌟 Premium" if is_premium else f"👤 Free"
    await message.reply_text(f"Sᴇǫᴜᴇɴᴄᴇ ᴇɴᴅᴇᴅ. ({status})\nNᴏᴡ ᴘʀᴏᴄᴇssɪɴɢ ᴀʟʟ {count} ғɪʟᴇ(s) sɪᴍᴜʟᴛᴀɴᴇᴏᴜsʟʏ...!!")
    
    # Increment file count for non-premium users
    if not is_premium:
        await Botskingdom.col.update_one(
            {"_id": user_id},
            {"$inc": {"usage_stats.files_renamed_today": count}}
        )
    
    # Process ALL files concurrently with NO LIMITS!
    tasks = []
    for file_info in file_list:
        task = asyncio.create_task(auto_rename_file_concurrent(client, file_info["message"], file_info))
        tasks.append(task)
    
    # Wait for all files to be processed
    try:
        await asyncio.gather(*tasks, return_exceptions=True)
    except Exception as e:
        print(f"Error in concurrent sequence processing: {e}")
    
    # Show final status
    if not is_premium:
        new_remaining = Config.FREE_USER_DAILY_LIMIT - await Botskingdom.get_user_usage_today(user_id)
        await message.reply_text(
            f"✅ Aʟʟ {count} ғɪʟᴇs ᴘʀᴏᴄᴇssᴇᴅ sɪᴍᴜʟᴛᴀɴᴇᴏᴜsʟʏ!\n"
            f"📊 Remaining today: {new_remaining}"
        )
    else:
        await message.reply_text(f"✅ Aʟʟ {count} ғɪʟᴇs ᴘʀᴏᴄᴇssᴇᴅ sɪᴍᴜʟᴛᴀɴᴇᴏᴜsʟʏ!")
    
    # Clean up messages
    try:
        await client.delete_messages(chat_id=message.chat.id, message_ids=delete_messages)
    except Exception as e:
        print(f"Error deleting messages: {e}")

async def process_thumb_async(ph_path):
    """Process thumbnail in thread pool to avoid blocking"""
    def _resize_thumb(path):
        try:
            img = Image.open(path).convert("RGB")
            img = img.resize((320, 320))
            img.save(path, "JPEG")
        except Exception as e:
            print(f"Thumbnail processing error: {e}")
    
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(thread_pool, _resize_thumb, ph_path)

async def run_ffmpeg_async(metadata_command):
    """Run FFmpeg in thread pool with global semaphore."""
    async with GLOBAL_FFMPEG_SEMAPHORE:  # Global limit for FFmpeg operations
        def _run_ffmpeg():
            import subprocess
            try:
                result = subprocess.run(
                    metadata_command,
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minute timeout
                )
                return result.returncode, result.stdout, result.stderr
            except subprocess.TimeoutExpired:
                return -1, "", "FFmpeg timeout"
            except Exception as e:
                return -1, "", str(e)
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(thread_pool, _run_ffmpeg)

async def concurrent_download(client, message, renamed_file_path, progress_msg):
    """COMPLETELY REDESIGNED concurrent download with global semaphore"""
    async with GLOBAL_DOWNLOAD_SEMAPHORE:  # Global download limit
        try:
            path = await client.download_media(
                message,
                file_name=renamed_file_path,
                progress=progress_for_pyrogram,
                progress_args=("Dᴏᴡɴʟᴏᴀᴅ sᴛᴀʀᴛᴇᴅ ᴅᴜᴅᴇ....!!", progress_msg, time.time()),
            )
            return path
        except Exception as e:
            raise Exception(f"Download Error: {e}")

async def concurrent_upload(client, message, path, media_type, caption, ph_path, progress_msg):
    """COMPLETELY REDESIGNED concurrent upload with global semaphore"""
    async with GLOBAL_UPLOAD_SEMAPHORE:  # Global upload limit
        try:
            if media_type == "document":
                await client.send_document(
                    message.chat.id,
                    document=path,
                    thumb=ph_path,
                    caption=caption,
                    progress=progress_for_pyrogram,
                    progress_args=("Uᴘʟᴏᴀᴅ sᴛᴀʀᴛᴇᴅ ᴅᴜᴅᴇ...!!", progress_msg, time.time()),
                )
            elif media_type == "video":
                await client.send_video(
                    message.chat.id,
                    video=path,
                    caption=caption,
                    thumb=ph_path,
                    duration=0,
                    progress=progress_for_pyrogram,
                    progress_args=("Uᴘʟᴏᴀᴅ sᴛᴀʀᴛᴇᴅ ᴅᴜᴅᴇ...!!", progress_msg, time.time()),
                )
            elif media_type == "audio":
                await client.send_audio(
                    message.chat.id,
                    audio=path,
                    caption=caption,
                    thumb=ph_path,
                    duration=0,
                    progress=progress_for_pyrogram,
                    progress_args=("Uᴘʟᴏᴀᴅ sᴛᴀʀᴛᴇᴅ ᴅᴜᴅᴇ...!!", progress_msg, time.time()),
                )
        except Exception as e:
            raise Exception(f"Upload Error: {e}")

async def auto_rename_file_concurrent(client, message, file_info):
    """COMPLETELY REWRITTEN for maximum multi-user concurrency"""
    path = None
    ph_path = None
    
    try:
        user_id = message.from_user.id
        file_id = file_info["file_id"]
        file_name = file_info["file_name"]
        operation_key = file_info.get("operation_key", f"{user_id}_{file_id}")
        
        # Check premium status
        is_premium = await Botskingdom.is_premium_user(user_id)
        
        # Get user settings concurrently
        settings_tasks = [
            Botskingdom.get_format_template(user_id),
            Botskingdom.get_media_preference(user_id)
        ]
        format_template, media_preference = await asyncio.gather(*settings_tasks)
        
        if not format_template:
            await message.reply_text("Cutie Pʟᴇᴀsᴇ Sᴇᴛ Aɴ Aᴜᴛᴏ Rᴇɴᴀᴍᴇ Fᴏʀᴍᴀᴛ Fɪʀsᴛ Usɪɴɢ /autorename")
            return
        
        # Determine media type
        media_type = media_preference
        if not media_type:
            if file_name and file_name.lower().endswith((".mp4", ".mkv", ".avi", ".webm")):
                media_type = "video"
            elif file_name and file_name.lower().endswith((".mp3", ".flac", ".wav", ".ogg")):
                media_type = "audio"
            else:
                media_type = "document"
        
        # NSFW check (run in background)
        nsfw_task = asyncio.create_task(check_anti_nsfw(file_name, message))
        
        # Extract metadata from filename (run concurrently)
        metadata_tasks = [
            asyncio.create_task(asyncio.to_thread(extract_episode_number, file_name or "Unknown")),
            asyncio.create_task(asyncio.to_thread(extract_season_number, file_name or "Unknown")),
            asyncio.create_task(asyncio.to_thread(extract_audio_info, file_name or "Unknown")),
            asyncio.create_task(asyncio.to_thread(extract_quality, file_name or "Unknown"))
        ]
        
        # Wait for NSFW check
        if await nsfw_task:
            await message.reply_text("NSFW ᴄᴏɴᴛᴇɴᴛ ᴅᴇᴛᴇᴄᴛᴇᴅ. Fɪʟᴇ ᴜᴘʟᴏᴀᴅ ʀᴇᴊᴇᴄᴛᴇᴅ.")
            return
        
        # Get metadata extraction results
        episode_number, season_number, audio_info_extracted, quality_extracted = await asyncio.gather(*metadata_tasks)
        
        # Process template
        template = format_template
        season_value_formatted = str(season_number).zfill(2) if season_number is not None else "01"
        episode_value_formatted = str(episode_number).zfill(2) if episode_number is not None else "01"
        
        # Replace placeholders with enhanced regex patterns
        template = re.sub(r'S(?:Season|season|SEASON)(\d+)', f'S{season_value_formatted}', template, flags=re.IGNORECASE)
        
        for pattern in [
            re.compile(r'\{season\}', re.IGNORECASE),
            re.compile(r'\{Season\}', re.IGNORECASE),
            re.compile(r'\{SEASON\}', re.IGNORECASE),
            re.compile(r'\bseason\b', re.IGNORECASE),
            re.compile(r'\bSeason\b', re.IGNORECASE),
            re.compile(r'\bSEASON\b', re.IGNORECASE),
            re.compile(r'Season[\s._-]*\d*', re.IGNORECASE),
            re.compile(r'season[\s._-]*\d*', re.IGNORECASE),
            re.compile(r'SEASON[\s._-]*\d*', re.IGNORECASE),
        ]:
            template = pattern.sub(season_value_formatted, template)
        
        template = re.sub(r'EP(?:Episode|episode|EPISODE)', f'EP{episode_value_formatted}', template, flags=re.IGNORECASE)
        
        for pattern in [
            re.compile(r'\{episode\}', re.IGNORECASE),
            re.compile(r'\bEpisode\b', re.IGNORECASE),
            re.compile(r'\bEP\b', re.IGNORECASE),
        ]:
            template = pattern.sub(episode_value_formatted, template)
        
        # Audio and quality replacements
        audio_replacement = audio_info_extracted or ""
        for pattern in [
            re.compile(r'\{audio\}', re.IGNORECASE),
            re.compile(r'\bAudio\b', re.IGNORECASE),
        ]:
            template = pattern.sub(audio_replacement, template)
        
        quality_replacement = quality_extracted or ""
        for pattern in [
            re.compile(r'\{quality\}', re.IGNORECASE),
            re.compile(r'\bQuality\b', re.IGNORECASE),
        ]:
            template = pattern.sub(quality_replacement, template)
        
        # Clean up template
        template = re.sub(r'\s{2,}', ' ', template)
        template = re.sub(r'\[\s*\]', '', template)
        template = re.sub(r'\(\s*\)', '', template)
        template = re.sub(r'\{\s*\}', '', template)
        template = re.sub(r'\.{2,}', '.', template)
        template = re.sub(r'-{2,}', '-', template)
        template = re.sub(r'\s*\.\s*', '.', template)
        template = re.sub(r'\s*-\s*', '-', template)
        template = template.strip()
        template = re.sub(r'^[._\s]+', '', template)
        template = re.sub(r'[._\s]+$', '', template)
        
        # Get file extension
        _, file_extension = os.path.splitext(file_name or "")
        if file_extension and not file_extension.startswith('.'):
            file_extension = '.' + file_extension
        
        renamed_file_name = f"{template}{file_extension}"
        
        # Generate unique paths with user isolation
        renamed_file_path, metadata_file_path, final_name = generate_unique_paths(renamed_file_name, user_id)
        
        premium_indicator = "🌟" if is_premium else "👤"
        download_msg = await message.reply_text(f"{premium_indicator} Wait cutie Iᴀᴍ ᴅᴏᴡɴʟᴏᴀᴅɪɴɢ ʏᴏᴜʀ ғɪʟᴇ...!!")
        
        try:
            # Download with global concurrency control
            path = await concurrent_download(client, message, renamed_file_path, download_msg)
            
            await download_msg.edit("Nᴏᴡ ᴀᴅᴅɪɴɢ ᴍᴇᴛᴀᴅᴀᴛᴀ babe...!!")
            
            # Check for FFmpeg
            ffmpeg_cmd = shutil.which('ffmpeg')
            if not ffmpeg_cmd:
                raise Exception("FFmpeg not found")
            
            # Get metadata settings concurrently
            metadata_tasks = [
                Botskingdom.get_title(user_id),
                Botskingdom.get_artist(user_id),
                Botskingdom.get_author(user_id),
                Botskingdom.get_video(user_id),
                Botskingdom.get_audio(user_id),
                Botskingdom.get_subtitle(user_id),
                Botskingdom.get_encoded_by(user_id),
                Botskingdom.get_custom_tag(user_id)
            ]
            
            metadata_values = await asyncio.gather(*metadata_tasks)
            title, artist, author, video_title, audio_title, subtitle_title, encoded_by, custom_tag = metadata_values
            
            # Prepare FFmpeg command
            metadata_command = [
                ffmpeg_cmd,
                '-i', path,
                '-metadata', f'title={title}',
                '-metadata', f'artist={artist}',
                '-metadata', f'author={author}',
                '-metadata:s:v', f'title={video_title}',
                '-metadata:s:a', f'title={audio_title}',
                '-metadata:s:s', f'title={subtitle_title}',
                '-metadata', f'encoded_by={encoded_by}',
                '-metadata', f'custom_tag={custom_tag}',
                '-map', '0',
                '-c', 'copy',
                '-loglevel', 'error',
                metadata_file_path
            ]
            
            # Run FFmpeg concurrently
            returncode, stdout, stderr = await run_ffmpeg_async(metadata_command)
            
            if returncode != 0:
                error_message = stderr
                await download_msg.edit(f"Mᴇᴛᴀᴅᴀᴛᴀ Eʀʀᴏʀ:\n{error_message}")
                return
            
            path = metadata_file_path
            
            await download_msg.edit("Wait cutie Iᴀm Uᴘʟᴏᴀᴅɪɴɢ ʏᴏᴜʀ ғɪʟᴇ...!!")
            
            # Get caption and thumbnail settings concurrently
            caption_task = Botskingdom.get_caption(message.chat.id)
            thumb_task = Botskingdom.get_thumbnail(message.chat.id)
            
            c_caption, c_thumb = await asyncio.gather(caption_task, thumb_task)
            
            # Prepare caption
            caption = (
                c_caption.format(
                    filename=final_name,
                    filesize=humanbytes(getattr(message.document, "file_size", 0)) if message.document else "Unknown",
                    duration=convert(0),
                ) if c_caption else f"{final_name}"
            )
            
            # Handle thumbnail
            if c_thumb:
                ph_path = await client.download_media(c_thumb)
            elif media_type == "video" and getattr(message.video, "thumbs", None):
                ph_path = await client.download_media(message.video.thumbs[0].file_id)
            
            if ph_path:
                await process_thumb_async(ph_path)
            
            # Upload with global concurrency control
            await concurrent_upload(client, message, path, media_type, caption, ph_path, download_msg)
            
            await download_msg.delete()
            
            # Send status message
            if is_premium:
                await message.reply_text("✅ **File renamed successfully!** 🌟 Premium User")
            else:
                remaining = Config.FREE_USER_DAILY_LIMIT - await Botskingdom.get_user_usage_today(user_id)
                await message.reply_text(f"✅ **File renamed successfully!**\n📊 Remaining today: {remaining}")
            
            # Send log concurrently (non-blocking)
            asyncio.create_task(send_log(client, message, file_name, final_name, path, media_type, ph_path))
            
        except Exception as e:
            try:
                await download_msg.edit(f"❌ Eʀʀᴏʀ: {str(e)}")
            except Exception:
                pass
            raise
        
    except Exception as e:
        print(f"An error occurred during renaming for operation {operation_key}: {e}")
        
    finally:
        # Clean up files
        for p in [path, renamed_file_path, metadata_file_path, ph_path]:
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except Exception as cleanup_e:
                    print(f"Error during file cleanup for {p}: {cleanup_e}")
        
        # Clean up operation tracking
        if 'operation_key' in locals():
            renaming_operations.pop(operation_key, None)

# Callback handlers (unchanged but included for completeness)
@Client.on_callback_query(filters.regex("^premium_info$"))
async def premium_info_callback(client, callback_query):
    """Handle premium info callback"""
    user_id = callback_query.from_user.id
    is_premium = await Botskingdom.is_premium_user(user_id)
    
    if is_premium:
        text = "🌟 **You are already a Premium user!**\n\nEnjoy unlimited file renames! 🚀"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 View Usage", callback_data="usage_stats")]
        ])
    else:
        files_today = await Botskingdom.get_user_usage_today(user_id)
        remaining = Config.FREE_USER_DAILY_LIMIT - files_today
        text = f'''💰 **Premium Subscription**\n\n**Current Status:** Free User\n**Files renamed today:** {files_today}/{Config.FREE_USER_DAILY_LIMIT}\n**Remaining today:** {remaining}\n\n🌟 **Premium Benefits:**\n• Unlimited file renames\n• Priority processing\n• Advanced features\n• 24/7 support\n\n💳 **Available Plans:**\n• Monthly: $9.99/month\n• Yearly: $99.99/year (Save 17%)'''
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 Contact Admin", url="https://t.me/Zenitsu_AF")],
            [InlineKeyboardButton("📊 View Usage", callback_data="usage_stats")]
        ])
    
    await callback_query.message.edit_text(text, reply_markup=keyboard)

@Client.on_callback_query(filters.regex("^usage_stats$"))
async def usage_stats_callback(client, callback_query):
    """Handle usage stats callback"""
    user_id = callback_query.from_user.id
    is_premium = await Botskingdom.is_premium_user(user_id)
    files_today = await Botskingdom.get_user_usage_today(user_id)
    
    if is_premium:
        text = f'''📊 **Your Usage Statistics**\n\n🌟 **Premium User**\n📁 **Files renamed today:** {files_today}\n🚀 **Daily limit:** Unlimited\n\nYou're enjoying premium benefits! 🎉'''
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("← Back", callback_data="premium_info")]
        ])
    else:
        remaining = Config.FREE_USER_DAILY_LIMIT - files_today
        text = f'''📊 **Your Usage Statistics**\n\n👤 **Free User**\n📁 **Files renamed today:** {files_today}/{Config.FREE_USER_DAILY_LIMIT}\n⏳ **Remaining today:** {remaining}\n\n💡 Upgrade to Premium for unlimited renames!'''
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🌟 Upgrade to Premium", callback_data="premium_info")],
            [InlineKeyboardButton("← Back", callback_data="premium_info")]
        ])
    
    await callback_query.message.edit_text(text, reply_markup=keyboard)

# Clean up function to run periodically
async def cleanup_old_operations():
    """Clean up old renaming operations"""
    while True:
        try:
            await asyncio.sleep(180)  # Run every 3 minutes (faster cleanup)
            current_time = datetime.now()
            
            # Clean up old operations (older than 15 minutes)
            old_operations = [
                key for key, timestamp in renaming_operations.items()
                if (current_time - timestamp).seconds > 900
            ]
            
            for key in old_operations:
                renaming_operations.pop(key, None)
            
            print(f"Cleaned up {len(old_operations)} old operations")
            
        except Exception as e:
            print(f"Error in cleanup: {e}")

# Start cleanup task when the bot starts
asyncio.create_task(cleanup_old_operations())

print("🚀 ULTRA CONCURRENT File Rename Bot - Ready for UNLIMITED Users!")
print(f"📊 Concurrency Limits: Downloads={GLOBAL_DOWNLOAD_SEMAPHORE._value}, Uploads={GLOBAL_UPLOAD_SEMAPHORE._value}, FFmpeg={GLOBAL_FFMPEG_SEMAPHORE._value}")
