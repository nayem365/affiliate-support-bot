from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from config import COUNTRIES

def country_selection_keyboard():
    keyboard = []
    for code, info in COUNTRIES.items():
        keyboard.append([
            InlineKeyboardButton(
                f"{info['flag']} {info['name']}",
                callback_data=f"country_{code}"
            )
        ])
    return InlineKeyboardMarkup(keyboard)

def contact_keyboard():
    keyboard = [[
        KeyboardButton("📱 Share Phone Number", request_contact=True)
    ]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

def main_menu_keyboard(is_admin=False):
    keyboard = [
        ["📞 Contact Local Manager", "ℹ️ About Program"],
        ["🔄 Restart"]
    ]
    
    if is_admin:
        keyboard.insert(0, ["📢 Broadcast"])
    
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def admin_broadcast_keyboard():
    keyboard = [
        [InlineKeyboardButton("📢 Broadcast to All", callback_data="broadcast_all")],
        [InlineKeyboardButton("🌍 Broadcast by Country", callback_data="broadcast_country")],
        [InlineKeyboardButton("👤 Broadcast to User", callback_data="broadcast_user")],
        [InlineKeyboardButton("↩️ Back", callback_data="back_to_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def broadcast_country_keyboard():
    keyboard = []
    for code, info in COUNTRIES.items():
        keyboard.append([
            InlineKeyboardButton(
                f"{info['flag']} {info['name']}",
                callback_data=f"broadcast_country_{code}"
            )
        ])
    keyboard.append([InlineKeyboardButton("↩️ Back", callback_data="admin_broadcast")])
    return InlineKeyboardMarkup(keyboard)
