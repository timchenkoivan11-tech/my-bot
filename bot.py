import logging
import random
import json
import os
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler

# ================= НАСТРОЙКИ =================
BOT_TOKEN = "8789333228:AAHbI5m71sKP2PVIHUWGLX6gZ8L2AoRq-lE"
WIN_CHANCE_PERCENT = 0.1
COOLDOWN_MINUTES = 60
DATA_FILE = "bot_data.json"
# =============================================

logging.basicConfig(level=logging.INFO)

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"cooldowns": {}}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

data = load_data()

async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    
    user = update.message.from_user
    chat_id = str(update.message.chat_id)
    user_id = str(user.id)
    key = f"{chat_id}_{user_id}"

    now = datetime.now()
    cooldowns = data.get("cooldowns", {})

    if COOLDOWN_MINUTES > 0:
        last_win = cooldowns.get(key)
        if last_win:
            last_time = datetime.fromisoformat(last_win)
            if now - last_time < timedelta(minutes=COOLDOWN_MINUTES):
                return

    if random.random() * 100 < WIN_CHANCE_PERCENT:
        cooldowns[key] = now.isoformat()
        data["cooldowns"] = cooldowns
        save_data(data)

        winner_name = f"@{user.username}" if user.username else user.first_name

        text = (
            f"🎉 Поздравляю, {winner_name}!\n\n"
            f"🧸 Ты выиграл **плюшевого мишку**!\n"
            f"✅ Подарок отправится в течение 2 часов 🕒\n\n"
            f"🚨 Пишите сообщения в чате, и получайте возможность так же залутать подарки.\n\n"
            f"Общайтесь в моем чате @твой_ник_чат"
        )

        await update.message.reply_text(
            text=text,
            parse_mode="Markdown"
        )

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🎲 Шанс на мишку: {WIN_CHANCE_PERCENT}% с каждого сообщения.\n"
        f"Кулдаун после победы: {COOLDOWN_MINUTES} мин."
    )

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    app.add_handler(CommandHandler("stats", stats))
    print("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
