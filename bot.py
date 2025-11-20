import os
import sqlite3
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler, 
    MessageHandler, filters, ContextTypes
)

# ---------------- Flask App -----------------
flask_app = Flask(__name__)

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN не задан!")

bot = Bot(token=TOKEN)
application = ApplicationBuilder().token(TOKEN).build()

# ---------------- SQLite Helper -----------------
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

def search_text_notes(keyword):
    with sqlite3.connect("notes.db") as conn:
        cursor = conn.cursor()
        query_text = f"%{keyword}%"
        cursor.execute("SELECT id, type, content FROM notes WHERE type='text' AND content LIKE ?", (query_text,))
        return cursor.fetchall()

def delete_note(note_id):
    with sqlite3.connect("notes.db") as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        conn.commit()

# ---------------- Telegram Handlers -----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_main_menu(update, context)

# Функция для отображения главного меню
async def show_main_menu(update_or_query, context):
    keyboard = [
        [InlineKeyboardButton("Добавить заметку", callback_data='add')],
        [InlineKeyboardButton("Поиск заметки", callback_data='search')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if hasattr(update_or_query, "edit_message_text"):
        await update_or_query.edit_message_text("Выбери действие:", reply_markup=reply_markup)
    else:
        await update_or_query.reply_text("Привет! Я бот для заметок. Выбери действие:", reply_markup=reply_markup)

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
        delete_note(note_id)
        await query.edit_message_text("Заметка удалена!")
        # Показываем главное меню после удаления
        await show_main_menu(query, context)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = context.user_data.get('mode')
    if mode == 'adding':
        if update.message.text:
            add_note("text", update.message.text)
        elif update.message.photo:
            file_id = update.message.photo[-1].file_id
            add_note("photo", file_id)
        elif update.message.video:
            file_id = update.message.video.file_id
            add_note("video", file_id)
        elif update.message.document:
            file_id = update.message.document.file_id
            add_note("document", file_id)
        else:
            await update.message.reply_text("Тип сообщения не поддерживается.")
            return
        await update.message.reply_text("Заметка сохранена!")
        context.user_data['mode'] = None
        # Показываем главное меню после добавления
        await show_main_menu(update, context)

    elif mode == 'searching':
        if update.message.text:
            results = search_text_notes(update.message.text)
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
        # Показываем главное меню после поиска
        await show_main_menu(update, context)

# ---------------- Register Handlers -----------------
application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(button))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
application.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.Document.ALL, handle_message))

# ---------------- Webhook Endpoint -----------------
@flask_app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, bot)
    import asyncio
    asyncio.run(application.process_update(update))  # Асинхронно обрабатываем update
    return "OK"

# ---------------- Healthcheck -----------------
@flask_app.route("/")
def home():
    return "Бот работает через Webhook!"

# ---------------- Main -----------------
if __name__ == "__main__":
    url = os.getenv("RENDER_EXTERNAL_URL")
    if not url:
        raise ValueError("RENDER_EXTERNAL_URL не задан!")

    webhook_url = f"{url}/{TOKEN}"
    bot.set_webhook(webhook_url)
    print(f"Webhook установлен: {webhook_url}")

    flask_app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
