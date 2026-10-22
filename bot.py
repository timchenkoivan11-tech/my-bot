import logging
import random
import json
import os
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler, CallbackQueryHandler
from flask import Flask
from threading import Thread

# ================= НАСТРОЙКИ =================
BOT_TOKEN = "8789333228:AAHbI5m71sKP2PVIHUWGLX6gZ8L2AoRq-lE"
ADMIN_ID = 5522110735  
ALLOWED_CHAT_ID = -1003797267456  
DEFAULT_WIN_CHANCE = 0.1
COOLDOWN_MINUTES = 60
DATA_FILE = "bot_data.json"

DEFAULT_TIMER = 60
DEFAULT_PRIZE = "Плюшевый мишка 🧸"
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

# Глобальные переменные для таймера
current_timer_task = None
current_king_id = None
current_king_name = None

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "win_chance" not in data: data["win_chance"] = DEFAULT_WIN_CHANCE
            if "timer" not in data: data["timer"] = DEFAULT_TIMER
            if "prize" not in data: data["prize"] = DEFAULT_PRIZE
            return data
    return {"cooldowns": {}, "win_chance": DEFAULT_WIN_CHANCE, "timer": DEFAULT_TIMER, "prize": DEFAULT_PRIZE}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

data = load_data()

# --- Вспомогательная функция для главного меню ---
def get_main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("⏱ 30 секунд", callback_data='time_30'),
         InlineKeyboardButton("⏱ 1 минута", callback_data='time_60')],
        [InlineKeyboardButton("⏱ 2 минуты", callback_data='time_120'),
         InlineKeyboardButton("⏱ 5 минут", callback_data='time_300')],
        [InlineKeyboardButton("📖 Все команды", callback_data='show_commands')],
        [InlineKeyboardButton(f"🎁 Текущий приз: {data.get('prize')}", callback_data='ignore')]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- Асинхронная задача таймера ---
async def run_timer(chat_id, user_id, user_name, seconds, prize, context):
    global current_king_id, current_king_name
    try:
        if seconds > 30:
            await asyncio.sleep(seconds - 30)
            await context.bot.send_message(chat_id, f"⏳ Осталось 30 секунд! Корону держит {user_name}. Успей перебить!")
        
        if seconds > 20:
            await asyncio.sleep(10)
            await context.bot.send_message(chat_id, f"⏳ Осталось 20 секунд!")
            
        if seconds > 10:
            await asyncio.sleep(10)
            await context.bot.send_message(chat_id, f"🚨 Внимание! Осталось 10 секунд!")

        for i in range(5, 0, -1):
            await asyncio.sleep(1)
            await context.bot.send_message(chat_id, f"🔥 **{i}**...", parse_mode="Markdown")

        await asyncio.sleep(1)
        text = (
            f"👑 **ПОБЕДА!**\n\n"
            f"Участник {user_name} продержался дольше всех и забирает приз:\n"
            f"🎁 **{prize}**!"
        )
        await context.bot.send_message(chat_id, text, parse_mode="Markdown")
        
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logging.error(f"Ошибка в таймере: {e}")

# --- Обработка сообщений в чате ---
async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_timer_task, current_king_id, current_king_name

    if not update.message or not update.message.text: return
    if update.message.chat_id != ALLOWED_CHAT_ID: return
    
    user = update.message.from_user
    if user.id == ADMIN_ID: return

    user_name = f"@{user.username}" if user.username else user.first_name

    if current_timer_task and not current_timer_task.done():
        current_timer_task.cancel()
        if current_king_id != user.id:
            await update.message.reply_text(f"⚔️ {user_name} перебивает {current_king_name} и забирает корону!")
    
    current_king_id = user.id
    current_king_name = user_name

    seconds = data.get("timer", DEFAULT_TIMER)
    prize = data.get("prize", DEFAULT_PRIZE)

    current_timer_task = asyncio.create_task(run_timer(update.message.chat_id, user.id, user_name, seconds, prize, context))

# --- АДМИН-ПАНЕЛЬ ---
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID: return
    
    await update.message.reply_text(
        f"👑 **Админ-панель**\n\n"
        f"Текущее время: **{data.get('timer')} сек.**\n"
        f"Выбери удобное время кнопкой ниже или загляни в список команд:",
        reply_markup=get_main_menu_keyboard(),
        parse_mode="Markdown"
    )

# --- Обработка нажатий на кнопки ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID: return

    # Обработка кнопок времени
    if query.data.startswith('time_'):
        new_time = int(query.data.split('_')[1])
        data["timer"] = new_time
        save_data(data)
        
        await query.edit_message_text(
            text=f"✅ **Успешно!**\n\nТаймер изменен на **{new_time} секунд**.\nТеперь можешь проверить в чате.",
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown"
        )
    
    # Обработка кнопки "Все команды"
    elif query.data == 'show_commands':
        commands_text = (
            "📚 **Все доступные команды (вводить в чате с ботом):**\n\n"
            "🔹 `/start` — Открыть эту панель управления\n"
            "🔹 `/settime <сек>` — Задать таймер вручную (напр. `/settime 45`)\n"
            "🔹 `/setprize <текст>` — Изменить приз (напр. `/setprize Тортик 🎂`)\n"
            "🔹 `/price <звезды>` — Объявить в чат новую цену (напр. `/price 5`)\n"
            "🔹 `/stats` — Узнать текущий шанс (работает только в общем чате)\n\n"
            "💡 *Кнопки времени работают автоматически, просто жми на них.*"
        )
        back_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад в меню", callback_data='back_to_menu')]])
        await query.edit_message_text(text=commands_text, reply_markup=back_keyboard, parse_mode="Markdown")

    # Обработка кнопки "Назад"
    elif query.data == 'back_to_menu':
        await query.edit_message_text(
            text=f"👑 **Админ-панель**\n\n"
                 f"Текущее время: **{data.get('timer')} сек.**\n"
                 f"Выбери удобное время кнопкой ниже или загляни в список команд:",
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown"
        )

async def set_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID: return
    try:
        new_time = int(context.args[0])
        data["timer"] = new_time
        save_data(data)
        await update.message.reply_text(f"✅ Время таймера изменено на {new_time} секунд.")
    except:
        await update.message.reply_text("❌ Ошибка. Пиши так: `/settime 90`")

async def set_prize(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID: return
    if not context.args:
        await update.message.reply_text("❌ Ошибка. Пиши так: `/setprize Плюшевый мишка`")
        return
    new_prize = " ".join(context.args)
    data["prize"] = new_prize
    save_data(data)
    await update.message.reply_text(f"✅ Приз изменен на: {new_prize}")

async def announce_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID: return
    if not context.args:
        await update.message.reply_text("❌ Ошибка. Пиши так: `/price 5`")
        return
    
    price = context.args[0]
    text = (
        f"📢 **ВНИМАНИЕ!**\n\n"
        f"Администратор установил цену за сообщение: **{price} ⭐**.\n"
        f"Теперь каждое сообщение в этом чате стоит {price} звезд. "
        f"Звезды идут на развитие и подарки для чата!"
    )
    await context.bot.send_message(chat_id=ALLOWED_CHAT_ID, text=text, parse_mode="Markdown")
    await update.message.reply_text("✅ Объявление отправлено в чат.")

# --- Запуск ---
def main():
    Thread(target=run_flask).start()
    
    app_bot = Application.builder().token(BOT_TOKEN).build()
    
    app_bot.add_handler(CommandHandler("start", start_cmd))
    app_bot.add_handler(CommandHandler("settime", set_time))
    app_bot.add_handler(CommandHandler("setprize", set_prize))
    app_bot.add_handler(CommandHandler("price", announce_price))
    
    app_bot.add_handler(CallbackQueryHandler(button_handler))
    
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.ChatType.PRIVATE, on_message))
    
    print("Бот запущен...")
    app_bot.run_polling()

if __name__ == "__main__":
    main()
