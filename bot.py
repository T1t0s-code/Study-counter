import os
import time
import psycopg2
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Config
TOKEN = os.getenv("BOT_TOKEN")
DB_URL = os.getenv("DATABASE_URL")
SUBJECTS = ["Μαθηματικά", "Πληροφορική", "Έκθεση", "ΑΟΘ"]
CATEGORIES = ["Θεωρία", "Ασκήσεις"]

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

def save_log(uid, sub, cat, hours):
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute("INSERT INTO study_logs (user_id, subject, category, hours) VALUES (%s, %s, %s, %s)", (uid, sub, cat, hours))
    conn.commit()
    cur.close()
    conn.close()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("⏱️ Start Timer", callback_data="menu_timer"),
         InlineKeyboardButton("📝 Manual Entry", callback_data="menu_manual")],
        [InlineKeyboardButton("📊 Stats", callback_data="stats"),
         InlineKeyboardButton("🗑️ Delete Last", callback_data="menu_delete")]
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
        await query.edit_message_text(f"Logging {context.user_data['manual_sub']} ({data.split('_')[2]}).\nType the hours (e.g., 1.5):")

    # Deletion Logic
    elif data == "menu_delete":
        await list_recent_for_delete(query)

    elif data.startswith("del_id_"):
        log_id = data.split("_")[2]
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute("DELETE FROM study_logs WHERE id = %s AND user_id = %s", (log_id, query.from_user.id))
        conn.commit()
        cur.close()
        conn.close()
        await query.edit_message_text("✅ Entry deleted successfully.")

    elif data == "stats":
        await send_stats(query.message, query.from_user.id)

async def stop_timer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'timer' not in context.user_data:
        await update.message.reply_text("No active timer!")
        return
    t = context.user_data.pop('timer')
    duration = round((time.time() - t['start']) / 3600, 2)
    save_log(update.effective_user.id, t['sub'], t['cat'], duration)
    await update.message.reply_text(f"✅ Saved {duration} hours for {t['sub']} ({t['cat']})!")

async def handle_manual_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'manual_cat' in context.user_data:
        try:
            hours = float(update.message.text.replace(',', '.'))
            sub = context.user_data.pop('manual_sub')
            cat = context.user_data.pop('manual_cat')
            save_log(update.effective_user.id, sub, cat, hours)
            await update.message.reply_text(f"✅ Manually logged {hours} hours for {sub} ({cat})!")
        except ValueError:
            await update.message.reply_text("Please enter a valid number (e.g. 1.5 or 2)")

async def list_recent_for_delete(query):
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute("SELECT id, subject, category, hours, timestamp FROM study_logs WHERE user_id = %s ORDER BY timestamp DESC LIMIT 5", (query.from_user.id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    if not rows:
        await query.edit_message_text("No logs found to delete.")
        return

    keyboard = []
    for r in rows:
        btn_text = f"❌ {r[1]} | {r[2]} | {r[3]}h"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"del_id_{r[0]}")])
    
    await query.edit_message_text("Select an entry to delete permanently:", reply_markup=InlineKeyboardMarkup(keyboard))

async def send_stats(message, uid):
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    periods = [("Today", "1 day"), ("Week", "7 days"), ("Month", "30 days"), ("Total", "100 years")]
    
    report = "📊 **STUDY STATISTICS**\n"
    for label, interval in periods:
        cur.execute(f"""SELECT subject, category, SUM(hours) FROM study_logs 
                       WHERE user_id = %s AND timestamp > CURRENT_TIMESTAMP - interval '{interval}' 
                       GROUP BY subject, category ORDER BY subject""", (uid,))
        rows = cur.fetchall()
        report += f"\n🗓️ **{label}**\n"
        if not rows:
            report += "No data.\n"
        else:
            current_sub = ""
            for sub, cat, hrs in rows:
                if sub != current_sub:
                    report += f"• {sub}:\n"
                    current_sub = sub
                report += f"  └ {cat}: {hrs:.2f}h\n"
    
    cur.close()
    conn.close()
    await message.reply_text(report, parse_mode="Markdown")

def main():
    init_db()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop_timer))
    app.add_handler(CommandHandler("stats", lambda u, c: send_stats(u.message, u.effective_user.id)))
    app.add_handler(CommandHandler("delete", lambda u, c: list_recent_for_delete(u.callback_query if u.callback_query else u)))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_manual_text))
    app.run_polling()

if __name__ == "__main__":
    main()
