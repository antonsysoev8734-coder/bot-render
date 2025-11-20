import os
import sqlite3
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import asyncio

TOKEN = os.getenv("BOT_TOKEN")
URL = os.getenv("RENDER_EXTERNAL_URL")
PORT = int(os.getenv("PORT", 10000))

if not TOKEN or not URL:
    raise ValueError("BOT_TOKEN и RENDER_EXTERNAL_URL должны быть заданы!")

bot = Bot(token=TOKEN)
application = ApplicationBuilder().token(TOKEN).build()

# --- SQLite ---
def init_db():
    with sqlite3.connect("notes.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            content TEXT NOT NULL
        )
        """)
        conn.commit()

init_db()

def add_note(note_type, content):
    with sqlite3.connect("notes.db") as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO notes (type, content) VALUES (?, ?)", (note_type, content))
        conn.commit()

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Добавить заметку", callback_data="add")],
        [InlineKeyboardButton("Поиск заметки", callback_data="search")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Привет! Я бот для заметок. Выбери действие:", reply_markup=reply_markup)

application.add_handler(CommandHandler("start", start))

# --- Flask ---
flask_app = Flask(__name__)

@flask_app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, bot)
    asyncio.create_task(application.process_update(update))
    return "OK"

@flask_app.route("/")
def home():
    return "Бот работает!"

# --- Установка Webhook ---
bot.set_webhook(f"{URL}/{TOKEN}")
print("Webhook установлен:", f"{URL}/{TOKEN}")

flask_app.run(host="0.0.0.0", port=PORT)
