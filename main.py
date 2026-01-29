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
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Database initialized")

def save_user(user_id: int, name: str, phone: str, language: str, country: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO users (user_id, name, phone, language, country)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, name, phone, language, country))
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

# ========== SHORT COUNTRY & LANGUAGE DATA ==========
COUNTRIES = {
    'UK': '🇬🇧 UK',
    'RU': '🇷🇺 Russia',
    'BD': '🇧🇩 Bangladesh',
    'IN': '🇮🇳 India',
    'PK': '🇵🇰 Pakistan',
    'PH': '🇵🇭 Philippines',
    'LK': '🇱🇰 Sri Lanka',
    'MY': '🇲🇾 Malaysia',
    'TH': '🇹🇭 Thailand',
    'NG': '🇳🇬 Nigeria',
    'TR': '🇹🇷 Turkey',
    'KE': '🇰🇪 Kenya'
}

LANGUAGES = {
    'EN': '🇬🇧 English',
    'RU': '🇷🇺 Русский',
    'BN': '🇧🇩 বাংলা',
    'HI': '🇮🇳 हिंदी',
    'UR': '🇵🇰 اردو',
    'TL': '🇵🇭 Filipino',
    'SI': '🇱🇰 සිංහල',
    'MS': '🇲🇾 Malay',
    'TH': '🇹🇭 ไทย',
    'TR': '🇹🇷 Türkçe'
}

# ========== COMPACT KEYBOARDS ==========
def get_phone_kb():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📞 Share Contact", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_lang_kb():
    """Compact 2-column language keyboard"""
    buttons = []
    row = []
    for i, (code, name) in enumerate(LANGUAGES.items()):
        row.append(InlineKeyboardButton(name, callback_data=f"lang_{code}"))
        if len(row) == 2 or i == len(LANGUAGES)-1:
            buttons.append(row)
            row = []
    return InlineKeyboardMarkup(buttons)

def get_country_kb():
    """Compact 2-column country keyboard"""
    buttons = []
    row = []
    for i, (code, name) in enumerate(COUNTRIES.items()):
        row.append(InlineKeyboardButton(name, callback_data=f"country_{code}"))
        if len(row) == 2 or i == len(COUNTRIES)-1:
            buttons.append(row)
            row = []
    return InlineKeyboardMarkup(buttons)

def get_user_menu():
    """Short user menu"""
    return ReplyKeyboardMarkup(
        [
            ["📞 Contact"],
            ["ℹ️ Info", "🔄 Restart"]
        ],
        resize_keyboard=True
    )

def get_admin_kb():
    """Compact admin menu"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Broadcast All", callback_data="broadcast_all")],
        [InlineKeyboardButton("👤 Send to User", callback_data="send_user")],
        [InlineKeyboardButton("📊 Stats", callback_data="stats")],
        [InlineKeyboardButton("👥 Users", callback_data="users_list")]
    ])

def get_confirm_kb():
    """Simple confirm buttons"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Send", callback_data="confirm_send")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_send")]
    ])

# ========== CONVERSATION STATES ==========
PHONE, LANGUAGE, COUNTRY = range(3)

# ========== HANDLERS ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.full_name
    
    print(f"🚀 Start: {user_id} ({user_name})")
    
    if user_id in ADMIN_IDS:
        await update.message.reply_text(
            f"👑 Admin {user_name}!\n/admin for panel",
            reply_markup=get_user_menu()
        )
        return ConversationHandler.END
    
    existing = get_user(user_id)
    if existing:
        await update.message.reply_text(
            f"👋 Welcome back {user_name}!",
            reply_markup=get_user_menu()
        )
        return ConversationHandler.END
    
    await update.message.reply_text(
        f"👋 Hi {user_name}!\nShare phone to join:",
        reply_markup=get_phone_kb()
    )
    return PHONE

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.contact:
        phone = update.message.contact.phone_number
        name = update.message.contact.first_name
        
        context.user_data['name'] = name
        context.user_data['phone'] = phone
        
        await update.message.reply_text(
            "✅ Phone saved!\nChoose language:",
            reply_markup=get_lang_kb()
        )
        return LANGUAGE
    
    await update.message.reply_text("📞 Use Share Contact button", reply_markup=get_phone_kb())
    return PHONE

async def handle_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    lang_code = query.data.replace('lang_', '')
    context.user_data['lang'] = lang_code
    
    await query.edit_message_text(
        f"✅ Lang: {LANGUAGES[lang_code]}\nChoose country:",
        reply_markup=get_country_kb()
    )
    return COUNTRY

async def handle_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    country_code = query.data.replace('country_', '')
    
    # Save user
    save_user(
        update.effective_user.id,
        context.user_data['name'],
        context.user_data['phone'],
        context.user_data['lang'],
        country_code
    )
    
    await query.edit_message_text(
        f"✅ Registered!\n🌍 {COUNTRIES[country_code]}\n🗣️ {LANGUAGES[context.user_data['lang']]}"
    )
    
    await query.message.reply_text(
        "Menu:",
        reply_markup=get_user_menu()
    )
    
    return ConversationHandler.END

async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    if text == "📞 Contact":
        await update.message.reply_text("📞 Contact: @SupportManager")
    elif text == "ℹ️ Info":
        await update.message.reply_text("ℹ️ Affiliate Program Bot")
    elif text == "🔄 Restart":
        await start(update, context)

# ========== ADMIN HANDLERS ==========
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Access denied")
        return
    
    context.user_data.clear()
    
    total = get_total_users()
    
    await update.message.reply_text(
        f"👑 Admin Panel\nUsers: {total}",
        reply_markup=get_admin_kb()
    )

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return
    
    if query.data == "send_user":
        context.user_data['awaiting_id'] = True
        await query.edit_message_text(
            "👤 Send User ID:\n\nExample: 8477793739\n/cancel to stop"
        )
    
    elif query.data == "broadcast_all":
        context.user_data['awaiting_broadcast'] = True
        total = get_total_users()
        await query.edit_message_text(
            f"📢 Broadcast to {total} users\n\nSend message:\n/cancel to stop"
        )
    
    elif query.data == "stats":
        total = get_total_users()
        users = get_all_users()
        
        text = f"📊 Stats\n\nTotal: {total}\n"
        
        if users:
            text += "\nRecent:\n"
            for user in users[:5]:
                text += f"• {user['name']} - {COUNTRIES.get(user['country'], user['country'])}\n"
        
        await query.edit_message_text(text)
    
    elif query.data == "users_list":
        users = get_all_users()
        
        if not users:
            await query.edit_message_text("👥 No users")
            return
        
        text = "👥 Users (ID - Name):\n\n"
        for user in users[:10]:
            text += f"`{user['user_id']}` - {user['name']}\n"
        
        if len(users) > 10:
            text += f"\n+{len(users)-10} more"
        
        await query.edit_message_text(text)

async def handle_admin_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        return
    
    text = update.message.text
    
    # Handle User ID input
    if context.user_data.get('awaiting_id'):
        try:
            target_id = int(text)
            user = get_user(target_id)
            
            if not user:
                await update.message.reply_text(f"❌ User {target_id} not found")
                context.user_data.clear()
                await admin(update, context)
                return
            
            context.user_data['target_user'] = user
            context.user_data['awaiting_id'] = False
            context.user_data['awaiting_msg'] = True
            
            await update.message.reply_text(
                f"✅ User: {user['name']}\n\nSend message:\n/cancel to stop"
            )
            return
            
        except ValueError:
            await update.message.reply_text("❌ Invalid ID")
            return
    
    # Handle message for user
    if context.user_data.get('awaiting_msg'):
        user = context.user_data.get('target_user')
        
        if not user:
            await update.message.reply_text("❌ Error")
            context.user_data.clear()
            await admin(update, context)
            return
        
        context.user_data['msg_to_send'] = update.message
        
        await update.message.reply_text(
            f"⚠️ Send to {user['name']}?\n\n{text[:50]}...",
            reply_markup=get_confirm_kb()
        )
        return
    
    # Handle broadcast message
    if context.user_data.get('awaiting_broadcast'):
        context.user_data['broadcast_msg'] = update.message
        context.user_data['awaiting_broadcast'] = False
        
        total = get_total_users()
        await update.message.reply_text(
            f"⚠️ Send to {total} users?\n\n{text[:50]}...",
            reply_markup=get_confirm_kb()
        )
        return
    
    # Default
    await admin(update, context)

async def handle_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return
    
    if query.data == "confirm_send":
        # Send to specific user
        if 'target_user' in context.user_data:
            user = context.user_data['target_user']
            msg = context.user_data['msg_to_send']
            
            try:
                await query.edit_message_text(f"📤 Sending...")
                await context.bot.copy_message(
                    chat_id=user['user_id'],
                    from_chat_id=msg.chat_id,
                    message_id=msg.message_id
                )
                await query.edit_message_text(f"✅ Sent to {user['name']}")
            except Exception as e:
                await query.edit_message_text(f"❌ Failed: {e}")
            
        # Broadcast to all
        elif 'broadcast_msg' in context.user_data:
            msg = context.user_data['broadcast_msg']
            users = get_all_users()
            
            total = len(users)
            success = 0
            
            await query.edit_message_text(f"📤 Sending... 0/{total}")
            
            for i, user in enumerate(users, 1):
                try:
                    await context.bot.copy_message(
                        chat_id=user['user_id'],
                        from_chat_id=msg.chat_id,
                        message_id=msg.message_id
                    )
                    success += 1
                    if i % 5 == 0 or i == total:
                        await query.edit_message_text(f"📤 {i}/{total}")
                except:
                    pass
            
            await query.edit_message_text(f"✅ Sent: {success}/{total}")
        
        context.user_data.clear()
    
    elif query.data == "cancel_send":
        await query.edit_message_text("❌ Cancelled")
        context.user_data.clear()
        await admin(update, context)

async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Cancelled")
    await admin(update, context)

# ========== MAIN ==========
def main():
    print("=" * 50)
    print("🤖 BOT STARTING")
    print("=" * 50)
    
    init_db()
    
    app = Application.builder().token(TOKEN).build()
    
    # User conversation
    conv = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            PHONE: [MessageHandler(filters.CONTACT, handle_contact)],
            LANGUAGE: [CallbackQueryHandler(handle_lang, pattern='^lang_')],
            COUNTRY: [CallbackQueryHandler(handle_country, pattern='^country_')]
        },
        fallbacks=[CommandHandler('cancel', cancel_cmd)]
    )
    
    app.add_handler(conv)
    app.add_handler(CommandHandler('admin', admin))
    app.add_handler(CommandHandler('cancel', cancel_cmd))
    
    # Admin callbacks
    app.add_handler(CallbackQueryHandler(admin_callback, pattern='^broadcast_|^send_|^stats|^users_'))
    app.add_handler(CallbackQueryHandler(handle_confirm, pattern='^confirm_|^cancel_'))
    
    # User menu
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu))
    
    # Admin messages (LAST!)
    app.add_handler(MessageHandler(
        filters.TEXT & filters.User(ADMIN_IDS) & ~filters.COMMAND,
        handle_admin_msg
    ))
    
    print("✅ Bot running!")
    print("📱 /start or /admin")
    print("=" * 50)
    
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
