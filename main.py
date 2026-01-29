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
TOKEN = os.environ['TELEGRAM_BOT_TOKEN'] 
ADMIN_IDS = []
try:
    admin_ids_str = os.environ.get('ADMIN_IDS', '7771621948')
    ADMIN_IDS = [int(x.strip()) for x in admin_ids_str.split(',') if x.strip()]
except:
    ADMIN_IDS = [7771621948]

print(f"🔑 Bot Token: {TOKEN[:10]}...")
print(f"👑 Admin IDs: {ADMIN_IDS}")

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
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            message_type TEXT,
            content TEXT,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

def save_user_state(user_id: int, state: str, data: str = ''):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO user_states VALUES (?, ?, ?)', (user_id, state, data))
    conn.commit()
    conn.close()

def get_user_state(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT state, data FROM user_states WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return {'state': result[0], 'data': result[1]} if result else None

def clear_user_state(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM user_states WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def save_user(user_id: int, name: str, phone: str, language: str, country: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO users (user_id, name, phone, language, country, last_active)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    ''', (user_id, name, phone, language, country))
    conn.commit()
    conn.close()
    
    print(f"✅ User registered: {name} ({user_id}) from {country}")

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

def update_user_activity(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET last_active = CURRENT_TIMESTAMP WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

# ========== CONVERSATION STATES ==========
PHONE, LANGUAGE, COUNTRY = range(3)

# ========== COUNTRY & LANGUAGE DATA ==========
COUNTRIES = {
    'ENG': '🇬🇧 United Kingdom',
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
    'ENG': '🇬🇧 English',
    'RU': '🇷🇺 Русский',
    'BD': '🇧🇩 বাংলা',
    'IN': '🇮🇳 हिंदी',
    'PK': '🇵🇰 اردو',
    'PH': '🇵🇭 Filipino',
    'LK': '🇱🇰 සිංහල',
    'MY': '🇲🇾 Bahasa Malaysia',
    'TH': '🇹🇭 ไทย',
    'NG': '🇳🇬 English',
    'TR': '🇹🇷 Türkçe',
    'KE': '🇰🇪 English'
}

# Country-based offers
COUNTRY_OFFERS = {
    'ENG': "🇬🇧 **UK AFFILIATE PROGRAM**\n\n• Commission: 30%\n• Min Deposit: £50\n• Daily Payout\n• Support: 24/7 UK Team",
    'RU': "🇷🇺 **РОССИЙСКАЯ ПАРТНЕРСКАЯ ПРОГРАММА**\n\n• Комиссия: 30%\n• Мин. депозит: 5000₽\n• Выплаты ежедневно\n• Поддержка 24/7",
    'BD': "🇧🇩 **বাংলাদেশ অ্যাফিলিয়েট প্রোগ্রাম**\n\n• কমিশন: ২৫%\n• ন্যূনতম ডিপোজিট: ৫০০০৳\n• দৈনিক পেমেন্ট\n• ২৪/৭ সাপোর্ট",
    'IN': "🇮🇳 **भारतीय सहबद्ध कार्यक्रम**\n\n• कमीशन: 25%\n• न्यूनतम जमा: ₹5000\n• दैनिक भुगतान\n• 24/7 समर्थन",
    'PK': "🇵🇰 **پاکستان ایفلی ایٹ پروگرام**\n\n• کمیشن: 25%\n• کم از کم ڈپازٹ: 5000 روپے\n• روزانہ ادائیگی\n• 24/7 سپورٹ",
    'PH': "🇵🇭 **PHILIPPINES AFFILIATE PROGRAM**\n\n• Commission: 25%\n• Min Deposit: ₱3000\n• Daily Payout\n• 24/7 Support",
    'LK': "🇱🇰 **ශ්‍රී ලංකා සහකරු වැඩසටහන**\n\n• කොමිස්: 25%\n• අවම තැන්පතු: රු.5000\n• දිනපතා ගෙවීම්\n• 24/7 සහාය",
    'MY': "🇲🇾 **PROGRAM AFFILIASI MALAYSIA**\n\n• Komisen: 25%\n• Deposit Min: RM300\n• Bayaran Harian\n• Sokongan 24/7",
    'TH': "🇹🇭 **โปรแกรมพันธมิตรไทย**\n\n• คอมมิชชั่น: 25%\n• เงินฝากขั้นต่ำ: 1500฿\n• การจ่ายเงินรายวัน\n• สนับสนุน 24/7",
    'NG': "🇳🇬 **NIGERIA AFFILIATE PROGRAM**\n\n• Commission: 30%\n• Min Deposit: ₦20,000\n• Daily Payout\n• 24/7 Support",
    'TR': "🇹🇷 **TÜRKİYE ORTAKLIK PROGRAMI**\n\n• Komisyon: 30%\n• Min Deposit: 1000₺\n• Günlük Ödeme\n• 7/24 Destek",
    'KE': "🇰🇪 **KENYA AFFILIATE PROGRAM**\n\n• Commission: 30%\n• Min Deposit: KSh 5,000\n• Daily Payout\n• 24/7 Support"
}

# ========== KEYBOARDS ==========
def get_phone_keyboard():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📞 Share Contact", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_language_keyboard():
    buttons = []
    for lang_code, lang_name in LANGUAGES.items():
        buttons.append([InlineKeyboardButton(lang_name, callback_data=f"lang_{lang_code}")])
    return InlineKeyboardMarkup(buttons)

def get_country_keyboard():
    buttons = []
    for country_code, country_name in COUNTRIES.items():
        buttons.append([InlineKeyboardButton(country_name, callback_data=f"country_{country_code}")])
    return InlineKeyboardMarkup(buttons)

def get_main_menu_keyboard():
    """Main menu with persistent buttons"""
    return ReplyKeyboardMarkup(
        [
            ["📞 Contact Local Manager"],
            ["ℹ️ About Program", "🔄 Restart"]
        ],
        resize_keyboard=True
    )

# ========== HANDLERS ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.full_name
    
    print(f"🚀 /start from {user_id} ({user_name})")
    
    existing_user = get_user(user_id)
    if existing_user:
        # Show menu immediately for existing users
        await update.message.reply_text(
            f"👋 Welcome back {user_name}!\n"
            "Use the menu below:",
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END
    
    # New user flow
    await update.message.reply_text(
        f"👋 Hello {user_name}!\n\n"
        "Welcome to **Affiliate Support Bot**!\n\n"
        "To access our affiliate program, please share your phone number:",
        reply_markup=get_phone_keyboard()
    )
    
    save_user_state(user_id, 'phone')
    return PHONE

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if update.message.contact:
        phone = update.message.contact.phone_number
        name = update.message.contact.first_name
        
        print(f"📱 Contact received: {name} - {phone}")
        
        save_user_state(user_id, 'language', f"{name}|{phone}")
        
        await update.message.reply_text(
            "✅ Phone number verified!\n\n"
            "Please select your preferred language:",
            reply_markup=get_language_keyboard()
        )
        return LANGUAGE
    
    await update.message.reply_text(
        "⚠️ Please use the 'Share Contact' button to continue.",
        reply_markup=get_phone_keyboard()
    )
    return PHONE

async def handle_language_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    language_code = query.data.replace('lang_', '')
    
    state = get_user_state(user_id)
    if not state:
        await query.edit_message_text("Session expired. Please send /start again.")
        return ConversationHandler.END
    
    name, phone = state['data'].split('|')
    save_user_state(user_id, 'country', f"{name}|{phone}|{language_code}")
    
    await query.edit_message_text(
        f"✅ Language selected: {LANGUAGES[language_code]}\n\n"
        "Now select your country:",
        reply_markup=get_country_keyboard()
    )
    return COUNTRY

async def handle_country_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    country_code = query.data.replace('country_', '')
    
    state = get_user_state(user_id)
    if not state:
        await query.edit_message_text("Session expired. Please send /start again.")
        return ConversationHandler.END
    
    name, phone, language_code = state['data'].split('|')
    
    # Save user to database
    save_user(user_id, name, phone, language_code, country_code)
    clear_user_state(user_id)
    
    # Get country-specific offer
    offer = COUNTRY_OFFERS.get(country_code, "Welcome to our affiliate program!")
    
    # Send registration success message
    await query.edit_message_text(
        f"🎉 **REGISTRATION SUCCESSFUL!**\n\n"
        f"✅ Account Created\n"
        f"👤 Name: {name}\n"
        f"🌍 Country: {COUNTRIES[country_code]}\n"
        f"🗣️ Language: {LANGUAGES[language_code]}\n\n"
        f"{offer}\n\n"
        f"👇 Use the menu below to get started:"
    )
    
    # NOTIFY ADMINS ABOUT NEW USER
    await notify_admins(context.application, user_id, name, phone, language_code, country_code)
    
    # Show main menu
    await show_main_menu(update, context)
    
    return ConversationHandler.END

async def notify_admins(application, user_id: int, name: str, phone: str, language: str, country: str):
    """Send notification to all admins about new user"""
    message = (
        "🆕 **NEW USER REGISTERED**\n\n"
        f"👤 Name: {name}\n"
        f"📱 Phone: {phone}\n"
        f"🌍 Country: {COUNTRIES.get(country, country)}\n"
        f"🗣️ Language: {LANGUAGES.get(language, language)}\n"
        f"🆔 User ID: `{user_id}`\n"
        f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    
    for admin_id in ADMIN_IDS:
        try:
            await application.bot.send_message(
                chat_id=admin_id,
                text=message,
                parse_mode='Markdown'
            )
            print(f"✅ Notified admin {admin_id} about new user")
        except Exception as e:
            print(f"❌ Failed to notify admin {admin_id}: {e}")

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show main menu"""
    keyboard = get_main_menu_keyboard()
    
    if update.callback_query:
        await update.callback_query.message.reply_text(
            "🎯 **MAIN MENU**\nSelect an option:",
            reply_markup=keyboard
        )
    else:
        await update.message.reply_text(
            "🎯 **MAIN MENU**\nSelect an option:",
            reply_markup=keyboard
        )

async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle main menu selections"""
    text = update.message.text
    user_id = update.effective_user.id
    
    # Update user activity
    update_user_activity(user_id)
    
    if text == "📞 Contact Local Manager":
        user = get_user(user_id)
        if user:
            country = user.get('country', 'ENG')
            country_name = COUNTRIES.get(country, 'Your Country')
            
            await update.message.reply_text(
                f"📞 **Contact Local Manager**\n\n"
                f"📍 Region: {country_name}\n\n"
                f"Please contact our local manager for personalized support:\n"
                f"👉 @SupportManager_{country}\n\n"
                f"*Note: Contact your manager directly on Telegram*"
            )
        else:
            await update.message.reply_text("Please register first with /start")
    
    elif text == "ℹ️ About Program":
        # Show program details automatically
        await show_program_details(update, context)
    
    elif text == "🔄 Restart":
        await start(update, context)

async def show_program_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show affiliate program details"""
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    if user:
        country = user.get('country', 'ENG')
        offer = COUNTRY_OFFERS.get(country, COUNTRY_OFFERS['ENG'])
        
        await update.message.reply_text(
            f"📊 **AFFILIATE PROGRAM DETAILS**\n\n"
            f"{offer}\n\n"
            f"💡 **General Features:**\n"
            f"• Real-time tracking dashboard\n"
            f"• Marketing materials provided\n"
            f"• Dedicated support team\n"
            f"• Weekly training sessions\n"
            f"• Performance bonuses\n\n"
            f"📞 Contact your local manager to get started!"
        )
    else:
        await update.message.reply_text(
            "📊 **AFFILIATE PROGRAM**\n\n"
            "Join our global affiliate network!\n\n"
            "• Commission: 20-30%\n"
            "• Daily payments\n"
            "• Marketing tools provided\n"
            "• 24/7 support\n\n"
            "Register with /start to see country-specific offers!"
        )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel conversation"""
    user_id = update.effective_user.id
    clear_user_state(user_id)
    await update.message.reply_text("Registration cancelled. Use /start to begin.")
    return ConversationHandler.END

# ========== ADMIN HANDLERS ==========
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Access denied. You are not an admin.")
        return
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Broadcast to All", callback_data="broadcast_all")],
        [InlineKeyboardButton("🌍 Broadcast by Country", callback_data="broadcast_country")],
        [InlineKeyboardButton("👤 Send to Specific User", callback_data="send_specific")],
        [InlineKeyboardButton("📊 User Statistics", callback_data="user_stats")],
        [InlineKeyboardButton("👥 User List", callback_data="user_list")]
    ])
    
    total_users = get_total_users()
    
    await update.message.reply_text(
        f"🔧 **ADMIN PANEL**\n\n"
        f"Welcome, Admin {user_id}!\n"
        f"Total Users: {total_users}\n\n"
        f"Select an action:",
        reply_markup=keyboard
    )

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await query.edit_message_text("❌ Access denied.")
        return
    
    if query.data == "user_stats":
        total = get_total_users()
        users = get_all_users()
        
        # Count by country
        country_stats = {}
        for user in users:
            country = user.get('country', 'Unknown')
            country_stats[country] = country_stats.get(country, 0) + 1
        
        stats_text = "📊 **USER STATISTICS**\n\n"
        stats_text += f"👥 Total Users: {total}\n\n"
        stats_text += "🌍 **By Country:**\n"
        for country, count in sorted(country_stats.items(), key=lambda x: x[1], reverse=True):
            country_name = COUNTRIES.get(country, country)
            stats_text += f"• {country_name}: {count}\n"
        
        await query.edit_message_text(stats_text)
    
    elif query.data == "user_list":
        users = get_all_users()
        if not users:
            await query.edit_message_text("No users registered yet.")
            return
        
        message = "📋 **RECENT USERS**\n\n"
        for i, user in enumerate(users[:10], 1):
            country = COUNTRIES.get(user.get('country', 'Unknown'), user.get('country', 'Unknown'))
            message += f"{i}. {user['name']} - {country}\n   📱 {user.get('phone', 'N/A')}\n   🆔 `{user['user_id']}`\n\n"
        
        if len(users) > 10:
            message += f"📄 ... and {len(users)-10} more users"
        
        await query.edit_message_text(message)
    
    elif query.data == "broadcast_all":
        context.user_data['broadcast_type'] = 'all'
        await query.edit_message_text(
            "📢 **BROADCAST TO ALL USERS**\n\n"
            "Send the message you want to broadcast to ALL users.\n"
            "You can send text, photo, or document.\n\n"
            "Type /cancel to abort."
        )
    
    elif query.data == "broadcast_country":
        # Show country selection for broadcast
        buttons = []
        for country_code, country_name in COUNTRIES.items():
            buttons.append([InlineKeyboardButton(country_name, callback_data=f"select_country_{country_code}")])
        buttons.append([InlineKeyboardButton("◀️ Back", callback_data="back_to_admin")])
        
        await query.edit_message_text(
            "🌍 **SELECT COUNTRY FOR BROADCAST**\n\n"
            "Choose which country to send message to:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    
    elif query.data == "send_specific":
        context.user_data['awaiting_user_id'] = True
        await query.edit_message_text(
            "👤 **SEND TO SPECIFIC USER**\n\n"
            "Please send the User ID first:\n"
            "(You can get User IDs from User List)\n\n"
            "Type /cancel to abort."
        )
    
    elif query.data.startswith("select_country_"):
        country_code = query.data.replace("select_country_", "")
        country_name = COUNTRIES.get(country_code, country_code)
        context.user_data['broadcast_type'] = 'country'
        context.user_data['broadcast_country'] = country_code
        
        await query.edit_message_text(
            f"🌍 **BROADCAST TO {country_name}**\n\n"
            f"Send the message you want to broadcast to users from {country_name}.\n\n"
            "Type /cancel to abort."
        )
    
    elif query.data == "back_to_admin":
        await admin_panel(update, context)

async def handle_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin messages (broadcasts, etc.)"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        return
    
    # Handle specific user ID input
    if context.user_data.get('awaiting_user_id'):
        try:
            target_user_id = int(update.message.text)
            context.user_data['target_user_id'] = target_user_id
            context.user_data['awaiting_user_id'] = False
            context.user_data['awaiting_specific_message'] = True
            
            await update.message.reply_text(
                f"✅ Target User ID: {target_user_id}\n\n"
                "Now send the message for this user:\n\n"
                "Type /cancel to abort."
            )
            return
        except ValueError:
            await update.message.reply_text("Invalid User ID. Please send a numeric ID.")
            return
    
    # Handle message for specific user
    if context.user_data.get('awaiting_specific_message'):
        target_user_id = context.user_data.get('target_user_id')
        try:
            await context.bot.copy_message(
                chat_id=target_user_id,
                from_chat_id=update.effective_chat.id,
                message_id=update.message.message_id
            )
            await update.message.reply_text(f"✅ Message sent to user {target_user_id}")
            
            # Clear state
            context.user_data.pop('awaiting_specific_message', None)
            context.user_data.pop('target_user_id', None)
        except Exception as e:
            await update.message.reply_text(f"❌ Failed to send: {str(e)}")
        return
    
    # Handle broadcast
    broadcast_type = context.user_data.get('broadcast_type')
    
    if broadcast_type in ['all', 'country']:
        users = get_all_users()
        
        if broadcast_type == 'country':
            country_code = context.user_data.get('broadcast_country')
            users = [u for u in users if u.get('country') == country_code]
            country_name = COUNTRIES.get(country_code, country_code)
        
        total = len(users)
        if total == 0:
            await update.message.reply_text("❌ No users found for this selection.")
            context.user_data.pop('broadcast_type', None)
            return
        
        # Ask for confirmation
        confirm_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Yes, Send Now", callback_data="confirm_send")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel_send")]
        ])
        
        context.user_data['broadcast_message'] = update.message
        context.user_data['broadcast_users'] = users
        
        target = "ALL users" if broadcast_type == 'all' else f"users from {country_name}"
        
        await update.message.reply_text(
            f"📢 **CONFIRM BROADCAST**\n\n"
            f"Send this message to {target}?\n"
            f"• Total recipients: {total}\n\n"
            f"**Message Preview:**\n"
            f"{update.message.text[:100] if update.message.text else 'Media message'}...\n\n"
            f"Click ✅ to confirm or ❌ to cancel:",
            reply_markup=confirm_keyboard
        )
        return

async def handle_broadcast_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle broadcast confirmation"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return
    
    if query.data == "confirm_send":
        broadcast_message = context.user_data.get('broadcast_message')
        users = context.user_data.get('broadcast_users', [])
        
        total = len(users)
        successful = 0
        failed = 0
        
        # Send progress message
        progress_msg = await query.message.reply_text(f"📤 Sending... 0/{total}")
        
        for i, user in enumerate(users, 1):
            try:
                await context.bot.copy_message(
                    chat_id=user['user_id'],
                    from_chat_id=broadcast_message.chat_id,
                    message_id=broadcast_message.message_id
                )
                successful += 1
                
                # Update progress every 10 messages
                if i % 10 == 0 or i == total:
                    await progress_msg.edit_text(f"📤 Sending... {i}/{total}")
            except Exception as e:
                failed += 1
                logger.error(f"Failed to send to user {user['user_id']}: {e}")
        
        # Send completion report
        report = (
            f"✅ **BROADCAST COMPLETE**\n\n"
            f"📊 Results:\n"
            f"• Total recipients: {total}\n"
            f"• Successfully sent: {successful}\n"
            f"• Failed: {failed}\n"
            f"• Success rate: {(successful/total*100):.1f}%"
        )
        
        await progress_msg.edit_text(report)
        
        # Clear broadcast data
        context.user_data.pop('broadcast_type', None)
        context.user_data.pop('broadcast_message', None)
        context.user_data.pop('broadcast_users', None)
        context.user_data.pop('broadcast_country', None)
    
    elif query.data == "cancel_send":
        await query.message.edit_text("❌ Broadcast cancelled.")
        
        # Clear broadcast data
        context.user_data.pop('broadcast_type', None)
        context.user_data.pop('broadcast_message', None)
        context.user_data.pop('broadcast_users', None)
        context.user_data.pop('broadcast_country', None)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {context.error}")
    try:
        if update and update.effective_user:
            await context.bot.send_message(
                chat_id=update.effective_user.id,
                text="❌ An error occurred. Please try again."
            )
    except:
        pass

# ========== MAIN FUNCTION ==========
def main():
    """Start the bot"""
    print("=" * 50)
    print("🤖 AFFILIATE SUPPORT BOT - STARTING")
    print("=" * 50)
    print(f"🔑 Token: {TOKEN[:10]}...")
    print(f"👑 Admin IDs: {ADMIN_IDS}")
    print(f"💾 Database: {DB_PATH}")
    print("=" * 50)
    
    # Initialize database
    init_db()
    
    # Create application
    application = Application.builder().token(TOKEN).build()
    
    # Add conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            PHONE: [MessageHandler(filters.CONTACT, handle_contact)],
            LANGUAGE: [CallbackQueryHandler(handle_language_selection, pattern='^lang_')],
            COUNTRY: [CallbackQueryHandler(handle_country_selection, pattern='^country_')]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    # Add all handlers
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('admin', admin_panel))
    application.add_handler(CallbackQueryHandler(admin_callback, pattern='^broadcast_|^send_|^user_|^select_|^back_'))
    application.add_handler(CallbackQueryHandler(handle_broadcast_confirmation, pattern='^confirm_|^cancel_'))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_main_menu))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_admin_message))
    application.add_error_handler(error_handler)
    
    # Start bot
    print("🔄 Starting bot polling...")
    print("✅ Bot is RUNNING!")
    print("📱 Test with: /start")
    print("👑 Admin panel: /admin")
    print("=" * 50 + "\n")
    
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )

if __name__ == '__main__':
    main()
