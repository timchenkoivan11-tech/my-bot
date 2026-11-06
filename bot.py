import logging
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from flask import Flask
from threading import Thread

logging.basicConfig(level=logging.INFO)

app = Flask('')
@app.route('/')
def home(): return "Bot is alive!"
def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

BOT_TOKEN = os.environ.get("BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Я работаю!")

# ЭТА ФУНКЦИЯ УДАЛЯЕТ ВЕБХУК ПРИ СТАРТЕ
async def post_init(application: Application) -> None:
    await application.bot.delete_webhook(drop_pending_updates=True)
    print("✅ Вебхук удален, старые сообщения сброшены.")

def main():
    Thread(target=run_flask).start()
    
    # ДОБАВЛЯЕМ ТАЙМАУТЫ И АВТООЧИСТКУ
    app_bot = (
        Application.builder()
        .token(BOT_TOKEN)
        .read_timeout(30)
        .write_timeout(30)
        .connect_timeout(30)
        .pool_timeout(30)
        .post_init(post_init) # Вызываем очистку при старте
        .build()
    )
    
    app_bot.add_handler(CommandHandler("start", start))
    
    print("Бот запущен...")
    app_bot.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
