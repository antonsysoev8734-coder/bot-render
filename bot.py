import os
import sqlite3
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ---------------- SQLite -----------------
conn = sqlite3.connect("notes.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,
    content TEXT NOT NULL
)
""")
conn.commit()

# ---------------- Telegram Handlers -----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Добавить заметку", callback_data='add')],
        [InlineKeyboardButton("Поиск заметки", callback_data='search')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Привет! Я бот для заметок. Выбери действие:", reply_markup=reply_markup)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == 'add':
        await query.edit_message_text("Отправь текст, фото, видео или файл для сохранения.")
        context.user_data['mode'] = 'adding'
    elif query.data == 'search':
        await query.edit_message_text("Отправь ключевое слово для поиска заметок.")
        context.user_data['mode'] = 'searching'
    elif query.data.startswith('delete_'):
        note_id = int(query.data.split('_')[1])
        cursor.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        conn.commit()
        await query.edit_message_text("Заметка удалена!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = context.user_data.get('mode')
    if mode == 'adding':
        if update.message.text:
            cursor.execute("INSERT INTO notes (type, content) VALUES (?, ?)", ("text", update.message.text))
        elif update.message.photo:
            file_id = update.message.photo[-1].file_id
            cursor.execute("INSERT INTO notes (type, content) VALUES (?, ?)", ("photo", file_id))
        elif update.message.video:
            file_id = update.message.video.file_id
            cursor.execute("INSERT INTO notes (type, content) VALUES (?, ?)", ("video", file_id))
        elif update.message.document:
            file_id = update.message.document.file_id
            cursor.execute("INSERT INTO notes (type, content) VALUES (?, ?)", ("document", file_id))
        else:
            await update.message.reply_text("Тип сообщения не поддерживается.")
            return
        conn.commit()
        await update.message.reply_text("Заметка сохранена!")
        context.user_data['mode'] = None
    elif mode == 'searching':
        if update.message.text:
            query_text = f"%{update.message.text}%"
            cursor.execute("SELECT id, type, content FROM notes WHERE type='text' AND content LIKE ?", (query_text,))
            results = cursor.fetchall()
            if results:
                keyboard = [[InlineKeyboardButton(f"Удалить: {content[:30]}", callback_data=f'delete_{note_id}')]
                            for note_id, _, content in results]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text("Найдено текстовых заметок. Можешь удалить любую:", reply_markup=reply_markup)
            else:
                await update.message.reply_text("Ничего не найдено.")
        else:
            await update.message.reply_text("Пожалуйста, ищи по тексту.")
        context.user_data['mode'] = None

# ---------------- Flask App -----------------
flask_app = Flask(__name__)

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN не задан!")

bot = Bot(token=TOKEN)
application = ApplicationBuilder().token(TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(button))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
application.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.Document.ALL, handle_message))

# Webhook endpoint
@flask_app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, bot)
    # Асинхронно обрабатываем update
    import asyncio
    asyncio.create_task(application.process_update(update))
    return "OK"

# Root для ping
@flask_app.route("/")
def home():
    return "Бот работает через Webhook!"

if __name__ == "__main__":
    url = os.getenv("RENDER_EXTERNAL_URL")
    if not url:
        raise ValueError("RENDER_EXTERNAL_URL не задан!")

    webhook_url = f"{url}/{TOKEN}"
    bot.set_webhook(webhook_url)
    print(f"Webhook установлен: {webhook_url}")

    flask_app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
