import logging
import random
import json
import os
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMember
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler, CallbackQueryHandler
from flask import Flask
from threading import Thread

# ================= НАСТРОЙКИ =================
BOT_TOKEN = "СЮДА_ВСТАВЬ_СВОЙ_ТОКЕН"
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

# Глобальные переменные для игр
active_event = None  
current_timer_task = None
current_king_id = None
current_king_name = None
secret_number = None

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

# --- Клавиатура для главного меню админа ---
def get_main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("👑 Запустить Царь горы", callback_data='start_king')],
        [InlineKeyboardButton("🎯 Запустить Угадай число", callback_data='start_guess')],
        [InlineKeyboardButton("⏱ 30 сек", callback_data='time_30'), InlineKeyboardButton("⏱ 1 мин", callback_data='time_60')],
        [InlineKeyboardButton("⏱ 3 мин", callback_data='time_180'), InlineKeyboardButton("⏱ 5 мин", callback_data='time_300')],
        [InlineKeyboardButton("📖 Все команды", callback_data='show_commands')]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- Таймер для Царя горы ---
async def run_timer(chat_id, user_id, user_name, seconds, prize, context):
    global current_king_id, current_king_name, active_event
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
            f"👑 **ИВЕНТ ЗАВЕРШЕН!**\n\n"
            f"🏆 Победитель: {user_name}\n"
            f"🎁 Он забирает приз: **{prize}**!\n\n"
            f"Поздравляем! 🎉"
        )
        await context.bot.send_message(chat_id, text, parse_mode="Markdown")
        active_event = None 
        
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logging.error(f"Ошибка в таймере: {e}")

# --- Обработка сообщений в чате ---
async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_timer_task, current_king_id, current_king_name, active_event, secret_number

    if not update.message or not update.message.text: return
    if update.message.chat_id != ALLOWED_CHAT_ID: return
    if not active_event: return  
    
    user = update.message.from_user
    text = update.message.text.strip()
    
    try:
        member = await context.bot.get_chat_member(update.message.chat_id, user.id)
        if member.status in [ChatMember.ADMINISTRATOR, ChatMember.CREATOR] or user.id == ADMIN_ID:
            return  
    except Exception:
        pass

    user_name = f"@{user.username}" if user.username else user.first_name

    if active_event == 'king':
        if current_timer_task and not current_timer_task.done():
            current_timer_task.cancel()
            if current_king_id != user.id:
                await update.message.reply_text(f"⚔️ {user_name} перебивает {current_king_name} и забирает корону!")
        
        current_king_id = user.id
        current_king_name = user_name

        seconds = data.get("timer", DEFAULT_TIMER)
        prize = data.get("prize", DEFAULT_PRIZE)
        current_timer_task = asyncio.create_task(run_timer(update.message.chat_id, user.id, user_name, seconds, prize, context))

    elif active_event == 'guess':
        if text.isdigit():
            guess = int(text)
            if guess == secret_number:
                prize = data.get("prize", DEFAULT_PRIZE)
                win_text = (
                    f"🎯 **БИНГО!**\n\n"
                    f"🏆 {user_name} угадал загаданное число (**{secret_number}**)!\n"
                    f"🎁 Победитель забирает приз: **{prize}**!\n\n"
                    f"Поздравляем! 🎉"
                )
                await context.bot.send_message(update.message.chat_id, win_text, parse_mode="Markdown")
                active_event = None
                secret_number = None

# --- АДМИН-ПАНЕЛЬ ---
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID: return
    await update.message.reply_text(
        f"👑 **Админ-панель**\n\n"
        f"Текущее время: **{data.get('timer')} сек.**\n"
        f"Текущий приз: **{data.get('prize')}**\n\n"
        f"Выбери ивент для запуска:",
        reply_markup=get_main_menu_keyboard(),
        parse_mode="Markdown"
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global active_event, secret_number, current_timer_task
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID: return

    if query.data.startswith('time_'):
        new_time = int(query.data.split('_')[1])
        data["timer"] = new_time
        save_data(data)
        await query.edit_message_text(
            text=f"✅ Таймер изменен на **{new_time} секунд**.\nВыбери ивент:",
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown"
        )
    
    elif query.data == 'start_king':
        if active_event:
            await query.answer("⚠️ Другой ивент уже идет!", show_alert=True)
            return
            
        active_event = 'king'
        seconds = data.get("timer", DEFAULT_TIMER)
        prize = data.get("prize", DEFAULT_PRIZE)
        
        event_text = (
            f"📣 **Ивент «Царь горы» начался!**\n\n"
            f"⏳ Цель: **{seconds} сек.** без перебива\n\n"
            f"🎁 Приз: **{prize}**\n\n"
            f"👉 *Напиши любое сообщение в чат, чтобы запустить таймер!*"
        )
        end_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🛑 Завершить ивент", callback_data='end_event')]])
        
        await context.bot.send_message(chat_id=ALLOWED_CHAT_ID, text=event_text, reply_markup=end_keyboard, parse_mode="Markdown")
        await query.edit_message_text("✅ Царь горы запущен!", reply_markup=get_main_menu_keyboard())

    elif query.data == 'start_guess':
        if active_event:
            await query.answer("⚠️ Другой ивент уже идет!", show_alert=True)
            return
            
        active_event = 'guess'
        secret_number = random.randint(1, 1000)  
        prize = data.get("prize", DEFAULT_PRIZE)
        
        event_text = (
            f"🎯 **Ивент «Угадай число» начался!**\n\n"
            f"🎁 Приз: **{prize}**\n\n"
            f"👉 Пиши в чат число от **1 до 1000** — кто угадает, тот и получит приз!"
        )
        end_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🛑 Завершить ивент", callback_data='end_event')]])
        
        await context.bot.send_message(chat_id=ALLOWED_CHAT_ID, text=event_text, reply_markup=end_keyboard, parse_mode="Markdown")
        await query.edit_message_text("✅ Угадай число запущен!", reply_markup=get_main_menu_keyboard())

    elif query.data == 'end_event':
        if query.from_user.id != ADMIN_ID:
            await query.answer("⛔ У вас нет прав!", show_alert=True)
            return
        
        active_event = None
        secret_number = None
        if current_timer_task and not current_timer_task.done():
            current_timer_task.cancel()
            
        await query.message.edit_text("🛑 **Ивент был принудительно завершен администратором.**", parse_mode="Markdown")

    elif query.data == 'show_commands':
        commands_text = (
            "📚 **Команды (вводить в личке с ботом):**\n\n"
            "🔹 `/setprize <текст>` — Изменить приз\n"
            "🔹 `/settime <сек>` — Задать таймер для Царя горы\n"
            "🔹 `/price <звезды>` — Объявить цену за сообщения\n\n"
            "💡 *Для запуска игр используй кнопки в меню.*"
        )
        back_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data='back_to_menu')]])
        await query.edit_message_text(text=commands_text, reply_markup=back_keyboard, parse_mode="Markdown")

    elif query.data == 'back_to_menu':
        await query.edit_message_text(
            text=f"👑 **Админ-панель**\n\nТекущее время: **{data.get('timer')} сек.**\nПриз: **{data.get('prize')}**",
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown"
        )

async def set_prize(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID: return
    if not context.args:
        await update.message.reply_text("❌ Пиши так: `/setprize Плюшевый мишка`")
        return
    new_prize = " ".join(context.args)
    data["prize"] = new_prize
    save_data(data)
    await update.message.reply_text(f"✅ Приз изменен на: {new_prize}")

async def announce_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID: return
    if not context.args:
        await update.message.reply_text("❌ Пиши так: `/price 5`")
        return
    price = context.args[0]
    text = f"📢 **ВНИМАНИЕ!**\n\nАдминистратор установил цену за сообщение: **{price} ⭐**."
    await context.bot.send_message(chat_id=ALLOWED_CHAT_ID, text=text, parse_mode="Markdown")
    await update.message.reply_text("✅ Объявление отправлено.")

def main():
    Thread(target=run_flask).start()
    app_bot = Application.builder().token(BOT_TOKEN).build()
    
    app_bot.add_handler(CommandHandler("start", start_cmd))
    app_bot.add_handler(CommandHandler("setprize", set_prize))
    app_bot.add_handler(CommandHandler("price", announce_price))
    app_bot.add_handler(CallbackQueryHandler(button_handler))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.ChatType.PRIVATE, on_message))
    
    print("Бот запущен...")
    app_bot.run_polling()

if __name__ == "__main__":
    main()
