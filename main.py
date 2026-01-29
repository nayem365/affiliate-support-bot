import os
import sys
import logging
import sqlite3
from datetime import datetime, timedelta
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
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS broadcasts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER,
            target_type TEXT,
            target_id TEXT,
            message_type TEXT,
            content TEXT,
            sent_count INTEGER,
            failed_count INTEGER,
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

def get_users_by_country(country_code: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE country = ? ORDER BY registered_at DESC', (country_code,))
    columns = [description[0] for description in cursor.description]
    results = cursor.fetchall()
    conn.close()
    return [dict(zip(columns, row)) for row in results]

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

def save_broadcast(admin_id: int, target_type: str, target_id: str, message_type: str, content: str, sent_count: int, failed_count: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO broadcasts (admin_id, target_type, target_id, message_type, content, sent_count, failed_count)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (admin_id, target_type, target_id, message_type, content, sent_count, failed_count))
    conn.commit()
    conn.close()

# ========== CONVERSATION STATES ==========
PHONE, LANGUAGE, COUNTRY = range(3)
ADMIN_BROADCAST, ADMIN_SPECIFIC_USER = range(2)

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
    'PK': "🇵🇰 **पाकिस्तान एफिलिएट प्रोग्राम**\n\n• कमीशन: 25%\n• न्यूनतम जमा: 5000 रुपए\n• दैनिक भुगतान\n• 24/7 समर्थन",
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
    """Create language keyboard with 3 buttons per row (4 rows total)"""
    buttons = []
    lang_items = list(LANGUAGES.items())
    
    # Split into chunks of 3 for 4 rows (12 items total)
    for i in range(0, len(lang_items), 3):
        row = []
        for lang_code, lang_name in lang_items[i:i+3]:
            row.append(InlineKeyboardButton(lang_name, callback_data=f"lang_{lang_code}"))
        buttons.append(row)
    
    return InlineKeyboardMarkup(buttons)

def get_country_keyboard():
    """Create country keyboard with 3 buttons per row (4 rows total)"""
    buttons = []
    country_items = list(COUNTRIES.items())
    
    # Split into chunks of 3 for 4 rows (12 items total)
    for i in range(0, len(country_items), 3):
        row = []
        for country_code, country_name in country_items[i:i+3]:
            row.append(InlineKeyboardButton(country_name, callback_data=f"country_{country_code}"))
        buttons.append(row)
    
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

def get_admin_keyboard():
    """Admin menu keyboard"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Send Message to All Users", callback_data="broadcast_all")],
        [InlineKeyboardButton("👤 Send Message to Specific User", callback_data="send_specific")],
        [InlineKeyboardButton("🌍 Send Message by Country", callback_data="broadcast_country")],
        [InlineKeyboardButton("📊 View Statistics", callback_data="view_stats")],
        [InlineKeyboardButton("👥 View User List", callback_data="view_users")],
        [InlineKeyboardButton("❌ Close Admin Panel", callback_data="close_admin")]
    ])

def get_country_selection_keyboard():
    """Country selection keyboard for broadcast"""
    buttons = []
    country_items = list(COUNTRIES.items())
    
    # Split into chunks of 3 for 4 rows (12 items total)
    for i in range(0, len(country_items), 3):
        row = []
        for country_code, country_name in country_items[i:i+3]:
            row.append(InlineKeyboardButton(country_name, callback_data=f"bcast_country_{country_code}"))
        buttons.append(row)
    
    # Add back button
    buttons.append([InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="back_to_admin")])
    
    return InlineKeyboardMarkup(buttons)

def get_broadcast_confirm_keyboard():
    """Broadcast confirmation keyboard"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Yes, Send Now", callback_data="confirm_send"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel_send")
        ]
    ])

def get_specific_user_confirm_keyboard():
    """Specific user confirmation keyboard"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Yes, Send to This User", callback_data="confirm_specific"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel_specific")
        ]
    ])

def get_country_broadcast_confirm_keyboard():
    """Country broadcast confirmation keyboard"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Yes, Send to This Country", callback_data="confirm_country"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel_country")
        ]
    ])

# ========== HANDLERS ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.full_name
    
    print(f"🚀 /start from {user_id} ({user_name})")
    
    # Check if admin
    if user_id in ADMIN_IDS:
        await update.message.reply_text(
            f"👑 Welcome Admin {user_name}!\n"
            f"Use /admin to access admin panel.",
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END
    
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
    
    # Clear any admin states
    if context.user_data.get('admin_mode'):
        context.user_data.clear()
    
    await update.message.reply_text("Operation cancelled. Use /start to begin or /admin for admin panel.")
    return ConversationHandler.END

# ========== ADMIN HANDLERS ==========
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Access denied. You are not an admin.")
        return
    
    # Clear any previous states
    context.user_data.clear()
    context.user_data['admin_mode'] = True
    
    total_users = get_total_users()
    
    await update.message.reply_text(
        f"👑 **ADMIN PANEL**\n\n"
        f"Welcome, Admin {user_id}!\n"
        f"Total Users: {total_users}\n\n"
        f"Select an option:",
        reply_markup=get_admin_keyboard()
    )
    return ConversationHandler.END

async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin callback queries"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await query.edit_message_text("❌ Access denied.")
        return
    
    if query.data == "broadcast_all":
        # Set state for broadcast to all users
        context.user_data['awaiting_message'] = True
        context.user_data['broadcast_type'] = 'all'
        
        await query.edit_message_text(
            "📢 **SEND MESSAGE TO ALL USERS**\n\n"
            "Please send the message you want to broadcast to ALL registered users.\n\n"
            "You can send:\n"
            "• Text message\n"
            "• Photo with caption\n"
            "• Video with caption\n"
            "• Document\n\n"
            "To cancel, send /cancel"
        )
    
    elif query.data == "send_specific":
        # Set state for specific user
        context.user_data['awaiting_user_id'] = True
        context.user_data['broadcast_type'] = 'specific'
        
        await query.edit_message_text(
            "👤 **SEND MESSAGE TO SPECIFIC USER**\n\n"
            "Please send the User ID first:\n"
            "(Get User IDs from 'View User List' option)\n\n"
            "To cancel, send /cancel"
        )
    
    elif query.data == "broadcast_country":
        # Set state for country selection
        context.user_data['awaiting_country'] = True
        context.user_data['broadcast_type'] = 'country'
        
        await query.edit_message_text(
            "🌍 **SEND MESSAGE BY COUNTRY**\n\n"
            "Select the country you want to send message to:",
            reply_markup=get_country_selection_keyboard()
        )
    
    elif query.data.startswith("bcast_country_"):
        # Country selected for broadcast
        country_code = query.data.replace('bcast_country_', '')
        country_name = COUNTRIES.get(country_code, country_code)
        
        context.user_data['selected_country'] = country_code
        context.user_data['selected_country_name'] = country_name
        context.user_data['awaiting_country'] = False
        context.user_data['awaiting_message'] = True
        
        # Get number of users in this country
        users_in_country = get_users_by_country(country_code)
        user_count = len(users_in_country)
        
        await query.edit_message_text(
            f"✅ Country selected: {country_name}\n"
            f"👥 Users in this country: {user_count}\n\n"
            "Now send the message you want to broadcast to users in this country:\n\n"
            "You can send:\n"
            "• Text message\n"
            "• Photo with caption\n"
            "• Video with caption\n"
            "• Document\n\n"
            "To cancel, send /cancel"
        )
    
    elif query.data == "view_stats":
        total = get_total_users()
        users = get_all_users()
        
        # Count by country
        country_stats = {}
        for user in users:
            country = user.get('country', 'Unknown')
            country_stats[country] = country_stats.get(country, 0) + 1
        
        # Calculate active users (last 24 hours)
        active_users = 0
        day_ago = datetime.now() - timedelta(hours=24)
        
        stats_text = "📊 **USER STATISTICS**\n\n"
        stats_text += f"👥 Total Users: {total}\n"
        
        if total > 0:
            # Count users by registration date (last 7 days)
            week_ago = datetime.now() - timedelta(days=7)
            new_users = 0
            
            stats_text += f"📈 Active (last 24h): {active_users}\n"
            stats_text += f"🆕 New (last 7 days): {new_users}\n\n"
            stats_text += "🌍 **Users by Country:**\n"
            for country, count in sorted(country_stats.items(), key=lambda x: x[1], reverse=True):
                country_name = COUNTRIES.get(country, country)
                percentage = (count / total) * 100
                stats_text += f"• {country_name}: {count} ({percentage:.1f}%)\n"
        else:
            stats_text += "\nNo users registered yet."
        
        # Add back button
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="back_to_admin")]
        ])
        
        await query.edit_message_text(stats_text, reply_markup=keyboard)
    
    elif query.data == "view_users":
        users = get_all_users()
        if not users:
            await query.edit_message_text("📋 No users registered yet.")
            return
        
        # Show first 10 users
        message = "📋 **REGISTERED USERS**\n\n"
        for i, user in enumerate(users[:10], 1):
            country = COUNTRIES.get(user.get('country', 'Unknown'), user.get('country', 'Unknown'))
            reg_date = datetime.strptime(user['registered_at'], '%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y')
            message += f"{i}. **{user['name']}**\n"
            message += f"   🆔 `{user['user_id']}`\n"
            message += f"   🌍 {country}\n"
            message += f"   📱 {user.get('phone', 'N/A')}\n"
            message += f"   📅 Registered: {reg_date}\n\n"
        
        if len(users) > 10:
            message += f"📄 ... and {len(users)-10} more users"
        
        # Add back button
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="back_to_admin")]
        ])
        
        await query.edit_message_text(message, reply_markup=keyboard)
    
    elif query.data == "close_admin":
        context.user_data.clear()
        await query.edit_message_text("✅ Admin panel closed.")
        await show_main_menu(update, context)
    
    elif query.data == "back_to_admin":
        total_users = get_total_users()
        
        await query.edit_message_text(
            f"👑 **ADMIN PANEL**\n\n"
            f"Welcome, Admin {user_id}!\n"
            f"Total Users: {total_users}\n\n"
            f"Select an option:",
            reply_markup=get_admin_keyboard()
        )

async def handle_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin messages for broadcast"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        return
    
    # Skip if message is a command
    if update.message.text and update.message.text.startswith('/'):
        return
    
    # Handle user ID input for specific user - FIXED
    if context.user_data.get('awaiting_user_id'):
        try:
            # Extract the first number from the message
            text = update.message.text.strip()
            
            # Try to find a number in the text
            import re
            numbers = re.findall(r'\d+', text)
            
            if not numbers:
                await update.message.reply_text(
                    "❌ No valid User ID found in your message.\n"
                    "Please send only the numeric User ID (e.g., 123456789)\n"
                    "or /cancel to cancel."
                )
                return
            
            target_user_id = int(numbers[0])
            
            # Check if user exists
            user = get_user(target_user_id)
            if not user:
                await update.message.reply_text(
                    f"❌ User ID {target_user_id} not found in database.\n"
                    f"Please send a valid User ID or /cancel"
                )
                return
            
            context.user_data['target_user_id'] = target_user_id
            context.user_data['target_user_name'] = user['name']
            context.user_data['awaiting_user_id'] = False
            context.user_data['awaiting_message'] = True
            
            await update.message.reply_text(
                f"✅ User found: {user['name']} (ID: {target_user_id})\n\n"
                "Now send the message for this user:\n\n"
                "To cancel, send /cancel"
            )
            return
        except ValueError as e:
            await update.message.reply_text(
                f"❌ Invalid input. Please send only the numeric User ID (e.g., 123456789)\n"
                f"Error: {str(e)}\n\n"
                f"To cancel, send /cancel"
            )
            return
    
    # Handle message input for broadcast
    if context.user_data.get('awaiting_message'):
        broadcast_type = context.user_data.get('broadcast_type')
        
        if broadcast_type == 'all':
            # Broadcast to all users
            users = get_all_users()
            total_users = len(users)
            
            if total_users == 0:
                await update.message.reply_text("❌ No users to broadcast to.")
                context.user_data.clear()
                return
            
            # Store message for confirmation
            context.user_data['broadcast_message'] = update.message
            context.user_data['total_users'] = total_users
            
            # Extract message text for preview
            message_text = ""
            if update.message.text:
                message_text = update.message.text[:200]
            elif update.message.caption:
                message_text = update.message.caption[:200]
            elif update.message.photo:
                message_text = "📷 Photo message"
            elif update.message.video:
                message_text = "🎥 Video message"
            elif update.message.document:
                message_text = "📄 Document"
            else:
                message_text = "Media message"
            
            await update.message.reply_text(
                f"⚠️ **CONFIRM BROADCAST**\n\n"
                f"Send this message to ALL {total_users} users?\n\n"
                f"**Message Preview:**\n"
                f"{message_text}...\n\n"
                f"This action cannot be undone!",
                reply_markup=get_broadcast_confirm_keyboard()
            )
            
        elif broadcast_type == 'specific':
            # Send to specific user
            target_user_id = context.user_data.get('target_user_id')
            target_user_name = context.user_data.get('target_user_name', 'User')
            
            if not target_user_id:
                await update.message.reply_text("❌ User ID not found. Please start over.")
                context.user_data.clear()
                return
            
            # Store message for confirmation
            context.user_data['broadcast_message'] = update.message
            
            # Extract message text for preview
            message_text = ""
            if update.message.text:
                message_text = update.message.text[:200]
            elif update.message.caption:
                message_text = update.message.caption[:200]
            elif update.message.photo:
                message_text = "📷 Photo message"
            elif update.message.video:
                message_text = "🎥 Video message"
            elif update.message.document:
                message_text = "📄 Document"
            else:
                message_text = "Media message"
            
            await update.message.reply_text(
                f"⚠️ **CONFIRM SEND**\n\n"
                f"Send this message to {target_user_name} (ID: {target_user_id})?\n\n"
                f"**Message Preview:**\n"
                f"{message_text}...",
                reply_markup=get_specific_user_confirm_keyboard()
            )
        
        elif broadcast_type == 'country':
            # Send to specific country
            country_code = context.user_data.get('selected_country')
            country_name = context.user_data.get('selected_country_name', 'Unknown')
            
            if not country_code:
                await update.message.reply_text("❌ Country not selected. Please start over.")
                context.user_data.clear()
                return
            
            # Get users in this country
            users = get_users_by_country(country_code)
            total_users = len(users)
            
            if total_users == 0:
                await update.message.reply_text(
                    f"❌ No users found in {country_name}.\n"
                    f"Please select another country or cancel."
                )
                context.user_data.clear()
                return
            
            # Store message for confirmation
            context.user_data['broadcast_message'] = update.message
            context.user_data['country_users_count'] = total_users
            
            # Extract message text for preview
            message_text = ""
            if update.message.text:
                message_text = update.message.text[:200]
            elif update.message.caption:
                message_text = update.message.caption[:200]
            elif update.message.photo:
                message_text = "📷 Photo message"
            elif update.message.video:
                message_text = "🎥 Video message"
            elif update.message.document:
                message_text = "📄 Document"
            else:
                message_text = "Media message"
            
            await update.message.reply_text(
                f"⚠️ **CONFIRM COUNTRY BROADCAST**\n\n"
                f"Send this message to {total_users} users in {country_name}?\n\n"
                f"**Message Preview:**\n"
                f"{message_text}...\n\n"
                f"This action cannot be undone!",
                reply_markup=get_country_broadcast_confirm_keyboard()
            )
        
        return
    
    # If not in any admin mode, show admin panel
    await admin_panel(update, context)

async def handle_broadcast_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle broadcast confirmation"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return
    
    if query.data == "confirm_send":
        # Broadcast to all users
        broadcast_message = context.user_data.get('broadcast_message')
        users = get_all_users()
        
        if not broadcast_message or not users:
            await query.edit_message_text("❌ Broadcast data not found.")
            return
        
        total = len(users)
        successful = 0
        failed = 0
        
        # Send initial progress message
        progress_msg = await query.message.reply_text(f"📤 Starting broadcast...\n0/{total} (0%)")
        
        for i, user in enumerate(users, 1):
            try:
                await context.bot.copy_message(
                    chat_id=user['user_id'],
                    from_chat_id=broadcast_message.chat_id,
                    message_id=broadcast_message.message_id
                )
                successful += 1
                
                # Update progress every 5 messages or at the end
                if i % 5 == 0 or i == total:
                    percentage = (i / total) * 100
                    await progress_msg.edit_text(
                        f"📤 Broadcasting...\n"
                        f"{i}/{total} ({percentage:.1f}%)\n"
                        f"✅ {successful} successful"
                    )
                    
            except Exception as e:
                failed += 1
                logger.error(f"Failed to send to user {user['user_id']}: {e}")
        
        # Save broadcast record
        content_preview = ""
        if broadcast_message.text:
            content_preview = broadcast_message.text[:100]
        elif broadcast_message.caption:
            content_preview = broadcast_message.caption[:100]
        else:
            content_preview = "Media message"
            
        save_broadcast(
            admin_id=user_id,
            target_type='all',
            target_id='all',
            message_type='broadcast',
            content=content_preview,
            sent_count=successful,
            failed_count=failed
        )
        
        # Send final report
        report = (
            f"✅ **BROADCAST COMPLETED**\n\n"
            f"📊 **Results:**\n"
            f"• Total users: {total}\n"
            f"• Successfully sent: {successful}\n"
            f"• Failed: {failed}\n"
            f"• Success rate: {(successful/total*100):.1f}%\n\n"
            f"📝 Message preview saved in database."
        )
        
        # Add back to admin button
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="back_to_admin")]
        ])
        
        await progress_msg.edit_text(report, reply_markup=keyboard)
        await query.message.delete()
        
        # Clear broadcast data
        context.user_data.clear()
    
    elif query.data == "confirm_specific":
        # Send to specific user
        broadcast_message = context.user_data.get('broadcast_message')
        target_user_id = context.user_data.get('target_user_id')
        target_user_name = context.user_data.get('target_user_name', 'User')
        
        if not broadcast_message or not target_user_id:
            await query.edit_message_text("❌ User data not found.")
            return
        
        try:
            # Send message to specific user
            await context.bot.copy_message(
                chat_id=target_user_id,
                from_chat_id=broadcast_message.chat_id,
                message_id=broadcast_message.message_id
            )
            
            # Save record
            content_preview = ""
            if broadcast_message.text:
                content_preview = broadcast_message.text[:100]
            elif broadcast_message.caption:
                content_preview = broadcast_message.caption[:100]
            else:
                content_preview = "Media message"
                
            save_broadcast(
                admin_id=user_id,
                target_type='specific',
                target_id=str(target_user_id),
                message_type='direct',
                content=content_preview,
                sent_count=1,
                failed_count=0
            )
            
            await query.edit_message_text(
                f"✅ **MESSAGE SENT SUCCESSFULLY**\n\n"
                f"To: {target_user_name} (ID: {target_user_id})\n\n"
                f"Message preview saved in database."
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ **FAILED TO SEND MESSAGE**\n\n"
                f"Error: {str(e)}\n\n"
                f"The user may have blocked the bot."
            )
        
        # Clear data
        context.user_data.clear()
    
    elif query.data == "confirm_country":
        # Broadcast to specific country
        broadcast_message = context.user_data.get('broadcast_message')
        country_code = context.user_data.get('selected_country')
        country_name = context.user_data.get('selected_country_name', 'Unknown')
        
        if not broadcast_message or not country_code:
            await query.edit_message_text("❌ Country data not found.")
            return
        
        # Get users in this country
        users = get_users_by_country(country_code)
        
        if not users:
            await query.edit_message_text(f"❌ No users found in {country_name}.")
            return
        
        total = len(users)
        successful = 0
        failed = 0
        
        # Send initial progress message
        progress_msg = await query.message.reply_text(
            f"📤 Starting broadcast to {country_name}...\n0/{total} (0%)"
        )
        
        for i, user in enumerate(users, 1):
            try:
                await context.bot.copy_message(
                    chat_id=user['user_id'],
                    from_chat_id=broadcast_message.chat_id,
                    message_id=broadcast_message.message_id
                )
                successful += 1
                
                # Update progress every 5 messages or at the end
                if i % 5 == 0 or i == total:
                    percentage = (i / total) * 100
                    await progress_msg.edit_text(
                        f"📤 Broadcasting to {country_name}...\n"
                        f"{i}/{total} ({percentage:.1f}%)\n"
                        f"✅ {successful} successful"
                    )
                    
            except Exception as e:
                failed += 1
                logger.error(f"Failed to send to user {user['user_id']} in {country_name}: {e}")
        
        # Save broadcast record
        content_preview = ""
        if broadcast_message.text:
            content_preview = broadcast_message.text[:100]
        elif broadcast_message.caption:
            content_preview = broadcast_message.caption[:100]
        else:
            content_preview = "Media message"
            
        save_broadcast(
            admin_id=user_id,
            target_type='country',
            target_id=country_code,
            message_type='country_broadcast',
            content=content_preview,
            sent_count=successful,
            failed_count=failed
        )
        
        # Send final report
        report = (
            f"✅ **COUNTRY BROADCAST COMPLETED**\n\n"
            f"📍 Country: {country_name}\n"
            f"📊 **Results:**\n"
            f"• Total users: {total}\n"
            f"• Successfully sent: {successful}\n"
            f"• Failed: {failed}\n"
            f"• Success rate: {(successful/total*100):.1f}%\n\n"
            f"📝 Message preview saved in database."
        )
        
        # Add back to admin button
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="back_to_admin")]
        ])
        
        await progress_msg.edit_text(report, reply_markup=keyboard)
        await query.message.delete()
        
        # Clear broadcast data
        context.user_data.clear()
    
    elif query.data == "cancel_send" or query.data == "cancel_specific" or query.data == "cancel_country":
        await query.edit_message_text("❌ Operation cancelled.")
        context.user_data.clear()
        await admin_panel(update, context)

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
    
    # Add conversation handler for user registration
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
    application.add_handler(CommandHandler('cancel', cancel))
    
    # Admin callback handlers
    application.add_handler(CallbackQueryHandler(admin_callback_handler, pattern='^broadcast_|^send_|^view_|^close_|^back_|^bcast_country_'))
    application.add_handler(CallbackQueryHandler(handle_broadcast_confirmation, pattern='^confirm_|^cancel_'))
    
    # Message handlers for users
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_main_menu))
    
    # Special handler for admin messages (for broadcast input)
    application.add_handler(MessageHandler(
        filters.ALL & filters.User(ADMIN_IDS), 
        handle_admin_message
    ))
    
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
