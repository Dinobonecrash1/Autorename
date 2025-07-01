import os
import asyncio
import shutil
from datetime import datetime

async def auto_rename_file(client, message, file_info, is_sequence=False, status_msg=None, manual_rename=False):
    try:
        user_id = message.from_user.id
        file_id = file_info["file_id"]
        orig_file_name = file_info["file_name"]

        # 1. Determine new file name
        if manual_rename and "manual_new_name" in file_info:
            new_file_name = file_info["manual_new_name"]
            # Add extension if not present
            _, ext = os.path.splitext(orig_file_name)
            if not os.path.splitext(new_file_name)[1]:
                new_file_name += ext
            renamed_file_name = new_file_name
        else:
            # ----- AUTO MODE: Use template -----
            # Fetch template and preferences
            format_template = await codeflixbots.get_format_template(user_id)
            media_preference = await codeflixbots.get_media_preference(user_id)

            if not format_template:
                error_msg = "Please Set An Auto Rename Format First Using /autorename"
                if status_msg:
                    return await status_msg.edit(error_msg)
                else:
                    return await message.reply_text(error_msg)

            # Compose new name (add your own logic for episode, season, quality, etc.)
            episode_number = file_info.get("episode_num", 1)
            template = format_template.replace("{episode}", str(episode_number))
            # Add similar replacements for season, quality, etc., as your logic requires

            _, ext = os.path.splitext(orig_file_name)
            renamed_file_name = f"{template}{ext}"

        # 2. Prepare paths
        renamed_file_path = f"downloads/{renamed_file_name}"
        metadata_file_path = f"Metadata/{renamed_file_name}"
        os.makedirs(os.path.dirname(renamed_file_path), exist_ok=True)
        os.makedirs(os.path.dirname(metadata_file_path), exist_ok=True)

        # 3. Download file
        if status_msg:
            download_msg = status_msg
            await download_msg.edit("Downloading file...")
        else:
            download_msg = await message.reply_text("Downloading file...")

        path = await client.download_media(
            file_info["message"],
            file_name=renamed_file_path
        )

        # 4. Add metadata (optional, use your logic)
        # Skipping for brevity. If not needed, use `path` directly for upload.

        # 5. Upload file
        if status_msg:
            upload_msg = status_msg
            await upload_msg.edit("Uploading file...")
        else:
            upload_msg = await message.reply_text("Uploading file...")

        media_type = "document"
        if renamed_file_name.endswith(".mp4"):
            media_type = "video"
        elif renamed_file_name.endswith(".mp3"):
            media_type = "audio"

        if media_type == "document":
            await client.send_document(
                message.chat.id,
                document=path,
                caption=renamed_file_name
            )
        elif media_type == "video":
            await client.send_video(
                message.chat.id,
                video=path,
                caption=renamed_file_name
            )
        elif media_type == "audio":
            await client.send_audio(
                message.chat.id,
                audio=path,
                caption=renamed_file_name
            )

        # 6. Clean up
        if os.path.exists(path):
            os.remove(path)
        if os.path.exists(renamed_file_path):
            os.remove(renamed_file_path)
        if os.path.exists(metadata_file_path):
            os.remove(metadata_file_path)

        if status_msg:
            await status_msg.delete()
        else:
            await upload_msg.delete()

    except Exception as e:
        if status_msg:
            await status_msg.edit(f"Error: {e}")
        else:
            await message.reply_text(f"Error: {e}")
