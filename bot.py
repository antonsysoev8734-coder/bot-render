import os
import sqlite3
import asyncio
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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

# ---------------- Telegram Bot -----------------
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

# ---------------- Flask для ping -----------------
flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "Бот работает круглосуточно!"

# ---------------- Main -----------------
async def main():
    TOKEN = os.getenv("BOT_TOKEN")
    if not TOKEN:
        print("Ошибка: нужно задать BOT_TOKEN")
        return

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.Document.ALL, handle_message))

    print("Бот запущен...")

    # Запуск Telegram и Flask одновременно
    loop = asyncio.get_event_loop()
    from threading import Thread
    def run_flask():
        flask_app.run(host="0.0.0.0", port=10000)
    Thread(target=run_flask).start()

    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
