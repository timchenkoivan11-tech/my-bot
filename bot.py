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
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = 5522110735  

CHAT_MAIN = -1003797267456      # Основной чат (мишки, ивенты)
CHAT_CASINO = -5431231286       # Новый чат (казино)

DEFAULT_WIN_CHANCE = 0.4
DEFAULT_COOLDOWN = 60  
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

# Глобальные переменные для основного чата
active_event = None  
current_timer_task = None
current_king_id = None
current_king_name = None
secret_number = None
current_prize = None 
guess_range = None
lucky777_prize = None

# Хранилище для активных игр в казино
casino_games = {} 

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
        [InlineKeyboardButton("🎰 Запустить Лудку 777", callback_data='setup_lucky777')],
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

def get_back_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад в меню", callback_data='back_to_menu')]])

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
        msg = await context.bot.send_message(chat_id, text, parse_mode="Markdown")
        
        try:
            await context.bot.pin_chat_message(chat_id=chat_id, message_id=msg.message_id, disable_notification=True)
        except Exception:
            pass
            
        active_event = None 
        
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logging.error(f"Ошибка в таймере: {e}")

# --- Обработка ТЕКСТОВЫХ сообщений ---
async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_timer_task, current_king_id, current_king_name, active_event, secret_number, current_prize

    if not update.message or not update.message.text: return
    
    chat_id = update.message.chat_id
    if chat_id not in [CHAT_MAIN, CHAT_CASINO]: return
    
    user = update.message.from_user
    text = update.message.text.strip()
    
    if user.id == ADMIN_ID: return

    try:
        member = await context.bot.get_chat_member(chat_id, user.id)
        if member.status in ['administrator', 'creator', ChatMember.ADMINISTRATOR, ChatMember.CREATOR]:
            return  
    except Exception:
        pass

    user_name = f"@{user.username}" if user.username else user.first_name

    # Если это КАЗИНО - обычный текст игнорируется
    if chat_id == CHAT_CASINO:
        return

    # === ЛОГИКА ОСНОВНОГО ЧАТА ===
    if active_event == 'king':
        seconds = data.get("timer", DEFAULT_TIMER)
        if current_timer_task and not current_timer_task.done():
            current_timer_task.cancel()
            if current_king_id != user.id:
                await update.message.reply_text(f"⚔️ {user_name} перебивает {current_king_name}! Он забирает корону. Новый таймер на {seconds} секунд пошел!")
        else:
            await update.message.reply_text(f"👑 {user_name} первый! Он держит корону. Пошел таймер на {seconds} секунд! Успейте перебить!")
        
        current_king_id = user.id
        current_king_name = user_name
        current_timer_task = asyncio.create_task(run_timer(chat_id, user.id, user_name, seconds, current_prize, context))
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
                msg = await context.bot.send_message(chat_id, win_text, parse_mode="Markdown")
                try:
                    await context.bot.pin_chat_message(chat_id=chat_id, message_id=msg.message_id, disable_notification=True)
                except Exception:
                    pass
                active_event = None
                secret_number = None
        return 

    # === МИШКА (сработает только в основном чате) ===
    key = f"{chat_id}_{user.id}"
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
            f"🧸 Ты выиграл **мишку**!\n"
            f"✅ Подарок отправится в течение 2 часов 🕒\n\n"
            f"🚨 Пишите сообщения в чате, и получайте возможность так же залутать подарки."
        )
        bear_photo = "https://i.postimg.cc/pXvngzR7/72BE0C1A-3E12-494D-895E-369895A4E8FF.png"
        
        try:
            msg = await update.message.reply_photo(photo=bear_photo, caption=text_win, parse_mode="Markdown")
        except Exception:
            msg = await update.message.reply_text(text_win, parse_mode="Markdown")
        
        try:
            await context.bot.pin_chat_message(chat_id=chat_id, message_id=msg.message_id, disable_notification=True)
            await context.bot.send_message(ADMIN_ID, text=f"🔔 **Уведомление!**\n\n{user_name} выиграл мишку в основном чате!", parse_mode="Markdown")
        except Exception:
            pass

# --- Обработка ДАЙСОВ (Слоты) ---
async def on_dice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global active_event, lucky777_prize
    if not update.message or not update.message.dice: return
    
    chat_id = update.message.chat_id
    if chat_id not in [CHAT_MAIN, CHAT_CASINO]: return

    user = update.message.from_user
    if user.id == ADMIN_ID: return
    
    try:
        member = await context.bot.get_chat_member(chat_id, user.id)
        if member.status in ['administrator', 'creator', ChatMember.ADMINISTRATOR, ChatMember.CREATOR]:
            return  
    except Exception:
        pass

    user_name = f"@{user.username}" if user.username else user.first_name
    dice = update.message.dice

    # ==========================================
    # НОВЫЙ ЧАТ: КАЗИНО
    # ==========================================
    if chat_id == CHAT_CASINO:
        if dice.emoji == '🎰':
            val = dice.value
            
            # 1, 22, 43 - это 3 Бара, 3 Винограда, 3 Лимона
            if val in [1, 22, 43]:
                prizes = ['❌', '❌', '🧸']
                random.shuffle(prizes)
                buttons = []
                for p in prizes:
                    if p == '🧸':
                        buttons.append(InlineKeyboardButton("❓", callback_data="casino_win_🧸_15"))
                    else:
                        buttons.append(InlineKeyboardButton("❓", callback_data="casino_lose"))
                        
                keyboard = InlineKeyboardMarkup([buttons])
                msg = await update.message.reply_text(
                    f"✨ {user_name} выбил три в ряд!\n\nПеред тобой 3 ячейки — в одной из них мишка 🧸. Выбирай!",
                    reply_markup=keyboard
                )
                casino_games[msg.message_id] = {'user_id': user.id, 'user_name': user_name}
                
            # 64 - это 777
            elif val == 64:
                # 5 гарантированных призов
                prizes = ['🧸_15', '🌷_25', '🎂_50', '💍_100', '💎_150']
                random.shuffle(prizes)
                buttons = [InlineKeyboardButton("❓", callback_data=f"casino_win_{p}") for p in prizes]
                keyboard = InlineKeyboardMarkup([buttons])
                
                msg = await update.message.reply_text(
                    f"🎰 **ДЖЕКПОТ 777!** 🎰\n\n🏆 {user_name} сорвал куш!\nВыбирай одну из 5 ячеек — здесь **все** ячейки выигрышные!",
                    reply_markup=keyboard
                )
                casino_games[msg.message_id] = {'user_id': user.id, 'user_name': user_name}
        return 

    # ==========================================
    # СТАРЫЙ ЧАТ: ИВЕНТ ЛУДКА 777 (Админский)
    # ==========================================
    if chat_id == CHAT_MAIN:
        if active_event == 'lucky777' and dice.emoji == '🎰':
            if dice.value == 64:
                win_text = (
                    f"🎰 **ДЖЕКПОТ 777!**\n\n"
                    f"🏆 {user_name} выбил три семерки и забирает приз:\n"
                    f"🎁 **{lucky777_prize}**!\n\nПоздравляем! 🎉"
                )
                msg = await context.bot.send_message(chat_id, win_text, parse_mode="Markdown")
                try:
                    await context.bot.pin_chat_message(chat_id=chat_id, message_id=msg.message_id, disable_notification=True)
                    await context.bot.send_message(ADMIN_ID, text=f"🔔 **Джекпот!**\n\n{user_name} выбил 777: {lucky777_prize}", parse_mode="Markdown")
                except Exception:
                    pass
                active_event = None
                lucky777_prize = None

# --- ОБРАБОТКА КНОПОК КАЗИНО ---
async def casino_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    msg_id = query.message.message_id
    
    if msg_id not in casino_games:
        await query.answer("Эта игра уже завершена.", show_alert=True)
        return

    game = casino_games[msg_id]
    
    if query.from_user.id != game['user_id']:
        await query.answer("Это не твоя игра! Кидай свои слоты.", show_alert=True)
        return

    await query.answer()
    del casino_games[msg_id] 
    
    if query.data == 'casino_lose':
        await query.message.edit_text(f"😔 Увы, {game['user_name']} попал на пустую ячейку. В следующий раз повезет!", parse_mode="Markdown")
    elif query.data.startswith('casino_win_'):
        prize_data = query.data.split('_')[2:]
        emoji = prize_data[0]
        price = prize_data[1] if len(prize_data) > 1 else "?"
        
        win_text = (
            f"🎉 **ПОБЕДА!**\n\n"
            f"🏆 {game['user_name']} открыл ячейку и забирает:\n"
            f"🎁 **{emoji} Подарок** (Цена: {price} ⭐)\n\n"
            f"Свяжитесь с админом для получения! @твой_ник_админа"
        )
        await query.message.edit_text(win_text, parse_mode="Markdown")
        
        # Вот тут то самое уведомление с указанием чата
        try:
            await context.bot.send_message(
                ADMIN_ID, 
                text=f"🎰 **ВЫИГРЫШ В КАЗИНО (Чат №2)!**\n\n🏆 {game['user_name']} выиграл {emoji} (за {price} звезд).\n\n👉 Не забудь выдать приз в чате казино!", 
                parse_mode="Markdown"
            )
        except Exception:
            pass

# --- АДМИН-ПАНЕЛЬ ---
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID: return
    context.user_data['setup_step'] = None 
    await update.message.reply_text(
        f"👑 **Админ-панель**\n\nВремя ивента: **{data.get('timer')} сек.**\nШанс мишки: **{data.get('win_chance')}%**\nКулдаун мишки: **{data.get('cooldown')} мин.**\n\nВыбери действие:",
        reply_markup=get_main_menu_keyboard(),
        parse_mode="Markdown"
    )

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat_id != CHAT_MAIN and update.message.chat.type != 'private': return
    await update.message.reply_text(
        f"🎲 Шанс на мишку: **{data.get('win_chance', DEFAULT_WIN_CHANCE)}%** с каждого сообщения.\n⏱ Кулдаун после победы: **{data.get('cooldown', DEFAULT_COOLDOWN)} мин.**",
        parse_mode="Markdown"
    )

# --- ОБРАБОТКА КНОПОК АДМИНКИ ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global active_event
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID: return

    if query.data.startswith('time_'):
        new_time = int(query.data.split('_')[1])
        data["timer"] = new_time
        save_data(data)
        await query.edit_message_text(text=f"✅ Таймер изменен на **{new_time} секунд**.", reply_markup=get_main_menu_keyboard(), parse_mode="Markdown")
    
    elif query.data == 'setup_king':
        if active_event:
            await query.answer("⚠️ Другой ивент уже идет!", show_alert=True)
            return
        context.user_data['setup_step'] = 'king_prize'
        await query.edit_message_text("🎁 **Шаг 1/1:** Напиши в этот чат приз для «Царя горы»:", reply_markup=get_back_keyboard())

    elif query.data == 'setup_guess':
        if active_event:
            await query.answer("⚠️ Другой ивент уже идет!", show_alert=True)
            return
        context.user_data['setup_step'] = 'guess_range'
        await query.edit_message_text("🎯 **Шаг 1/3:** Выбери диапазон чисел:", reply_markup=get_range_keyboard())

    elif query.data == 'setup_lucky777':
        if active_event:
            await query.answer("⚠️ Другой ивент уже идет!", show_alert=True)
            return
        context.user_data['setup_step'] = 'lucky777_prize'
        await query.edit_message_text("🎁 **Шаг 1/2:** Напиши приз для «Лудки 777»:", reply_markup=get_back_keyboard())

    elif query.data in ['range_100', 'range_1000']:
        context.user_data['guess_range'] = 100 if query.data == 'range_100' else 1000
        context.user_data['setup_step'] = 'guess_number'
        await query.edit_message_text(f"✅ Диапазон: 1-{context.user_data['guess_range']}.\n\n🔢 **Шаг 2/3:** Напиши секретное число:", reply_markup=get_back_keyboard())

    elif query.data == 'end_event':
        active_event = None
        if current_timer_task and not current_timer_task.done(): current_timer_task.cancel()
        await query.message.edit_text("🛑 **Ивент был принудительно завершен.**", parse_mode="Markdown")

    elif query.data == 'change_chance':
        await query.edit_message_text(text="🎲 **Изменение шанса мишки**\n\nНапиши число (например: `5` или `0.5`):", reply_markup=get_back_keyboard(), parse_mode="Markdown")
        context.user_data['setup_step'] = 'set_chance'
    
    elif query.data == 'change_cooldown':
        await query.edit_message_text(text="⏱ **Изменение кулдауна**\n\nНапиши число минут (например: `30`). Чтобы отключить, напиши `0`.", reply_markup=get_back_keyboard(), parse_mode="Markdown")
        context.user_data['setup_step'] = 'set_cooldown'

    elif query.data == 'show_commands':
        commands_text = (
            "📚 **Все доступные команды:**\n\n"
            "🔹 `/startguess` — Запустить «Угадай число»\n"
            "🔹 `/startking` — Запустить «Царь горы»\n"
            "🔹 `/stop` — Остановить любой ивент\n"
            "🔹 `/stats` — Узнать шанс мишки\n"
            "🔹 `/price <звезды>` — Объявить цену за сообщения\n\n"
        )
        await query.edit_message_text(text=commands_text, reply_markup=get_back_keyboard(), parse_mode="Markdown")

    elif query.data == 'back_to_menu':
        context.user_data['setup_step'] = None
        await query.edit_message_text(text=f"👑 **Админ-панель**\n\nВремя: **{data.get('timer')} сек.**\nШанс: **{data.get('win_chance')}%**\nКулдаун: **{data.get('cooldown')} мин.**", reply_markup=get_main_menu_keyboard(), parse_mode="Markdown")

# --- ОБРАБОТКА ТЕКСТА ОТ АДМИНА ---
async def admin_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global active_event, secret_number, current_prize, current_king_id, current_king_name, lucky777_prize
    
    if update.message.from_user.id != ADMIN_ID or update.message.chat.type != 'private': return
    
    step = context.user_data.get('setup_step')
    text = update.message.text.strip()

    if step == 'set_chance':
        try:
            new_chance = float(text.replace(',', '.'))
            data["win_chance"] = new_chance
            save_data(data)
            await update.message.reply_text(f"✅ Шанс изменен на **{new_chance}%**.", reply_markup=get_main_menu_keyboard(), parse_mode="Markdown")
            context.user_data['setup_step'] = None
        except ValueError:
            await update.message.reply_text("❌ Это не число.", reply_markup=get_back_keyboard())
        return
    
    if step == 'set_cooldown':
        try:
            new_cd = int(text)
            if new_cd < 0: raise ValueError
            data["cooldown"] = new_cd
            save_data(data)
            await update.message.reply_text(f"✅ Кулдаун изменен на **{new_cd} мин.**", reply_markup=get_main_menu_keyboard(), parse_mode="Markdown")
            context.user_data['setup_step'] = None
        except ValueError:
            await update.message.reply_text("❌ Нужно целое число минут.", reply_markup=get_back_keyboard())
        return

    if step == 'king_prize':
        current_prize = text
        active_event = 'king'
        current_king_id = None 
        current_king_name = None
        context.user_data['setup_step'] = None
        seconds = data.get("timer", DEFAULT_TIMER)
        event_text = f"📣 **Ивент «Царь горы» начался!**\n\n⏳ Цель: **{seconds} сек.**\n\n🎁 Приз: **{current_prize}**\n\n👉 *Напиши сообщение!*"
        end_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🛑 Завершить ивент", callback_data='end_event')]])
        msg = await context.bot.send_message(chat_id=CHAT_MAIN, text=event_text, reply_markup=end_keyboard, parse_mode="Markdown")
        try: await context.bot.pin_chat_message(chat_id=CHAT_MAIN, message_id=msg.message_id, disable_notification=True)
        except: pass
        await update.message.reply_text("✅ Царь горы запущен!", reply_markup=get_main_menu_keyboard())
        return

    elif step == 'guess_number':
        if not text.isdigit(): return
        num = int(text)
        max_range = context.user_data.get('guess_range', 1000)
        if num < 1 or num > max_range: return
        secret_number = num
        context.user_data['setup_step'] = 'guess_prize'
        await update.message.reply_text("✅ Число принято!\n\n🎁 **Шаг 3/3:** Напиши приз:", reply_markup=get_back_keyboard())
        return

    elif step == 'guess_prize':
        current_prize = text
        active_event = 'guess'
        context.user_data['setup_step'] = None
        event_text = f"🎯 **Ивент «Угадай число» начался!**\n\n🎁 Приз: **{current_prize}**\n\n👉 Пиши число от **1 до {context.user_data.get('guess_range', 1000)}**!"
        end_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🛑 Завершить ивент", callback_data='end_event')]])
        msg = await context.bot.send_message(chat_id=CHAT_MAIN, text=event_text, reply_markup=end_keyboard, parse_mode="Markdown")
        try: await context.bot.pin_chat_message(chat_id=CHAT_MAIN, message_id=msg.message_id, disable_notification=True)
        except: pass
        await update.message.reply_text(f"✅ Игра запущена! Загадано: {secret_number}", reply_markup=get_main_menu_keyboard())
        return
        
    elif step == 'lucky777_prize':
        context.user_data['lucky777_prize'] = text
        context.user_data['setup_step'] = 'lucky777_price'
        await update.message.reply_text("✅ Приз принят!\n\n💰 **Шаг 2/2:** Напиши цену (например: `17 ⭐`):", reply_markup=get_back_keyboard())
        return
        
    elif step == 'lucky777_price':
        price = text
        lucky777_prize = context.user_data.get('lucky777_prize', 'Секретный приз')
        active_event = 'lucky777'
        context.user_data['setup_step'] = None
        event_text = f"🎰 **Лудка 777 запущена!**\n\n🎁 Приз: **{lucky777_prize}**\n⭐ Цена: {price}\n\n🥇 Кто выбьет 777, тот забирает приз!"
        end_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🛑 Завершить ивент", callback_data='end_event')]])
        msg = await context.bot.send_message(chat_id=CHAT_MAIN, text=event_text, reply_markup=end_keyboard, parse_mode="Markdown")
        try: await context.bot.pin_chat_message(chat_id=CHAT_MAIN, message_id=msg.message_id, disable_notification=True)
        except: pass
        await update.message.reply_text("✅ Лудка 777 запущена!", reply_markup=get_main_menu_keyboard())
        return

# --- Текстовые команды ---
async def cmd_start_guess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID: return
    if active_event: return
    context.user_data['setup_step'] = 'guess_range'
    await update.message.reply_text("🎯 **Шаг 1/3:** Выбери диапазон:", reply_markup=get_range_keyboard())

async def cmd_start_king(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID: return
    if active_event: return
    context.user_data['setup_step'] = 'king_prize'
    await update.message.reply_text("🎁 **Шаг 1/1:** Напиши приз для «Царя горы»:", reply_markup=get_back_keyboard())

async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global active_event, secret_number, current_timer_task
    if update.message.from_user.id != ADMIN_ID: return
    if not active_event: return
    active_event = None
    secret_number = None
    if current_timer_task and not current_timer_task.done(): current_timer_task.cancel()
    await context.bot.send_message(chat_id=CHAT_MAIN, text="🛑 **Ивент остановлен.**", parse_mode="Markdown")
    await update.message.reply_text("✅ Ивент остановлен.", reply_markup=get_main_menu_keyboard())

async def announce_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID: return
    if not context.args: return
    price = context.args[0]
    text = f"📢 **ВНИМАНИЕ!**\n\nАдминистратор установил цену за сообщение: **{price} ⭐**."
    await context.bot.send_message(chat_id=CHAT_MAIN, text=text, parse_mode="Markdown")
    await update.message.reply_text("✅ Объявление отправлено.")

def main():
    Thread(target=run_flask).start()
    app_bot = Application.builder().token(BOT_TOKEN).build()
    
    app_bot.add_handler(CommandHandler("start", start_cmd))
    app_bot.add_handler(CommandHandler("startguess", cmd_start_guess))
    app_bot.add_handler(CommandHandler("startking", cmd_start_king))
    app_bot.add_handler(CommandHandler("stop", cmd_stop))
    app_bot.add_handler(CommandHandler("stats", stats)) 
    app_bot.add_handler(CommandHandler("price", announce_price))
    
    # Обработчик кнопок админки
    app_bot.add_handler(CallbackQueryHandler(button_handler, pattern="^(time_|setup_|range_|end_event|change_|show_commands|back_to_menu)"))
    # Обработчик кнопок казино
    app_bot.add_handler(CallbackQueryHandler(casino_button_handler, pattern="^casino_"))
    
    app_bot.add_handler(MessageHandler(filters.Dice.ALL, on_dice))
    app_bot.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE & filters.User(user_id=int(ADMIN_ID)), admin_text_handler))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.ChatType.PRIVATE, on_message))
    
    print("Бот запущен...")
    app_bot.run_polling()

if __name__ == "__main__":
    main()
