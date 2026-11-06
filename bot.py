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

def main():
    Thread(target=run_flask).start()
    app_bot = Application.builder().token(BOT_TOKEN).build()
    app_bot.add_handler(CommandHandler("start", start))
    print("Бот запущен...")
    app_bot.run_polling()

if __name__ == "__main__":
    main()
