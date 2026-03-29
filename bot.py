import os
import time
import psycopg2
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Config
TOKEN = os.getenv("BOT_TOKEN")
DB_URL = os.getenv("DATABASE_URL")
SUBJECTS = ["Μαθηματικά", "Πληροφορική", "Έκθεση", "ΑΟΘ"]
CATEGORIES = ["Study", "Writing"]

# Database Setup
def init_db():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS study_logs (
        id SERIAL PRIMARY KEY,
        user_id BIGINT,
        subject TEXT,
        category TEXT,
        hours FLOAT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.commit()
    cur.close()
    conn.close()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("⏱️ Start Timer", callback_data="menu_timer"),
         InlineKeyboardButton("📝 Manual", callback_data="menu_manual")],
        [InlineKeyboardButton("📊 Stats", callback_data="stats")]
    ]
    await update.message.reply_text("Study Tracker 📚\nChoose an action:", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    # Timer Logic
    if data == "menu_timer":
        keys = [[InlineKeyboardButton(s, callback_data=f"t_sub_{s}")] for s in SUBJECTS]
        await query.edit_message_text("Select Subject:", reply_markup=InlineKeyboardMarkup(keys))
    
    elif data.startswith("t_sub_"):
        sub = data.split("_")[2]
        keys = [[InlineKeyboardButton(c, callback_data=f"start_{sub}_{c}")] for c in CATEGORIES]
        await query.edit_message_text(f"{sub}: Select Category:", reply_markup=InlineKeyboardMarkup(keys))

    elif data.startswith("start_"):
        _, sub, cat = data.split("_")
        context.user_data['timer'] = {"start": time.time(), "sub": sub, "cat": cat}
        await query.edit_message_text(f"🔴 Timer started for {sub} ({cat})...\nUse /stop to finish.")

    # Manual Entry Logic
    elif data == "menu_manual":
        keys = [[InlineKeyboardButton(s, callback_data=f"m_sub_{s}")] for s in SUBJECTS]
        await query.edit_message_text("Manual Entry - Select Subject:", reply_markup=InlineKeyboardMarkup(keys))

    elif data.startswith("m_sub_"):
        sub = data.split("_")[2]
        context.user_data['manual_sub'] = sub
        keys = [[InlineKeyboardButton(c, callback_data=f"m_cat_{c}")] for c in CATEGORIES]
        await query.edit_message_text(f"Manual {sub}: Select Category:", reply_markup=InlineKeyboardMarkup(keys))

    elif data.startswith("m_cat_"):
        context.user_data['manual_cat'] = data.split("_")[2]
        await query.edit_message_text("Please type the hours (e.g., 1.5 or 2):")

    # Stats Logic
    elif data == "stats":
        await send_stats(query.message, query.from_user.id)

async def stop_timer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'timer' not in context.user_data:
        await update.message.reply_text("No active timer!")
        return
    
    t = context.user_data.pop('timer')
    duration = (time.time() - t['start']) / 3600
    save_log(update.effective_user.id, t['sub'], t['cat'], duration)
    await update.message.reply_text(f"✅ Saved {duration:.2f} hours for {t['sub']} ({t['cat']})!")

async def handle_manual_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'manual_cat' in context.user_data:
        try:
            hours = float(update.message.text)
            sub = context.user_data.pop('manual_sub')
            cat = context.user_data.pop('manual_cat')
            save_log(update.effective_user.id, sub, cat, hours)
            await update.message.reply_text(f"✅ Manually logged {hours} hours for {sub} ({cat})!")
        except ValueError:
            await update.message.reply_text("Please enter a valid number (e.g. 1.5)")

def save_log(uid, sub, cat, hours):
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute("INSERT INTO study_logs (user_id, subject, category, hours) VALUES (%s, %s, %s, %s)", (uid, sub, cat, hours))
    conn.commit()
    cur.close()
    conn.close()

async def send_stats(message, uid):
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    
    periods = {
        "Today": "interval '1 day'",
        "Week": "interval '7 days'",
        "Month": "interval '30 days'",
        "Total": "interval '100 years'"
    }
    
    report = "📊 **STUDY STATISTICS**\n"
    for label, period in periods.items():
        cur.execute(f"SELECT subject, category, SUM(hours) FROM study_logs WHERE user_id = %s AND timestamp > CURRENT_TIMESTAMP - {period} GROUP BY subject, category", (uid,))
        rows = cur.fetchall()
        
        report += f"\n--- {label} ---\n"
        if not rows: report += "No data yet.\n"
        for sub, cat, hrs in rows:
            report += f"• {sub} ({cat}): {hrs:.2f}h\n"
    
    cur.close()
    conn.close()
    await message.reply_text(report, parse_mode="Markdown")

def main():
    init_db()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop_timer))
    app.add_handler(CommandHandler("stats", lambda u, c: send_stats(u.message, u.effective_user.id)))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_manual_text))
    app.run_polling()

if __name__ == "__main__":
    main()
