import motor.motor_asyncio, datetime, pytz
from config import Config
import logging # Added for logging errors and important information
from .utils import send_log

class Database:
    def __init__(self, uri, database_name):
        try:
            self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
            self._client.server_info() # This will raise an exception if the connection fails
            logging.info("Successfully connected to MongoDB")
        except Exception as e:
            logging.error(f"Failed to connect to MongoDB: {e}")
            raise e # Re-raise the exception after logging it
        self.Botskingdom = self._client[database_name]
        self.col = self.Botskingdom.user

    def new_user(self, id, username=None):
        return dict(
            _id=int(id),
            username=username.lower() if username else None,
            join_date=datetime.date.today().isoformat(),
            file_id=None,
            caption=None,
            metadata=True,
            metadata_code="Telegram : @botskingdoms",
            format_template=None,
            # Premium subscription info
            subscription=dict(
                is_premium=False,
                plan=None,  # 'monthly' or 'yearly'
                activated_on=None,
                expiry_date=None,
                payment_id=None
            ),
            # Usage tracking for daily limits
            usage_stats=dict(
                files_renamed_today=0,
                last_reset=datetime.date.today().isoformat(),
                total_files_renamed=0
            ),
            ban_status=dict(
                is_banned=False,
                banned_on=datetime.date.max.isoformat(),
                ban_reason=''
            )
        )
    
    async def add_user(self, b, m):
        u = m.from_user
        if not await self.is_user_exist(u.id):
            user = self.new_user(u.id, u.username)
            try:
                await self.col.insert_one(user)
                await send_log(b, u)
            except Exception as e:
                logging.error(f"Error adding user {u.id}: {e}")

    # Premium-related methods
    async def is_premium_user(self, user_id: int) -> bool:
        """Check if user has active premium subscription"""
        try:
            user = await self.col.find_one({"_id": int(user_id)})
            if not user:
                return False
            
            subscription = user.get("subscription", {})
            if not subscription.get("is_premium", False):
                return False
            
            # Check if subscription is still valid
            expiry_date = subscription.get("expiry_date")
            if expiry_date:
                try:
                    expiry = datetime.datetime.fromisoformat(expiry_date)
                    if datetime.datetime.now() > expiry:
                        # Subscription expired, update user status
                        await self.col.update_one(
                            {"_id": int(user_id)},
                            {"$set": {"subscription.is_premium": False}}
                        )
                        return False
                except ValueError:
                    # Invalid date format, assume expired
                    return False
            
            return True
        except Exception as e:
            logging.error(f"Error checking premium status for user {user_id}: {e}")
            return False
    
    async def get_user_usage_today(self, user_id: int) -> int:
        """Get number of files renamed today by user"""
        try:
            user = await self.col.find_one({"_id": int(user_id)})
            if not user:
                return 0
            
            usage_stats = user.get("usage_stats", {})
            last_reset = usage_stats.get("last_reset")
            today = datetime.date.today().isoformat()
            
            # Reset counter if it's a new day
            if last_reset != today:
                await self.col.update_one(
                    {"_id": int(user_id)},
                    {"$set": {
                        "usage_stats.files_renamed_today": 0,
                        "usage_stats.last_reset": today
                    }}
                )
                return 0
            
            return usage_stats.get("files_renamed_today", 0)
        except Exception as e:
            logging.error(f"Error getting usage for user {user_id}: {e}")
            return 0
    
    async def can_rename_file(self, user_id: int) -> tuple[bool, str]:
        """Check if user can rename file and return status message"""
        try:
            is_premium = await self.is_premium_user(user_id)
            
            if is_premium:
                return True, "Premium user - unlimited renames"
            
            files_today = await self.get_user_usage_today(user_id)
            
            if files_today >= Config.FREE_USER_DAILY_LIMIT:
                return False, f"Daily limit reached! Free users can rename only {Config.FREE_USER_DAILY_LIMIT} files per day. Upgrade to Premium for unlimited renames!"
            
            remaining = Config.FREE_USER_DAILY_LIMIT - files_today
            return True, f"{remaining} files remaining today. Upgrade to Premium for unlimited renames!"
            
        except Exception as e:
            logging.error(f"Error checking rename permission for user {user_id}: {e}")
            return False, "Error checking permissions. Please try again."
    
    async def increment_file_count(self, user_id: int):
        """Increment daily file count for user"""
        try:
            today = datetime.date.today().isoformat()
            await self.col.update_one(
                {"_id": int(user_id)},
                {
                    "$inc": {
                        "usage_stats.files_renamed_today": 1,
                        "usage_stats.total_files_renamed": 1
                    },
                    "$set": {"usage_stats.last_reset": today}
                }
            )
        except Exception as e:
            logging.error(f"Error incrementing file count for user {user_id}: {e}")
    
    async def activate_premium(self, user_id: int, plan: str, expiry_date: str, payment_id: str = None) -> bool:
        """Activate premium subscription for user"""
        try:
            subscription_data = {
                "subscription.is_premium": True,
                "subscription.plan": plan,
                "subscription.activated_on": datetime.datetime.now().isoformat(),
                "subscription.expiry_date": expiry_date,
                "subscription.payment_id": payment_id
            }
            
            result = await self.col.update_one(
                {"_id": int(user_id)},
                {"$set": subscription_data}
            )
            
            logging.info(f"Premium activated for user {user_id}, plan: {plan}")
            return result.modified_count > 0
        except Exception as e:
            logging.error(f"Error activating premium for user {user_id}: {e}")
            return False
    
    async def get_premium_users(self):
        """Get all premium users"""
        try:
            cursor = self.col.find({"subscription.is_premium": True})
            return cursor
        except Exception as e:
            logging.error(f"Error getting premium users: {e}")
            return None
    
    # Existing methods (keeping all the original functionality)
    async def is_user_exist(self, id):
        try:
            user = await self.col.find_one({"_id": int(id)})
            return bool(user)
        except Exception as e:
            logging.error(f"Error checking if user {id} exists: {e}")
            return False

    async def total_users_count(self):
        try:
            count = await self.col.count_documents({})
            return count
        except Exception as e:
            logging.error(f"Error counting users: {e}")
            return 0

    async def get_all_users(self):
        try:
            all_users = self.col.find({})
            return all_users
        except Exception as e:
            logging.error(f"Error getting all users: {e}")
            return None

    async def delete_user(self, user_id):
        try:
            await self.col.delete_many({"_id": int(user_id)})
        except Exception as e:
            logging.error(f"Error deleting user {user_id}: {e}")

    async def set_thumbnail(self, id, file_id):
        try:
            await self.col.update_one({"_id": int(id)}, {"$set": {"file_id": file_id}})
        except Exception as e:
            logging.error(f"Error setting thumbnail for user {id}: {e}")

    async def get_thumbnail(self, id):
        try:
            user = await self.col.find_one({"_id": int(id)})
            return user.get("file_id", None) if user else None
        except Exception as e:
            logging.error(f"Error getting thumbnail for user {id}: {e}")
            return None

    async def set_caption(self, id, caption):
        try:
            await self.col.update_one({"_id": int(id)}, {"$set": {"caption": caption}})
        except Exception as e:
            logging.error(f"Error setting caption for user {id}: {e}")

    async def get_caption(self, id):
        try:
            user = await self.col.find_one({"_id": int(id)})
            return user.get("caption", None) if user else None
        except Exception as e:
            logging.error(f"Error getting caption for user {id}: {e}")
            return None

    async def set_format_template(self, id, format_template):
        try:
            await self.col.update_one(
                {"_id": int(id)}, {"$set": {"format_template": format_template}}
            )
        except Exception as e:
            logging.error(f"Error setting format template for user {id}: {e}")

    async def get_format_template(self, id):
        try:
            user = await self.col.find_one({"_id": int(id)})
            return user.get("format_template", None) if user else None
        except Exception as e:
            logging.error(f"Error getting format template for user {id}: {e}")
            return None

    async def set_media_preference(self, id, media_type):
        try:
            await self.col.update_one(
                {"_id": int(id)}, {"$set": {"media_type": media_type}}
            )
        except Exception as e:
            logging.error(f"Error setting media preference for user {id}: {e}")

    async def get_media_preference(self, id):
        try:
            user = await self.col.find_one({"_id": int(id)})
            return user.get("media_type", None) if user else None
        except Exception as e:
            logging.error(f"Error getting media preference for user {id}: {e}")
            return None

    # Metadata methods
    async def get_metadata(self, user_id):
        user = await self.col.find_one({'_id': int(user_id)})
        return user.get('metadata', "Off")

    async def set_metadata(self, user_id, metadata):
        await self.col.update_one({'_id': int(user_id)}, {'$set': {'metadata': metadata}})

    async def get_title(self, user_id):
        user = await self.col.find_one({'_id': int(user_id)})
        return user.get('title', 'Botskingdom')

    async def set_title(self, user_id, title):
        await self.col.update_one({'_id': int(user_id)}, {'$set': {'title': title}})

    async def get_author(self, user_id):
        user = await self.col.find_one({'_id': int(user_id)})
        return user.get('author', 'Botskingdom')

    async def set_author(self, user_id, author):
        await self.col.update_one({'_id': int(user_id)}, {'$set': {'author': author}})

    async def get_artist(self, user_id):
        user = await self.col.find_one({'_id': int(user_id)})
        return user.get('artist', 'Botskingdom')

    async def set_artist(self, user_id, artist):
        await self.col.update_one({'_id': int(user_id)}, {'$set': {'artist': artist}})

    async def get_audio(self, user_id):
        user = await self.col.find_one({'_id': int(user_id)})
        return user.get('audio', 'Botskingdom')

    async def set_audio(self, user_id, audio):
        await self.col.update_one({'_id': int(user_id)}, {'$set': {'audio': audio}})

    async def get_subtitle(self, user_id):
        user = await self.col.find_one({'_id': int(user_id)})
        return user.get('subtitle', "Botskingdom")

    async def set_subtitle(self, user_id, subtitle):
        await self.col.update_one({'_id': int(user_id)}, {'$set': {'subtitle': subtitle}})

    async def get_video(self, user_id):
        user = await self.col.find_one({'_id': int(user_id)})
        return user.get('video', 'Botskingdom')

    async def set_video(self, user_id, video):
        await self.col.update_one({'_id': int(user_id)}, {'$set': {'video': video}})

    async def get_encoded_by(self, user_id):
        user = await self.col.find_one({'_id': int(user_id)})
        return user.get('encoded_by', "Botskingdom")

    async def set_encoded_by(self, user_id, encoded_by):
        await self.col.update_one({'_id': int(user_id)}, {'$set': {'encoded_by': encoded_by}})
    
    async def get_custom_tag(self, user_id):
        user = await self.col.find_one({'_id': int(user_id)})
        return user.get('customtag', "Botskingdom")

    async def set_custom_tag(self, user_id, custom_tag):
        await self.col.update_one({'_id': int(user_id)}, {'$set': {'custom_tag': custom_tag}})

    # Ban/unban methods (Fixed the original broken implementation)
    async def ban_user(self, user_id):
        try:
            await self.col.update_one(
                {"_id": int(user_id)}, 
                {"$set": {"ban_status.is_banned": True, "ban_status.banned_on": datetime.date.today().isoformat()}}
            )
        except Exception as e:
            logging.error(f"Error banning user {user_id}: {e}")
    
    async def unban_user(self, user_id):
        try:
            await self.col.update_one(
                {"_id": int(user_id)}, 
                {"$set": {"ban_status.is_banned": False}}
            )
        except Exception as e:
            logging.error(f"Error unbanning user {user_id}: {e}")

    async def is_banned(self, user_id):
        try:
            user = await self.col.find_one({"_id": int(user_id)})
            return user.get("ban_status", {}).get("is_banned", False) if user else False
        except Exception as e:
            logging.error(f"Error checking ban status for user {user_id}: {e}")
            return False

    async def get_banned_users(self):
        try:
            return self.col.find({"ban_status.is_banned": True})
        except Exception as e:
            logging.error(f"Error getting banned users: {e}")
            return None

Botskingdom = Database(Config.DB_URL, Config.DB_NAME)