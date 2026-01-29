import os
import sys
import logging
import sqlite3
from datetime import datetime
from typing import Dict, Any, List, Optional

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    ContextTypes
)

# ========== CONFIGURATION ==========
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '8236723437:AAGMxhUm1uwMeqskhvj3HoGRREu3_5i_g1c')
ADMIN_IDS = [7771621948]  # Your admin ID
DB_PATH = 'bot.db'

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ========== DATABASE SETUP ==========
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            name TEXT,
            phone TEXT,
            language TEXT,
            country TEXT,
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_states (
            user_id INTEGER PRIMARY KEY,
            state TEXT,
            data TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

def get_user(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    columns = [description[0] for description in cursor.description]
    result = cursor.fetchone()
    conn.close()
    return dict(zip(columns, result)) if result else None

def get_all_users():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users ORDER BY registered_at DESC')
    columns = [description[0] for description in cursor.description]
    results = cursor.fetchall()
    conn.close()
    return [dict(zip(columns, row)) for row in results]

def get_total_users():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM users')
    count = cursor.fetchone()[0]
    conn.close()
    return count

# ========== KEYBOARDS ==========
def get_admin_keyboard():
    """Admin menu keyboard - SIMPLIFIED"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Broadcast to All", callback_data="broadcast_all")],
        [InlineKeyboardButton("👤 Send to Specific User", callback_data="send_specific")],
        [InlineKeyboardButton("📊 User Statistics", callback_data="user_stats")],
        [InlineKeyboardButton("👥 User List", callback_data="user_list")]
    ])

def get_broadcast_confirm_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Send", callback_data="confirm_send")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_send")]
    ])

# ========== HANDLERS ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id in ADMIN_IDS:
        await update.message.reply_text(
            f"👑 Welcome Admin! Use /admin for admin panel."
        )
        return
    
    await update.message.reply_text(
        "👋 Welcome! This is Affiliate Support Bot.\n"
        "Contact admin for access."
    )

# ========== ADMIN HANDLERS ==========
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Access denied.")
        return
    
    # Clear any previous states
    context.user_data.clear()
    
    total_users = get_total_users()
    
    await update.message.reply_text(
        f"👑 ADMIN PANEL\n\n"
        f"Total Users: {total_users}\n\n"
        f"Select option:",
        reply_markup=get_admin_keyboard()
    )

async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin callbacks"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return
    
    if query.data == "send_specific":
        # Set state for specific user
        context.user_data['awaiting_user_id'] = True
        
        await query.edit_message_text(
            "👤 **SEND TO SPECIFIC USER**\n\n"
            "Send me the User ID:\n"
            "(Get from User List)\n\n"
            "Or send /cancel"
        )
    
    elif query.data == "user_stats":
        total = get_total_users()
        await query.edit_message_text(f"📊 Total Users: {total}")
    
    elif query.data == "user_list":
        users = get_all_users()
        if not users:
            await query.edit_message_text("No users yet.")
            return
        
        text = "👥 **USER LIST**\n\n"
        for user in users[:10]:
            text += f"• {user['name']} - ID: `{user['user_id']}`\n"
        
        if len(users) > 10:
            text += f"\n... and {len(users)-10} more"
        
        await query.edit_message_text(text)
    
    elif query.data == "broadcast_all":
        context.user_data['awaiting_broadcast'] = True
        await query.edit_message_text(
            "📢 **BROADCAST TO ALL**\n\n"
            "Send your message to broadcast to all users:\n\n"
            "Or send /cancel"
        )

async def handle_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin messages"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        return
    
    text = update.message.text
    
    # Handle User ID input
    if context.user_data.get('awaiting_user_id'):
        try:
            target_id = int(text)
            user = get_user(target_id)
            
            if not user:
                await update.message.reply_text(f"❌ User ID {target_id} not found.")
                context.user_data.clear()
                await admin_panel(update, context)
                return
            
            # Store user info
            context.user_data['target_user'] = user
            context.user_data['awaiting_user_id'] = False
            context.user_data['awaiting_message'] = True
            
            await update.message.reply_text(
                f"✅ User found: {user['name']}\n\n"
                f"Now send the message for this user:\n\n"
                f"Or send /cancel"
            )
            return
            
        except ValueError:
            await update.message.reply_text("❌ Invalid User ID. Send numbers only.")
            return
    
    # Handle message for specific user
    if context.user_data.get('awaiting_message'):
        user = context.user_data.get('target_user')
        
        if not user:
            await update.message.reply_text("❌ User data lost. Start over.")
            context.user_data.clear()
            await admin_panel(update, context)
            return
        
        # Store message
        context.user_data['message_to_send'] = update.message
        
        await update.message.reply_text(
            f"⚠️ **CONFIRM SEND**\n\n"
            f"Send this to {user['name']} (ID: {user['user_id']})?\n\n"
            f"Message: {text[:100] if text else 'Media message'}...",
            reply_markup=get_broadcast_confirm_keyboard()
        )
        return
    
    # Handle broadcast message
    if context.user_data.get('awaiting_broadcast'):
        context.user_data['broadcast_message'] = update.message
        context.user_data['awaiting_broadcast'] = False
        
        total = get_total_users()
        await update.message.reply_text(
            f"⚠️ **CONFIRM BROADCAST**\n\n"
            f"Send to ALL {total} users?\n\n"
            f"Message: {text[:100] if text else 'Media message'}...",
            reply_markup=get_broadcast_confirm_keyboard()
        )
        return
    
    # Default: show admin panel
    await admin_panel(update, context)

async def handle_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle confirmation buttons"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return
    
    if query.data == "confirm_send":
        # Check what type of send
        if 'target_user' in context.user_data:
            # Send to specific user
            user = context.user_data['target_user']
            message = context.user_data['message_to_send']
            
            try:
                await context.bot.copy_message(
                    chat_id=user['user_id'],
                    from_chat_id=message.chat_id,
                    message_id=message.message_id
                )
                await query.edit_message_text(f"✅ Sent to {user['name']}!")
            except Exception as e:
                await query.edit_message_text(f"❌ Failed: {str(e)}")
            
        elif 'broadcast_message' in context.user_data:
            # Broadcast to all
            message = context.user_data['broadcast_message']
            users = get_all_users()
            
            total = len(users)
            successful = 0
            
            progress = await query.message.reply_text(f"📤 Sending... 0/{total}")
            
            for i, user in enumerate(users, 1):
                try:
                    await context.bot.copy_message(
                        chat_id=user['user_id'],
                        from_chat_id=message.chat_id,
                        message_id=message.message_id
                    )
                    successful += 1
                    
                    if i % 5 == 0 or i == total:
                        await progress.edit_text(f"📤 Sending... {i}/{total}")
                except:
                    pass
            
            await progress.edit_text(f"✅ Sent to {successful}/{total} users!")
            await query.edit_message_text("✅ Broadcast complete!")
        
        # Clear all data
        context.user_data.clear()
    
    elif query.data == "cancel_send":
        await query.edit_message_text("❌ Cancelled.")
        context.user_data.clear()
        await admin_panel(update, context)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel operation"""
    user_id = update.effective_user.id
    if user_id in ADMIN_IDS:
        context.user_data.clear()
        await update.message.reply_text("❌ Cancelled.")
        await admin_panel(update, context)
    else:
        await update.message.reply_text("Use /start to begin.")

# ========== MAIN FUNCTION ==========
def main():
    """Start the bot"""
    print("=" * 50)
    print("🤖 AFFILIATE BOT - STARTING")
    print("=" * 50)
    
    # Initialize database
    init_db()
    
    # Create application
    application = Application.builder().token(TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('admin', admin_panel))
    application.add_handler(CommandHandler('cancel', cancel))
    
    # Admin handlers
    application.add_handler(CallbackQueryHandler(admin_callback_handler, pattern='^broadcast_|^send_|^user_'))
    application.add_handler(CallbackQueryHandler(handle_confirmation, pattern='^confirm_|^cancel_'))
    
    # Admin message handler (MUST BE LAST)
    application.add_handler(MessageHandler(
        filters.TEXT & filters.User(ADMIN_IDS) & ~filters.COMMAND,
        handle_admin_message
    ))
    
    # Start bot
    print("✅ Bot is RUNNING!")
    print("📱 Test: /admin")
    print("=" * 50)
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
