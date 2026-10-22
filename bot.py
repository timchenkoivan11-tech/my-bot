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
BOT_TOKEN = "8789333228:AAHbI5m71sKP2PVIHUWGLX6gZ8L2AoRq-lE"
ADMIN_ID = 5522110735  
ALLOWED_CHAT_ID = -1003797267456  
DEFAULT_WIN_CHANCE = 0.1
DEFAULT_COOLDOWN = 60  # Кулдаун по умолчанию (в минутах)
DATA_FILE = "bot_data.json"

DEFAULT_TIMER = 60
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
current_prize = None 
guess_range = None

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "win_chance" not in data: data["win_chance"] = DEFAULT_WIN_CHANCE
            if "timer" not in data: data["timer"] = DEFAULT_TIMER
            if "cooldown" not in data: data["cooldown"] = DEFAULT_COOLDOWN
            return data
    return {"cooldowns": {}, "win_chance": DEFAULT_WIN_CHANCE, "timer": DEFAULT_TIMER, "cooldown": DEFAULT_COOLDOWN}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

data = load_data()

# --- Клавиатуры ---
def get_main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("👑 Запустить Царь горы", callback_data='setup_king')],
        [InlineKeyboardButton("🎯 Запустить Угадай число", callback_data='setup_guess')],
        [InlineKeyboardButton("⏱ 30 сек", callback_data='time_30'), InlineKeyboardButton("⏱ 1 мин", callback_data='time_60')],
        [InlineKeyboardButton("⏱ 3 мин", callback_data='time_180'), InlineKeyboardButton("⏱ 5 мин", callback_data='time_300')],
        [InlineKeyboardButton("🎲 Шанс мишки", callback_data='change_chance')],
        [InlineKeyboardButton("⏱ Кулдаун мишки", callback_data='change_cooldown')],
        [InlineKeyboardButton("📖 Все команды", callback_data='show_commands')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_range_keyboard():
    keyboard = [
        [InlineKeyboardButton("1 - 100", callback_data='range_100')],
        [InlineKeyboardButton("1 - 1000", callback_data='range_1000')]
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
    global current_timer_task, current_king_id, current_king_name, active_event, secret_number, current_prize

    if not update.message or not update.message.text: return
    if update.message.chat_id != ALLOWED_CHAT_ID: return
    
    user = update.message.from_user
    text = update.message.text.strip()
    
    try:
        member = await context.bot.get_chat_member(update.message.chat_id, user.id)
        if member.status in [ChatMember.ADMINISTRATOR, ChatMember.CREATOR] or user.id == ADMIN_ID:
            return  
    except Exception:
        pass

    user_name = f"@{user.username}" if user.username else user.first_name

    # ИВЕНТЫ
    if active_event == 'king':
        if current_timer_task and not current_timer_task.done():
            current_timer_task.cancel()
            if current_king_id != user.id:
                await update.message.reply_text(f"⚔️ {user_name} перебивает {current_king_name} и забирает корону!")
        
        current_king_id = user.id
        current_king_name = user_name

        seconds = data.get("timer", DEFAULT_TIMER)
        current_timer_task = asyncio.create_task(run_timer(update.message.chat_id, user.id, user_name, seconds, current_prize, context))
        return 

    elif active_event == 'guess':
        if text.isdigit():
            guess = int(text)
            if guess == secret_number:
                win_text = (
                    f"🎯 **БИНГО!**\n\n"
                    f"🏆 {user_name} угадал загаданное число (**{secret_number}**)!\n"
                    f"🎁 Победитель забирает приз: **{current_prize}**!\n\n"
                    f"Поздравляем! 🎉"
                )
                await context.bot.send_message(update.message.chat_id, win_text, parse_mode="Markdown")
                active_event = None
                secret_number = None
        return 

    # МИШКА (С динамическим кулдауном)
    chat_id_str = str(update.message.chat_id)
    user_id_str = str(user.id)
    key = f"{chat_id_str}_{user_id_str}"
    
    now = datetime.now()
    cooldowns = data.get("cooldowns", {})
    current_chance = data.get("win_chance", DEFAULT_WIN_CHANCE)
    current_cooldown = data.get("cooldown", DEFAULT_COOLDOWN)

    if current_cooldown > 0:
        last_win = cooldowns.get(key)
        if last_win:
            last_time = datetime.fromisoformat(last_win)
            if now - last_time < timedelta(minutes=current_cooldown):
                return

    if random.random() * 100 < current_chance:
        cooldowns[key] = now.isoformat()
        data["cooldowns"] = cooldowns
        save_data(data)

        text_win = (
            f"🎉 Поздравляю, {user_name}!\n\n"
            f"🧸 Ты выиграл **плюшевого мишку**!\n"
            f"✅ Подарок отправится в течение 2 часов 🕒\n\n"
            f"🚨 Пишите сообщения в чате, и получайте возможность так же залутать подарки."
        )
        bear_photo = "https://i.postimg.cc/qhh1Hndf/IMG_7671.jpg" 
        
        await update.message.reply_photo(photo=bear_photo, caption=text_win, parse_mode="Markdown")

# --- АДМИН-ПАНЕЛЬ ---
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID: return
    context.user_data['setup_step'] = None 
    await update.message.reply_text(
        f"👑 **Админ-панель**\n\n"
        f"Время ивента: **{data.get('timer')} сек.**\n"
        f"Шанс мишки: **{data.get('win_chance')}%**\n"
        f"Кулдаун мишки: **{data.get('cooldown')} мин.**\n\n"
        f"Выбери действие:",
        reply_markup=get_main_menu_keyboard(),
        parse_mode="Markdown"
    )

# --- Обработка нажатий на кнопки ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global active_event
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID: return

    if query.data.startswith('time_'):
        new_time = int(query.data.split('_')[1])
        data["timer"] = new_time
        save_data(data)
        await query.edit_message_text(
            text=f"✅ Таймер изменен на **{new_time} секунд**.",
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown"
        )
    
    elif query.data == 'setup_king':
        if active_event:
            await query.answer("⚠️ Другой ивент уже идет!", show_alert=True)
            return
        context.user_data['setup_step'] = 'king_prize'
        await query.edit_message_text("🎁 **Шаг 1/1:** Напиши в этот чат приз для «Царя горы» (например: 100 рублей):")

    elif query.data == 'setup_guess':
        if active_event:
            await query.answer("⚠️ Другой ивент уже идет!", show_alert=True)
            return
        context.user_data['setup_step'] = 'guess_range'
        await query.edit_message_text("🎯 **Шаг 1/3:** Выбери диапазон чисел:", reply_markup=get_range_keyboard())

    elif query.data in ['range_100', 'range_1000']:
        context.user_data['guess_range'] = 100 if query.data == 'range_100' else 1000
        context.user_data['setup_step'] = 'guess_number'
        await query.edit_message_text(f"✅ Диапазон: 1-{context.user_data['guess_range']}.\n\n🔢 **Шаг 2/3:** Напиши секретное число (от 1 до {context.user_data['guess_range']}):")

    elif query.data == 'end_event':
        active_event = None
        if current_timer_task and not current_timer_task.done(): current_timer_task.cancel()
        await query.message.edit_text("🛑 **Ивент был принудительно завершен.**", parse_mode="Markdown")

    elif query.data == 'change_chance':
        await query.edit_message_text(text="🎲 **Изменение шанса мишки**\n\nНапиши в этот чат число (например: `5` или `0.5`), чтобы изменить шанс.", parse_mode="Markdown")
        context.user_data['setup_step'] = 'set_chance'
    
    elif query.data == 'change_cooldown':
        await query.edit_message_text(text="⏱ **Изменение кулдауна**\n\nНапиши в этот чат число минут (например: `30`, `5`). Чтобы отключить кулдаун, напиши `0`.", parse_mode="Markdown")
        context.user_data['setup_step'] = 'set_cooldown'

    elif query.data == 'show_commands':
        commands_text = (
            "📚 **Все доступные команды:**\n\n"
            "🔹 `/startguess` — Запустить «Угадай число»\n"
            "🔹 `/startking` — Запустить «Царь горы»\n"
            "🔹 `/stop` — Остановить любой ивент\n"
            "🔹 `/price <звезды>` — Объявить цену за сообщения\n\n"
            "💡 *Все настройки призов и чисел делаются в диалоге с ботом.*"
        )
        back_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data='back_to_menu')]])
        await query.edit_message_text(text=commands_text, reply_markup=back_keyboard, parse_mode="Markdown")

    elif query.data == 'back_to_menu':
        await query.edit_message_text(
            text=f"👑 **Админ-панель**\n\nВремя: **{data.get('timer')} сек.**\nШанс: **{data.get('win_chance')}%**\nКулдаун: **{data.get('cooldown')} мин.**",
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown"
        )

# --- ОБРАБОТКА ТЕКСТА ОТ АДМИНА (пошаговая настройка) ---
async def admin_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global active_event, secret_number, current_prize
    
    if update.message.from_user.id != ADMIN_ID or update.message.chat.type != 'private': return
    
    step = context.user_data.get('setup_step')
    text = update.message.text.strip()

    if step == 'set_chance':
        try:
            new_chance = float(text.replace(',', '.'))
            data["win_chance"] = new_chance
            save_data(data)
            await update.message.reply_text(f"✅ Шанс мишки изменен на **{new_chance}%**.", parse_mode="Markdown")
            context.user_data['setup_step'] = None
        except ValueError:
            await update.message.reply_text("❌ Это не число. Попробуй еще раз.")
        return
    
    if step == 'set_cooldown':
        try:
            new_cd = int(text)
            if new_cd < 0: raise ValueError
            data["cooldown"] = new_cd
            save_data(data)
            await update.message.reply_text(f"✅ Кулдаун изменен на **{new_cd} мин.** (0 = отключен).", parse_mode="Markdown")
            context.user_data['setup_step'] = None
        except ValueError:
            await update.message.reply_text("❌ Нужно ввести целое число минут (например 5 или 0).")
        return

    if step == 'king_prize':
        current_prize = text
        active_event = 'king'
        context.user_data['setup_step'] = None
        seconds = data.get("timer", DEFAULT_TIMER)
        
        event_text = f"📣 **Ивент «Царь горы» начался!**\n\n⏳ Цель: **{seconds} сек.**\n\n🎁 Приз: **{current_prize}**\n\n👉 *Напиши сообщение, чтобы запустить таймер!*"
        end_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🛑 Завершить ивент", callback_data='end_event')]])
        await context.bot.send_message(chat_id=ALLOWED_CHAT_ID, text=event_text, reply_markup=end_keyboard, parse_mode="Markdown")
        await update.message.reply_text("✅ Царь горы запущен в чате! (Мишка на паузе)")
        return

    elif step == 'guess_number':
        if not text.isdigit():
            await update.message.reply_text("❌ Нужно ввести цифру. Попробуй еще раз.")
            return
        
        num = int(text)
        max_range = context.user_data.get('guess_range', 1000)
        if num < 1 or num > max_range:
            await update.message.reply_text(f"❌ Число должно быть от 1 до {max_range}!")
            return
            
        secret_number = num
        context.user_data['setup_step'] = 'guess_prize'
        await update.message.reply_text("✅ Число принято!\n\n🎁 **Шаг 3/3:** Напиши приз для победителя:")
        return

    elif step == 'guess_prize':
        current_prize = text
        active_event = 'guess'
        context.user_data['setup_step'] = None
        
        event_text = f"🎯 **Ивент «Угадай число» начался!**\n\n🎁 Приз: **{current_prize}**\n\n👉 Пиши число от **1 до {context.user_data.get('guess_range', 1000)}** — кто угадает, тот получит приз!"
        end_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🛑 Завершить ивент", callback_data='end_event')]])
        await context.bot.send_message(chat_id=ALLOWED_CHAT_ID, text=event_text, reply_markup=end_keyboard, parse_mode="Markdown")
        await update.message.reply_text(f"✅ Игра запущена! Загаданное число: {secret_number} (сохрани в тайне).")
        return

# --- Текстовые команды ---
async def cmd_start_guess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID: return
    if active_event:
        await update.message.reply_text("⚠️ Другой ивент уже идет! Останови его (/stop).")
        return
    context.user_data['setup_step'] = 'guess_range'
    await update.message.reply_text("🎯 **Шаг 1/3:** Выбери диапазон чисел:", reply_markup=get_range_keyboard())

async def cmd_start_king(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID: return
    if active_event:
        await update.message.reply_text("⚠️ Другой ивент уже идет! Останови его (/stop).")
        return
    context.user_data['setup_step'] = 'king_prize'
    await update.message.reply_text("🎁 **Шаг 1/1:** Напиши приз для «Царя горы» (например: 100 рублей):")

async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global active_event, secret_number, current_timer_task
    if update.message.from_user.id != ADMIN_ID: return
    if not active_event:
        await update.message.reply_text("🤷‍♂️ Сейчас нет активных ивентов.")
        return

    active_event = None
    secret_number = None
    if current_timer_task and not current_timer_task.done():
        current_timer_task.cancel()
        
    await context.bot.send_message(chat_id=ALLOWED_CHAT_ID, text="🛑 **Ивент был остановлен администратором.**", parse_mode="Markdown")
    await update.message.reply_text("✅ Ивент остановлен.")

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
    app_bot.add_handler(CommandHandler("startguess", cmd_start_guess))
    app_bot.add_handler(CommandHandler("startking", cmd_start_king))
    app_bot.add_handler(CommandHandler("stop", cmd_stop))
    app_bot.add_handler(CommandHandler("price", announce_price))
    
    app_bot.add_handler(CallbackQueryHandler(button_handler))
    
    app_bot.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE & filters.User(user_id=int(ADMIN_ID)), admin_text_handler))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.ChatType.PRIVATE, on_message))
    
    print("Бот запущен...")
    app_bot.run_polling()

if __name__ == "__main__":
    main()
