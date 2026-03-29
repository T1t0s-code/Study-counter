import os
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# Configuration
TOKEN = os.getenv("BOT_TOKEN")
SUBJECTS = ["Μαθηματικά", "Πληροφορική", "Έκθεση", "ΑΟΘ"]
CATEGORIES = ["Study", "Writing"]

# In-memory storage (Note: Resets if Railway restarts)
# For a permanent fix, you'd need a database, but let's start simple.
user_data = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("⏱️ Start Timer", callback_data="menu_timer")],
        [InlineKeyboardButton("📝 Manual Entry", callback_data="menu_manual")],
        [InlineKeyboardButton("📊 View Stats", callback_data="stats")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Choose an action:", reply_markup=reply_markup)

async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "menu_timer":
        keyboard = [[InlineKeyboardButton(s, callback_data=f"start_{s}")] for s in SUBJECTS]
        await query.edit_message_text("Select Subject to Start Timer:", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif query.data == "menu_manual":
        keyboard = [[InlineKeyboardButton(s, callback_data=f"man_{s}")] for s in SUBJECTS]
        await query.edit_message_text("Select Subject for Manual Entry:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("start_"):
        subject = query.data.split("_")[1]
        context.user_data['timer_start'] = time.time()
        context.user_data['current_subject'] = subject
        keyboard = [[InlineKeyboardButton("🛑 Stop & Save", callback_data=f"stop_{subject}")]]
        await query.edit_message_text(f"Timer started for {subject}...", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("stop_"):
        subject = query.data.split("_")[1]
        elapsed = (time.time() - context.user_data.get('timer_start', time.time())) / 3600
        # Save logic here...
        await query.edit_message_text(f"Logged {elapsed:.2f} hours for {subject}!")

# This is a simplified version. I will provide the full robust code once you confirm the logic.
