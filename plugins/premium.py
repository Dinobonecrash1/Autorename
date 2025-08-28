# Premium User Management System
# File: plugins/premium.py

import asyncio
import time
from datetime import datetime, timedelta
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from helper.database import Botskingdom
from config import Config
import logging

logger = logging.getLogger(__name__)

# Premium subscription plans
PREMIUM_PLANS = {
    "monthly": {
        "price": 9.99,
        "duration": 30,  # days
        "name": "Monthly Premium"
    },
    "yearly": {
        "price": 99.99,
        "duration": 365,  # days
        "name": "Yearly Premium"
    }
}

class PremiumManager:
    @staticmethod
    async def is_premium_user(user_id: int) -> bool:
        """Check if user has active premium subscription"""
        try:
            user = await Botskingdom.col.find_one({"_id": user_id})
            if not user:
                return False
            
            subscription = user.get("subscription", {})
            if not subscription.get("is_premium", False):
                return False
            
            # Check if subscription is still valid
            expiry_date = subscription.get("expiry_date")
            if expiry_date and datetime.now() > datetime.fromisoformat(expiry_date):
                # Subscription expired, update user status
                await Botskingdom.col.update_one(
                    {"_id": user_id},
                    {"$set": {"subscription.is_premium": False}}
                )
                return False
            
            return True
        except Exception as e:
            logger.error(f"Error checking premium status for user {user_id}: {e}")
            return False
    
    @staticmethod
    async def get_user_usage_today(user_id: int) -> int:
        """Get number of files renamed today by user"""
        try:
            user = await Botskingdom.col.find_one({"_id": user_id})
            if not user:
                return 0
            
            usage_stats = user.get("usage_stats", {})
            last_reset = usage_stats.get("last_reset")
            today = datetime.now().date().isoformat()
            
            # Reset counter if it's a new day
            if last_reset != today:
                await Botskingdom.col.update_one(
                    {"_id": user_id},
                    {"$set": {
                        "usage_stats.files_renamed_today": 0,
                        "usage_stats.last_reset": today
                    }}
                )
                return 0
            
            return usage_stats.get("files_renamed_today", 0)
        except Exception as e:
            logger.error(f"Error getting usage for user {user_id}: {e}")
            return 0
    
    @staticmethod
    async def can_rename_file(user_id: int) -> tuple[bool, str]:
        """Check if user can rename file and return status message"""
        try:
            is_premium = await PremiumManager.is_premium_user(user_id)
            
            if is_premium:
                return True, "Premium user - unlimited renames"
            
            files_today = await PremiumManager.get_user_usage_today(user_id)
            
            if files_today >= Config.FREE_USER_DAILY_LIMIT:
                return False, f"Daily limit reached! Free users can rename only {Config.FREE_USER_DAILY_LIMIT} files per day. Upgrade to Premium for unlimited renames!"
            
            remaining = Config.FREE_USER_DAILY_LIMIT - files_today
            return True, f"{remaining} files remaining today. Upgrade to Premium for unlimited renames!"
            
        except Exception as e:
            logger.error(f"Error checking rename permission for user {user_id}: {e}")
            return False, "Error checking permissions. Please try again."
    
    @staticmethod
    async def increment_file_count(user_id: int):
        """Increment daily file count for user"""
        try:
            today = datetime.now().date().isoformat()
            await Botskingdom.col.update_one(
                {"_id": user_id},
                {
                    "$inc": {"usage_stats.files_renamed_today": 1},
                    "$set": {"usage_stats.last_reset": today}
                }
            )
        except Exception as e:
            logger.error(f"Error incrementing file count for user {user_id}: {e}")
    
    @staticmethod
    async def activate_premium(user_id: int, plan: str, payment_id: str = None) -> bool:
        """Activate premium subscription for user"""
        try:
            if plan not in PREMIUM_PLANS:
                return False
            
            plan_info = PREMIUM_PLANS[plan]
            expiry_date = datetime.now() + timedelta(days=plan_info["duration"])
            
            subscription_data = {
                "is_premium": True,
                "plan": plan,
                "activated_on": datetime.now().isoformat(),
                "expiry_date": expiry_date.isoformat(),
                "payment_id": payment_id
            }
            
            await Botskingdom.col.update_one(
                {"_id": user_id},
                {"$set": {"subscription": subscription_data}}
            )
            
            logger.info(f"Premium activated for user {user_id}, plan: {plan}")
            return True
        except Exception as e:
            logger.error(f"Error activating premium for user {user_id}: {e}")
            return False

# Bot commands for premium features
@Client.on_message(filters.private & filters.command("premium"))
async def premium_info(client, message: Message):
    """Show premium subscription information"""
    user_id = message.from_user.id
    
    is_premium = await PremiumManager.is_premium_user(user_id)
    
    if is_premium:
        user = await Botskingdom.col.find_one({"_id": user_id})
        subscription = user.get("subscription", {})
        expiry = subscription.get("expiry_date", "Unknown")
        plan = subscription.get("plan", "Unknown")
        
        text = f'''🌟 **Premium Status: ACTIVE**

📅 **Plan:** {PREMIUM_PLANS.get(plan, {}).get("name", plan)}
⏰ **Expires:** {expiry[:10] if expiry != "Unknown" else "Unknown"}
🚀 **Benefits:** Unlimited file renames'''
    else:
        files_today = await PremiumManager.get_user_usage_today(user_id)
        remaining = Config.FREE_USER_DAILY_LIMIT - files_today
        
        text = f'''💰 **Premium Subscription**

**Current Status:** Free User
**Files renamed today:** {files_today}/{Config.FREE_USER_DAILY_LIMIT}
**Remaining today:** {remaining}

🌟 **Premium Benefits:**
• Unlimited file renames
• Priority processing
• Advanced features
• 24/7 support

💳 **Available Plans:**
• Monthly: ${PREMIUM_PLANS["monthly"]["price"]}/month
• Yearly: ${PREMIUM_PLANS["yearly"]["price"]}/year (Save 17%)'''
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💳 Monthly Plan", callback_data="buy_monthly"),
            InlineKeyboardButton("💎 Yearly Plan", callback_data="buy_yearly")
        ],
        [InlineKeyboardButton("❓ Support", url="https://t.me/Flame_Bots")]
    ])
    
    await message.reply_text(text, reply_markup=keyboard)

@Client.on_message(filters.private & filters.command("usage"))
async def usage_stats(client, message: Message):
    """Show user's current usage statistics"""
    user_id = message.from_user.id
    
    is_premium = await PremiumManager.is_premium_user(user_id)
    files_today = await PremiumManager.get_user_usage_today(user_id)
    
    if is_premium:
        text = f'''📊 **Your Usage Statistics**

🌟 **Premium User**
📁 **Files renamed today:** {files_today}
🚀 **Daily limit:** Unlimited

You're enjoying premium benefits! 🎉'''
    else:
        remaining = Config.FREE_USER_DAILY_LIMIT - files_today
        text = f'''📊 **Your Usage Statistics**

👤 **Free User**
📁 **Files renamed today:** {files_today}/{Config.FREE_USER_DAILY_LIMIT}
⏳ **Remaining today:** {remaining}

💡 Upgrade to Premium for unlimited renames!'''
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🌟 Upgrade to Premium", callback_data="premium_info")],
        [InlineKeyboardButton("📈 View Plans", callback_data="view_plans")]
    ])
    
    await message.reply_text(text, reply_markup=keyboard)

@Client.on_callback_query(filters.regex("^buy_"))
async def handle_premium_purchase(client, callback_query):
    """Handle premium purchase callback"""
    plan = callback_query.data.split("_")[1]  # monthly or yearly
    user_id = callback_query.from_user.id
    
    if plan not in PREMIUM_PLANS:
        await callback_query.answer("Invalid plan selected!", show_alert=True)
        return
    
    plan_info = PREMIUM_PLANS[plan]
    
    text = f'''💳 **Purchase {plan_info["name"]}**

💰 **Price:** ${plan_info["price"]}
⏱️ **Duration:** {plan_info["duration"]} days
🌟 **Benefits:** Unlimited file renames

**Payment Methods:**
• UPI: aryanchoudhary2ty@oksbi
• PayPal: your_paypal_email
• Crypto: Contact admin

After payment, send screenshot to admin for activation.'''
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 Contact Admin", url="https://t.me/Zenitsu_AF")],
        [InlineKeyboardButton("← Back", callback_data="premium_info")]
    ])
    
    await callback_query.message.edit_text(text, reply_markup=keyboard)

@Client.on_callback_query(filters.regex("^premium_info$"))
async def premium_info_callback(client, callback_query):
    """Handle premium info callback"""
    user_id = callback_query.from_user.id
    
    is_premium = await PremiumManager.is_premium_user(user_id)
    
    if is_premium:
        text = "🌟 **You are already a Premium user!**\n\nEnjoy unlimited file renames! 🚀"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 View Usage", callback_data="usage_stats")]
        ])
    else:
        files_today = await PremiumManager.get_user_usage_today(user_id)
        remaining = Config.FREE_USER_DAILY_LIMIT - files_today
        
        text = f'''💰 **Premium Subscription**\n\n**Current Status:** Free User\n**Files renamed today:** {files_today}/{Config.FREE_USER_DAILY_LIMIT}\n**Remaining today:** {remaining}\n\n🌟 **Premium Benefits:**\n• Unlimited file renames\n• Priority processing\n• Advanced features\n• 24/7 support\n\n💳 **Available Plans:**\n• Monthly: $9.99/month\n• Yearly: $99.99/year (Save 17%)'''
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("💳 Monthly Plan", callback_data="buy_monthly"),
                InlineKeyboardButton("💎 Yearly Plan", callback_data="buy_yearly")
            ],
            [InlineKeyboardButton("💬 Contact Admin", url="https://t.me/Zenitsu_AF")]
        ])
    
    await callback_query.message.edit_text(text, reply_markup=keyboard)

@Client.on_callback_query(filters.regex("^usage_stats$"))
async def usage_stats_callback(client, callback_query):
    """Handle usage stats callback"""
    user_id = callback_query.from_user.id
    
    is_premium = await PremiumManager.is_premium_user(user_id)
    files_today = await PremiumManager.get_user_usage_today(user_id)
    
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

@Client.on_callback_query(filters.regex("^view_plans$"))
async def view_plans_callback(client, callback_query):
    """Handle view plans callback"""
    text = f'''💳 **Premium Plans**

**Monthly Plan: ${PREMIUM_PLANS["monthly"]["price"]}/month**
• 30 days access
• Unlimited file renames
• Priority processing
• Advanced features

**Yearly Plan: ${PREMIUM_PLANS["yearly"]["price"]}/year**
• 365 days access
• All monthly benefits
• Save 17% compared to monthly
• Best value for money

🎯 **What you get:**
✅ Unlimited daily file renames
✅ No waiting times
✅ Priority support
✅ Advanced features
✅ Premium badge'''
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💳 Buy Monthly", callback_data="buy_monthly"),
            InlineKeyboardButton("💎 Buy Yearly", callback_data="buy_yearly")
        ],
        [InlineKeyboardButton("← Back", callback_data="premium_info")]
    ])
    
    await callback_query.message.edit_text(text, reply_markup=keyboard)

# Admin commands for premium management
@Client.on_message(filters.private & filters.command("addpremium") & filters.user(Config.ADMIN))
async def add_premium_user(client, message: Message):
    """Admin command to add premium user"""
    try:
        args = message.text.split()
        if len(args) < 3:
            await message.reply_text("Usage: /addpremium <user_id> <plan> [payment_id]\nPlans: monthly, yearly")
            return
        
        user_id = int(args[1])
        plan = args[2].lower()
        payment_id = args[3] if len(args) > 3 else f"admin_added_{int(time.time())}"
        
        if plan not in PREMIUM_PLANS:
            await message.reply_text(f"Invalid plan. Available: {', '.join(PREMIUM_PLANS.keys())}")
            return
        
        success = await PremiumManager.activate_premium(user_id, plan, payment_id)
        
        if success:
            await message.reply_text(f"✅ Premium activated for user {user_id} with {plan} plan")
            # Notify user
            try:
                await client.send_message(
                    user_id, 
                    f"🎉 **Premium Activated!**\n\n"
                    f"Your {PREMIUM_PLANS[plan]['name']} subscription is now active!\n"
                    f"Enjoy unlimited file renames! 🚀"
                )
            except:
                pass
        else:
            await message.reply_text("❌ Failed to activate premium")
    except ValueError:
        await message.reply_text("Invalid user ID format")
    except Exception as e:
        await message.reply_text(f"Error: {str(e)}")

@Client.on_message(filters.private & filters.command("removepremium") & filters.user(Config.ADMIN))
async def remove_premium_user(client, message: Message):
    """Admin command to remove premium user"""
    try:
        args = message.text.split()
        if len(args) < 2:
            await message.reply_text("Usage: /removepremium <user_id>")
            return
        
        user_id = int(args[1])
        
        await Botskingdom.col.update_one(
            {"_id": user_id},
            {"$set": {"subscription.is_premium": False}}
        )
        
        await message.reply_text(f"✅ Premium removed for user {user_id}")
        
        # Notify user
        try:
            await client.send_message(
                user_id, 
                "📢 **Premium Subscription Ended**\n\n"
                "Your premium subscription has been deactivated.\n"
                "You now have a daily limit of 100 file renames.\n\n"
                "Upgrade again to enjoy unlimited renames! /premium"
            )
        except:
            pass
    except ValueError:
        await message.reply_text("Invalid user ID format")
    except Exception as e:
        await message.reply_text(f"Error: {str(e)}")

@Client.on_message(filters.private & filters.command("premiumusers") & filters.user(Config.ADMIN))
async def list_premium_users(client, message: Message):
    """Admin command to list all premium users"""
    try:
        premium_users = await Botskingdom.col.find({
            "subscription.is_premium": True
        }).to_list(length=None)
        
        if not premium_users:
            await message.reply_text("No premium users found.")
            return
        
        text = "🌟 **Premium Users:**\n\n"
        for user in premium_users:
            user_id = user["_id"]
            subscription = user.get("subscription", {})
            plan = subscription.get("plan", "Unknown")
            expiry = subscription.get("expiry_date", "Unknown")
            
            text += f"👤 **User ID:** `{user_id}`\n"
            text += f"📅 **Plan:** {plan}\n"
            text += f"⏰ **Expires:** {expiry[:10] if expiry != 'Unknown' else 'Unknown'}\n\n"
        
        # Send in chunks if too long
        if len(text) > 4000:
            for i in range(0, len(text), 4000):
                await message.reply_text(text[i:i+4000])
        else:
            await message.reply_text(text)
    except Exception as e:
        await message.reply_text(f"Error: {str(e)}")

@Client.on_message(filters.private & filters.command("premiumstats") & filters.user(Config.ADMIN))
async def premium_statistics(client, message: Message):
    """Admin command to show premium statistics"""
    try:
        total_users = await Botskingdom.col.count_documents({})
        premium_users = await Botskingdom.col.count_documents({"subscription.is_premium": True})
        monthly_users = await Botskingdom.col.count_documents({"subscription.plan": "monthly"})
        yearly_users = await Botskingdom.col.count_documents({"subscription.plan": "yearly"})
        
        free_users = total_users - premium_users
        conversion_rate = (premium_users / total_users * 100) if total_users > 0 else 0
        
        text = f'''📊 **Premium Statistics**

👥 **Total Users:** {total_users}
🌟 **Premium Users:** {premium_users}
👤 **Free Users:** {free_users}
📈 **Conversion Rate:** {conversion_rate:.2f}%

💳 **Plan Distribution:**
📅 Monthly: {monthly_users}
🗓️ Yearly: {yearly_users}

💰 **Revenue Estimation:**
Monthly: ${monthly_users * PREMIUM_PLANS["monthly"]["price"]:.2f}
Yearly: ${yearly_users * PREMIUM_PLANS["yearly"]["price"]:.2f}
Total: ${(monthly_users * PREMIUM_PLANS["monthly"]["price"]) + (yearly_users * PREMIUM_PLANS["yearly"]["price"]):.2f}'''
        
        await message.reply_text(text)
    except Exception as e:
        await message.reply_text(f"Error: {str(e)}")
