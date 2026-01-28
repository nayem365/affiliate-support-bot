import os
import logging
import asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    MessageHandler, filters, ContextTypes
)
from telegram.constants import ParseMode

from config import BOT_TOKEN, COUNTRIES, ADMIN_IDS
from database import Database
from keyboards import (
    country_selection_keyboard, contact_keyboard,
    main_menu_keyboard, admin_broadcast_keyboard,
    broadcast_country_keyboard
)

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Check if token is set
if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN is not set! Please set it in Heroku config.")
    exit(1)

# Initialize database
db = Database()

# Flask app
app = Flask(__name__)

# Create bot application
application = Application.builder().token(BOT_TOKEN).build()

# Store broadcast states
broadcast_states = {}

# --- REGISTRATION FLOW ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    try:
        user = update.effective_user
        user_id = user.id
        
        existing_user = db.get_user(user_id)
        
        if existing_user and existing_user[3]:
            is_admin = db.is_admin(user_id)
            await update.message.reply_text(
                "**MAIN MENU**\nSelect an option:",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=main_menu_keyboard(is_admin)
            )
        else:
            await update.message.reply_text(
                "🌍 **Welcome! Please select your country:**",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=country_selection_keyboard()
            )
    except Exception as e:
        logger.error(f"Error in start_command: {e}")
        await update.message.reply_text("❌ An error occurred. Please try again.")

async def country_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle country selection"""
    try:
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        data = query.data
        
        if data.startswith('country_'):
            country_code = data.split('_')[1]
            country_info = COUNTRIES.get(country_code, {})
            
            db.set_user_country(user_id, country_code)
            
            await query.edit_message_text(
                f"📱 **Please share your phone number:**\n\n"
                f"Country: {country_info.get('flag', '')} {country_info.get('name', '')}\n"
                f"Tap the button below:",
                parse_mode=ParseMode.MARKDOWN
            )
            
            await context.bot.send_message(
                chat_id=user_id,
                text="Share phone number:",
                reply_markup=contact_keyboard()
            )
    except Exception as e:
        logger.error(f"Error in country_callback: {e}")
        await query.edit_message_text("❌ An error occurred. Please try /start again.")

async def contact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle contact sharing"""
    try:
        user = update.effective_user
        user_id = user.id
        contact = update.message.contact
        
        waiting, country_code = db.is_waiting_for_contact(user_id)
        
        if waiting and contact and country_code:
            phone = contact.phone_number
            if not phone.startswith('+'):
                phone = '+' + phone
            
            country_code = db.complete_registration(user_id, phone)
            
            if country_code:
                country_info = COUNTRIES.get(country_code, {})
                
                await update.message.reply_text(
                    "**REGISTRATION SUCCESSFUL!**\n\n"
                    "• Account Created\n"
                    f"  Name: {user.full_name or user.first_name}\n"
                    f"  Country: {country_info.get('flag', '')} {country_info.get('name', '')}\n"
                    f"  Language: {country_info.get('language', 'Русский')}\n\n"
                    "• Use the menu below to get started:",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=main_menu_keyboard(user_id in ADMIN_IDS)
                )
                
                # Notify admins
                for admin_id in ADMIN_IDS:
                    try:
                        await context.bot.send_message(
                            chat_id=admin_id,
                            text=f"👤 **NEW USER REGISTERED!**\n\n"
                                 f"• User ID: {user_id}\n"
                                 f"• Name: {user.full_name or user.first_name}\n"
                                 f"• Phone: {phone}\n"
                                 f"• Country: {country_info.get('flag', '')} {country_info.get('name', '')}",
                            parse_mode=ParseMode.MARKDOWN
                        )
                    except Exception as e:
                        logger.error(f"Failed to notify admin {admin_id}: {e}")
        else:
            await update.message.reply_text(
                "Please use /start to begin registration.",
                reply_markup=main_menu_keyboard(user_id in ADMIN_IDS)
            )
    except Exception as e:
        logger.error(f"Error in contact_handler: {e}")
        await update.message.reply_text("❌ An error occurred. Please try /start again.")

# --- MAIN MENU FUNCTIONS ---
async def contact_manager(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Contact Local Manager"""
    try:
        user_id = update.effective_user.id
        user_data = db.get_user(user_id)
        
        if user_data:
            country_code = user_data[4] or 'BD'
            country_info = COUNTRIES.get(country_code, {})
            
            await update.message.reply_text(
                f"**Contact Local Manager**\n"
                f"📞 Region: {country_info.get('flag', '')} {country_info.get('name', '')}\n\n"
                f"Please contact our local manager for personalized support:\n"
                f"{country_info.get('manager', '@SupportManager_BD')}\n\n"
                f"*Note: Contact your manager directly on Telegram*",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text("Please register first with /start")
    except Exception as e:
        logger.error(f"Error in contact_manager: {e}")
        await update.message.reply_text("❌ An error occurred.")

async def about_program(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle About Program"""
    try:
        user_id = update.effective_user.id
        user_data = db.get_user(user_id)
        
        country_code = user_data[4] if user_data else 'BD'
        country_info = COUNTRIES.get(country_code, {})
        
        await update.message.reply_text(
            f"**AFFILIATE PROGRAM - {country_info.get('flag', '')} {country_info.get('name', '')}**\n\n"
            f"• Commission: {country_info.get('commission', '20–30%')}\n"
            f"• Daily payments\n"
            f"• Marketing tools provided\n"
            f"• 24/7 support\n"
            f"• Country-specific offers\n\n"
            f"📞 Contact your local manager to get started!",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"Error in about_program: {e}")
        await update.message.reply_text("❌ An error occurred.")

async def restart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Restart"""
    try:
        user_id = update.effective_user.id
        is_admin = db.is_admin(user_id)
        
        await update.message.reply_text(
            "🔄 Session restarted!\n\n"
            "**MAIN MENU**\nSelect an option:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_menu_keyboard(is_admin)
        )
    except Exception as e:
        logger.error(f"Error in restart_command: {e}")
        await update.message.reply_text("❌ An error occurred.")

# --- ADMIN BROADCAST SYSTEM ---
async def admin_broadcast_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show admin broadcast menu"""
    try:
        user_id = update.effective_user.id
        
        if user_id in ADMIN_IDS:
            await update.message.reply_text(
                "📢 **BROADCAST TO ALL USERS**\n\n"
                "Select broadcast target:",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=admin_broadcast_keyboard()
            )
        else:
            await update.message.reply_text("⛔ You are not authorized.")
    except Exception as e:
        logger.error(f"Error in admin_broadcast_menu: {e}")
        await update.message.reply_text("❌ An error occurred.")

async def broadcast_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle broadcast callbacks"""
    try:
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        data = query.data
        
        if user_id not in ADMIN_IDS:
            await query.edit_message_text("⛔ You are not authorized.")
            return
        
        if data == 'admin_broadcast':
            await query.edit_message_text(
                "📢 **BROADCAST TO ALL USERS**\n\n"
                "Select broadcast target:",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=admin_broadcast_keyboard()
            )
        
        elif data == 'broadcast_all':
            broadcast_states[user_id] = {'type': 'all'}
            await query.edit_message_text(
                "📢 **BROADCAST TO ALL USERS**\n\n"
                "Send your message now (text, photo, or document):\n\n"
                "Type /cancel to abort.",
                parse_mode=ParseMode.MARKDOWN
            )
        
        elif data == 'broadcast_country':
            await query.edit_message_text(
                "🌍 **Select country to broadcast:**",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=broadcast_country_keyboard()
            )
        
        elif data.startswith('broadcast_country_'):
            country_code = data.split('_')[2]
            country_info = COUNTRIES.get(country_code, {})
            
            broadcast_states[user_id] = {'type': 'country', 'country': country_code}
            
            await query.edit_message_text(
                f"📢 **BROADCAST TO {country_info.get('flag', '')} {country_info.get('name', '')}**\n\n"
                f"Send your message now (text, photo, or document):\n\n"
                f"Type /cancel to abort.",
                parse_mode=ParseMode.MARKDOWN
            )
        
        elif data == 'broadcast_user':
            broadcast_states[user_id] = {'type': 'user', 'step': 'waiting_for_id'}
            await query.edit_message_text(
                "👤 **BROADCAST TO SPECIFIC USER**\n\n"
                "Please send the user ID you want to broadcast to:",
                parse_mode=ParseMode.MARKDOWN
            )
        
        elif data == 'back_to_menu':
            if user_id in broadcast_states:
                del broadcast_states[user_id]
            await query.edit_message_text(
                "**MAIN MENU**\nSelect an option:",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=main_menu_keyboard(True)
            )
    except Exception as e:
        logger.error(f"Error in broadcast_callback: {e}")
        await query.edit_message_text("❌ An error occurred.")

async def broadcast_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle broadcast messages from admin"""
    try:
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            return
        
        if user_id in broadcast_states and broadcast_states[user_id].get('step') == 'waiting_for_id':
            try:
                target_user_id = int(update.message.text)
                broadcast_states[user_id] = {
                    'type': 'specific_user', 
                    'target_user': target_user_id,
                    'step': 'waiting_for_message'
                }
                await update.message.reply_text(
                    f"✅ Target user set to: {target_user_id}\n\n"
                    f"Now send your message (text, photo, or document):",
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            except ValueError:
                await update.message.reply_text("❌ Please enter a valid user ID (numbers only).")
                return
        
        if user_id in broadcast_states:
            broadcast_info = broadcast_states[user_id]
            
            if broadcast_info['type'] == 'all':
                users = db.get_all_users()
                target_desc = "All Users"
            elif broadcast_info['type'] == 'country':
                users = db.get_users_by_country(broadcast_info['country'])
                country_info = COUNTRIES.get(broadcast_info['country'], {})
                target_desc = f"{country_info.get('flag', '')} {country_info.get('name', '')}"
            elif broadcast_info['type'] == 'specific_user':
                users = [broadcast_info['target_user']]
                target_desc = f"User ID: {broadcast_info['target_user']}"
            else:
                users = []
                target_desc = "Unknown"
            
            users = [uid for uid in users if uid != user_id]
            
            success = 0
            failed = 0
            
            for target_user in users:
                try:
                    if update.message.text:
                        await context.bot.send_message(
                            chat_id=target_user,
                            text=update.message.text,
                            parse_mode=ParseMode.MARKDOWN
                        )
                    elif update.message.photo:
                        await context.bot.send_photo(
                            chat_id=target_user,
                            photo=update.message.photo[-1].file_id,
                            caption=update.message.caption or ""
                        )
                    elif update.message.document:
                        await context.bot.send_document(
                            chat_id=target_user,
                            document=update.message.document.file_id,
                            caption=update.message.caption or ""
                        )
                    success += 1
                except Exception as e:
                    logger.error(f"Failed to send to {target_user}: {e}")
                    failed += 1
            
            del broadcast_states[user_id]
            
            await update.message.reply_text(
                f"✅ **Broadcast Sent Successfully!**\n\n"
                f"• Target: {target_desc}\n"
                f"• Success: {success}\n"
                f"• Failed: {failed}\n\n"
                f"Returning to main menu...",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=main_menu_keyboard(True)
            )
    except Exception as e:
        logger.error(f"Error in broadcast_message_handler: {e}")
        await update.message.reply_text("❌ An error occurred during broadcast.")

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel current operation"""
    try:
        user_id = update.effective_user.id
        
        if user_id in broadcast_states:
            del broadcast_states[user_id]
        
        is_admin = db.is_admin(user_id)
        await update.message.reply_text(
            "❌ Operation cancelled.",
            reply_markup=main_menu_keyboard(is_admin)
        )
    except Exception as e:
        logger.error(f"Error in cancel_command: {e}")
        await update.message.reply_text("❌ An error occurred.")

async def text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages for main menu"""
    try:
        user_id = update.effective_user.id
        text = update.message.text
        
        if text == "📞 Contact Local Manager":
            await contact_manager(update, context)
        elif text == "ℹ️ About Program":
            await about_program(update, context)
        elif text == "🔄 Restart":
            await restart_command(update, context)
        elif text == "📢 Broadcast":
            await admin_broadcast_menu(update, context)
        else:
            pass
    except Exception as e:
        logger.error(f"Error in text_message_handler: {e}")

# --- SETUP HANDLERS ---
def setup_handlers():
    """Setup all bot handlers"""
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    application.add_handler(CallbackQueryHandler(country_callback, pattern="^country_"))
    application.add_handler(CallbackQueryHandler(broadcast_callback))
    application.add_handler(MessageHandler(filters.CONTACT, contact_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler))
    application.add_handler(MessageHandler(
        (filters.TEXT | filters.PHOTO | filters.Document.ALL) & filters.User(ADMIN_IDS), 
        broadcast_message_handler
    ))

# --- FLASK ROUTES ---
@app.route('/')
def home():
    return "✅ Telegram Bot is running!"

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle Telegram webhook updates"""
    if request.method == 'POST':
        update = Update.de_json(request.get_json(force=True), application.bot)
        application.update_queue.put(update)
    return 'ok', 200

@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    """Set webhook manually"""
    try:
        webhook_url = f"https://{os.environ.get('HEROKU_APP_NAME', 'affiliate-system')}.herokuapp.com/webhook"
        
        # Delete existing webhook
        application.bot.delete_webhook()
        
        # Set new webhook
        result = application.bot.set_webhook(
            url=webhook_url,
            drop_pending_updates=True
        )
        
        return f"✅ Webhook set to: {webhook_url}<br>Result: {result}"
    except Exception as e:
        return f"❌ Error: {str(e)}"

# --- INITIALIZE BOT ---
async def initialize_bot():
    """Initialize the bot"""
    logger.info("Setting up bot handlers...")
    setup_handlers()
    await application.initialize()
    
    # Check if running on Heroku
    if 'DYNO' in os.environ:
        logger.info("Running on Heroku - webhook mode")
        
        # Set webhook
        webhook_url = f"https://{os.environ.get('HEROKU_APP_NAME', 'affiliate-system')}.herokuapp.com/webhook"
        await application.bot.set_webhook(
            url=webhook_url,
            drop_pending_updates=True
        )
        logger.info(f"Webhook set to: {webhook_url}")
        
        await application.start()
    else:
        logger.info("Running locally - polling mode")
        await application.start()
        await application.updater.start_polling()

# --- MAIN ---
def main():
    """Start the application"""
    logger.info(f"Starting bot with token starting: {BOT_TOKEN[:10]}...")
    
    # Start bot in background
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(initialize_bot())
    
    # Start Flask
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

if __name__ == '__main__':
    main()
