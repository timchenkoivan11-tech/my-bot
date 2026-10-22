import logging
import random
import json
import os
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler
from flask import Flask
from threading import Thread

# ================= НАСТРОЙКИ =================
BOT_TOKEN = "8789333228:AAHbI5m71sKP2PVIHUWGLX6gZ8L2AoRq-lE"
ADMIN_ID = 5522110735  # СЮДА ВСТАВЬ СВОЙ ID (БЕЗ КАВЫЧЕК)
ALLOWED_CHAT_ID = -1003797267456
DEFAULT_WIN_CHANCE = 99
COOLDOWN_MINUTES = 60
DATA_FILE = "bot_data.json"
# =============================================

logging.basicConfig(level=logging.INFO)

# --- Код мини-сайта для Render ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
# --------------------------------

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "win_chance" not in data:
                data["win_chance"] = DEFAULT_WIN_CHANCE
            return data
    return {"cooldowns": {}, "win_chance": DEFAULT_WIN_CHANCE}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

data = load_data()

# --- Админ-панель ---
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return
    
    await update.message.reply_text(
        f"👑 Привет, Админ!\n\n"
        f"Текущий шанс выпадения: **{data.get('win_chance', DEFAULT_WIN_CHANCE)}%**\n\n"
        f"Отправь мне сюда любое число (например, 5 или 0.5), чтобы изменить шанс.",
        parse_mode="Markdown"
    )

# --- Смена шанса ---
async def admin_change_chance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID or update.message.chat.type != 'private':
        return
    
    text = update.message.text.replace(',', '.')
    try:
        new_chance = float(text)
        if new_chance < 0 or new_chance > 100:
            await update.message.reply_text("❌ Ошибка! Введи число от 0 до 100.")
            return
            
        data["win_chance"] = new_chance
        save_data(data)
        
        await update.message.reply_text(f"✅ Успешно! Новый шанс на мишку: **{new_chance}%**", parse_mode="Markdown")
    except ValueError:
        await update.message.reply_text("❌ Это не похоже на число. Введи просто цифру (например: 1 или 0.5).")

# --- Основная логика чата ---
async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    
    user = update.message.from_user
    chat_id = str(update.message.chat_id)
    user_id = str(user.id)
    key = f"{chat_id}_{user_id}"

    now = datetime.now()
    cooldowns = data.get("cooldowns", {})
    current_chance = data.get("win_chance", DEFAULT_WIN_CHANCE)

    if COOLDOWN_MINUTES > 0:
        last_win = cooldowns.get(key)
        if last_win:
            last_time = datetime.fromisoformat(last_win)
            if now - last_time < timedelta(minutes=COOLDOWN_MINUTES):
                return

    if random.random() * 100 < current_chance:
        cooldowns[key] = now.isoformat()
        data["cooldowns"] = cooldowns
        save_data(data)

        winner_name = f"@{user.username}" if user.username else user.first_name

        text = (
            f"🎉 Поздравляю, {winner_name}!\n\n"
            f"🧸 Ты выиграл **мишку**!\n"
            f"✅ Подарок отправится в течение 2 часов 🕒\n\n"
            f"🚨 Пишите сообщения в чате, и получайте возможность так же залутать подарки."
        )

        bear_photo = "https://i.postimg.cc/qhh1Hndf/IMG_7671.jpg" 
        
        await update.message.reply_photo(
            photo=bear_photo, 
            caption=text, 
            parse_mode="Markdown"
        )

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    current_chance = data.get("win_chance", DEFAULT_WIN_CHANCE)
    await update.message.reply_text(
        f"🎲 Шанс на мишку: {current_chance}% с каждого сообщения.\n"
        f"Кулдаун после победы: {COOLDOWN_MINUTES} мин."
    )

def main():
    Thread(target=run_flask).start()
    
    app_bot = Application.builder().token(BOT_TOKEN).build()
    
    # Команды
    app_bot.add_handler(CommandHandler("start", start_cmd))
    app_bot.add_handler(CommandHandler("stats", stats))
    
    # Обработчик для админа (ловим только личные сообщения с числами)
    app_bot.add_handler(MessageHandler(
        filters.TEXT & filters.ChatType.PRIVATE & filters.User(user_id=int(ADMIN_ID)), 
        admin_change_chance
    ))
    
    # Обработчик сообщений в чате (активность)
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.ChatType.PRIVATE, on_message))
    
    print("Бот запущен...")
    app_bot.run_polling()

if __name__ == "__main__":
    main()
