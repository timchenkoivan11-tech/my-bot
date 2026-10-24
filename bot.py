import logging
import random
import json
import os
import asyncio
import html
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMember
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler, CallbackQueryHandler
from flask import Flask
from threading import Thread

# ================= НАСТРОЙКИ =================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = 5522110735  

CHAT_MAIN = -1003797267456      
CHAT_CASINO = -5431231286       

DEFAULT_WIN_CHANCE = 0.4
DEFAULT_COOLDOWN = 60  
DATA_FILE = "bot_data.json"
DEFAULT_TIMER = 60
# =============================================

logging.basicConfig(level=logging.INFO)

app = Flask('')
@app.route('/')
def home():
    return "Bot is alive!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

active_event = None  
current_timer_task = None
current_king_id = None
current_king_name = None
secret_number = None
current_prize = None 
guess_range = None
lucky777_prize = None
casino_games = {} 

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            data["win_chance"] = DEFAULT_WIN_CHANCE
            data["cooldown"] = DEFAULT_COOLDOWN
            if "timer" not in data: data["timer"] = DEFAULT_TIMER
            return data
    return {"cooldowns": {}, "win_chance": DEFAULT_WIN_CHANCE, "timer": DEFAULT_TIMER, "cooldown": DEFAULT_COOLDOWN}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

data = load_data()

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

async def run_timer(chat_id, user_id, user_name, seconds, prize, context):
    global current_king_id, current_king_name, active_event
    try:
        if seconds > 30:
            await asyncio.sleep(seconds - 30)
            await context.bot.send_message(chat_id, f"⏳ **Осталось 30 секунд!**\nКорону держит {user_name}. Успей перебить!", parse_mode="Markdown")
        if seconds > 20:
            await asyncio.sleep(10)
            await context.bot.send_message(chat_id, f"⏳ **Осталось 20 секунд!**", parse_mode="Markdown")
        if seconds > 10:
            await asyncio.sleep(10)
            await context.bot.send_message(chat_id, f"🚨 **Внимание! Осталось 10 секунд!**", parse_mode="Markdown")

        for i in range(5, 0, -1):
            await asyncio.sleep(1)
            await context.bot.send_message(chat_id, f"🔥 **{i}**...", parse_mode="Markdown")

        await asyncio.sleep(1)
        text = (
            f"👑 **ИВЕНТ ЗАВЕРШЕН!** 👑\n\n"
            f"🏆 Победитель: {user_name}\n"
            f"🎁 Он забирает приз: **{prize}**!\n\n"
            f"🎉 Поздравляем!"
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

async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_timer_task, current_king_id, current_king_name, active_event, secret_number, current_prize

    if not update.message or not update.message.text: 
        return
    
    chat_id = update.message.chat_id
    if chat_id not in [CHAT_MAIN, CHAT_CASINO]: 
        return
    
    user = update.message.from_user
    text = update.message.text.strip()
    
    if user.id == ADMIN_ID: 
        return

    try:
        member = await context.bot.get_chat_member(chat_id, user.id)
        if member.status in ['administrator', 'creator', ChatMember.ADMINISTRATOR, ChatMember.CREATOR]:
            return  
    except Exception:
        pass

    user_name = f"@{user.username}" if user.username else user.first_name
    
    if chat_id == CHAT_CASINO: 
        return

    if active_event == 'king':
        seconds = data.get("timer", DEFAULT_TIMER)
        if current_timer_task and not current_timer_task.done():
            current_timer_task.cancel()
            if current_king_id != user.id:
                await update.message.reply_text(f"⚔️ **{user_name} перебивает {current_king_name}!**\nОн забирает корону. Новый таймер на {seconds} сек. пошел!", parse_mode="Markdown")
        else:
            await update.message.reply_text(f"👑 **{user_name} первый!**\nОн держит корону. Пошел таймер на {seconds} сек.! Успейте перебить!", parse_mode="Markdown")
        
        current_king_id = user.id
        current_king_name = user_name
        current_timer_task = asyncio.create_task(run_timer(chat_id, user.id, user_name, seconds, current_prize, context))
        return 

    elif active_event == 'guess':
        if text.isdigit():
            guess = int(text)
            if guess == secret_number:
                win_text = (
                    f"🎯 **БИНГО!** 🎯\n\n"
                    f"🏆 {user_name} угадал загаданное число (**{secret_number}**)!\n"
                    f"🎁 Победитель забирает приз: **{current_prize}**!\n\n"
                    f"🎉 Поздравляем!"
                )
                msg = await context.bot.send_message(chat_id, win_text, parse_mode="Markdown")
                try:
                    await context.bot.pin_chat_message(chat_id=chat_id, message_id=msg.message_id, disable_notification=True)
                except Exception:
                    pass
                active_event = None
                secret_number = None
        return 

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
            f"🎊🎉 **ПОЗДРАВЛЯЮ!** 🎉🎊\n\n"
            f"🧸 {user_name}, ты выиграл **мишку**!\n\n"
            f"✅ Подарок отправится в течение 2 часов 🕒\n\n"
            f"🚨 Пишите сообщения в чате, и получайте возможность так же залутать подарки!"
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

async def on_dice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global active_event, lucky777_prize
    if not update.message or not update.message.dice: 
        return
    
    chat_id = update.message.chat_id
    if chat_id not in [CHAT_MAIN, CHAT_CASINO]: 
        return

    user = update.message.from_user
    if user.id == ADMIN_ID: 
        return
    
    try:
        member = await context.bot.get_chat_member(chat_id, user.id)
        if member.status in ['administrator', 'creator', ChatMember.ADMINISTRATOR, ChatMember.CREATOR]:
            return  
    except Exception:
        pass

    user_name = html.escape(user.first_name)
    user_link = f"<a href='tg://user?id={user.id}'>{user_name}</a>"
    dice = update.message.dice

    if chat_id == CHAT_CASINO:
        if dice.emoji == '🎰':
            val = dice.value
            if val in [1, 22, 43]:
                prizes = ['❌', '❌', '🧸']
                random.shuffle(prizes)
                buttons = []
                for i, p in enumerate(prizes):
                    buttons.append(InlineKeyboardButton("❓", callback_data=f"casino_click_{i}"))
                
                keyboard = InlineKeyboardMarkup([buttons])
                msg = await update.message.reply_text(
                    f"✨ {user_link} поймал три в ряд — бар / лимон / виноград!\n\n"
                    f"<blockquote>Перед тобой 3 ячейки — в одной из них мишка 🧸. Выбирай!</blockquote>",
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
                casino_games[msg.message_id] = {'user_id': user.id, 'user_name': user.first_name, 'user_link': user_link, 'prizes': prizes, 'type': 'regular', 'bear_index': prizes.index('🧸')}
                
            elif val == 64:
                prizes = ['🧸_15']*12 + ['🌷_25']*4 + ['🎂_50']*2 + ['💍_100'] + ['💎_100']
                random.shuffle(prizes)
                buttons = []
                row = []
                for i, p in enumerate(prizes):
                    row.append(InlineKeyboardButton("❓", callback_data=f"casino_click_{i}"))
                    if len(row) == 4: 
                        buttons.append(row)
                        row = []
                if row: buttons.append(row)
                
                keyboard = InlineKeyboardMarkup(buttons)
                msg = await update.message.reply_text(
                    f"🔥✨ {user_link} поймал ДЖЕКПОТ 777! 🎰🔥\n\n"
                    f"<blockquote>💰 Перед тобой 20 ячеек — здесь ВСЕ ячейки выигрышные! Выбирай!</blockquote>",
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
                casino_games[msg.message_id] = {'user_id': user.id, 'user_name': user.first_name, 'user_link': user_link, 'prizes': prizes, 'type': 'jackpot'}
        return 

    if chat_id == CHAT_MAIN:
        if active_event == 'lucky777' and dice.emoji == '🎰':
            if dice.value == 64:
                win_text = (
                    f"🎰 **ДЖЕКПОТ 777!** 🎰\n\n"
                    f"🏆 {user_name} выбил три семерки и забирает приз:\n"
                    f"🎁 **{lucky777_prize}**!\n\n🎉 Поздравляем!"
                )
                msg = await context.bot.send_message(chat_id, win_text, parse_mode="Markdown")
                try:
                    await context.bot.pin_chat_message(chat_id=chat_id, message_id=msg.message_id, disable_notification=True)
                    await context.bot.send_message(ADMIN_ID, text=f"🔔 **Джекпот!**\n\n{user_name} выбил 777: {lucky777_prize}", parse_mode="Markdown")
                except Exception:
                    pass
                active_event = None
                lucky777_prize = None

async def casino_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    msg_id = query.message.message_id
    
    if msg_id not in casino_games:
        await query.answer("Игра уже завершена.", show_alert=False)
        return

    game = casino_games[msg_id]
    
    if query.from_user.id != game['user_id']:
        await query.answer("Это не твоя игра! Кидай свои слоты.", show_alert=False)
        return
        
    if game.get('active') == False:
        await query.answer("Ты уже сделал выбор!", show_alert=False)
        return
    
    game['active'] = False
    await query.answer()

    click_index = int(query.data.split('_')[-1])
    prizes = game['prizes']
    clicked_prize = prizes[click_index]

    new_buttons = []
    row = []
    won = False
    won_prize_text = ""

    for p in prizes:
        btn_text = p
        if game['type'] == 'jackpot':
            btn_text = p.split('_')[0]

        row.append(InlineKeyboardButton(btn_text, callback_data="ignore"))
        
        if game['type'] == 'jackpot' and len(row) == 4:
            new_buttons.append(row)
            row = []
        elif game['type'] == 'regular' and len(row) == 3:
            new_buttons.append(row)
            row = []
            
    if row: new_buttons.append(row)
    new_keyboard = InlineKeyboardMarkup(new_buttons)

    if game['type'] == 'regular':
        if click_index == game['bear_index']:
            won = True
            won_prize_text = "🧸 Мишка (15 ⭐)"
    else: 
        won = True
        emoji = clicked_prize.split('_')[0]
        price = clicked_prize.split('_')[1]
        won_prize_text = f"{emoji} (Стоимость: {price} ⭐)"

    if won:
        win_text = (
            f"🎉🥳 <b>ПОБЕДА!</b> 🥳🎉\n\n"
            f"🏆 {game['user_link']} открыл ячейку и забирает:\n"
            f"🎁 <b>{won_prize_text}</b>\n\n"
            f"📩 Свяжитесь с админом для получения! @твой_ник_админа"
        )
        try:
            await query.message.edit_text(win_text, reply_markup=new_keyboard, parse_mode="HTML")
        except Exception:
            pass
        
        try:
            await context.bot.send_message(
                ADMIN_ID, 
                text=f"🎰 **ВЫИГРЫШ В КАЗИНО!**\n\n🏆 {game['user_name']} выиграл {won_prize_text}.", 
                parse_mode="Markdown"
            )
        except Exception:
            pass
    else:
        lose_text = (
            f"💔 Не повезло, {game['user_link']}...\n\n"
            f"<blockquote>😔 Вот где был спрятан мишка!\nПовезёт в следующий раз!</blockquote>"
        )
        try:
            await query.message.edit_text(lose_text, reply_markup=new_keyboard, parse_mode="HTML")
        except Exception:
            pass
            
    if msg_id in casino_games:
        del casino_games[msg_id]

async def ignore_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID: return
    context.user_data['setup_step'] = None 
    await update.message.reply_text(
        f"👑 **Админ-панель** 👑\n\n"
        f"⏱ Время ивента: **{data.get('timer')} сек.**\n"
        f"🧸 Шанс мишки: **{data.get('win_chance')}%**\n"
        f"⌛ Кулдаун мишки: **{data.get('cooldown')} мин.**\n\n"
        f"👇 Выбери действие:",
        reply_markup=get_main_menu_keyboard(),
        parse_mode="Markdown"
    )

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat_id != CHAT_MAIN and update.message.chat.type != 'private': return
    await update.message.reply_text(
        f"🎲 Шанс на мишку: **{data.get('win_chance', DEFAULT_WIN_CHANCE)}%**\n"
        f"⏱ Кулдаун: **{data.get('cooldown', DEFAULT_COOLDOWN)} мин.**",
        parse_mode="Markdown"
    )

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
    
    elif query.data:", == 'setup_king':
 reply        if active_event:
            await query._manswer("⚠️ Другarkой ивент ужеup идет!", show_alert=True)
           =get return
        context.user_data['setup_step'] = 'king_prize'
        await query.edit_message_text("🎁 **Шаг 1/1:** Напиши в этот чат приз для «Царя горы»:", reply_markup=get_back_keyboard(), parse_mode="Markdown")

    elif query.data == 'setup_guess':
        if active_event:
            await query.answer("⚠️ Другой ивент уже идет!", show_alert=True)
            return
        context.user_data['setup_step'] = 'guess_range'
        await query.edit_message_text("🎯 **Шаг 1/3:** Выбери диапазон чисел_range_keyboard(), parse_mode="Markdown")

    elif query.data == 'setup_lucky777':
        if active_event:
            await query.answer("⚠️ Другой ивент уже идет!", show_alert=True)
            return
        context.user_data['setup_step'] = 'lucky777_prize'
        await query.edit_message_text("🎁 **Шаг 1/2:** Напиши приз для «Лудки 777»:", reply_markup=get_back_keyboard(), parse_mode="Markdown")

    elif query.data in ['range_100', 'range_1000']:
        context.user_data['guess_range'] = 100 if query.data == 'range_100' else 1000
        context.user_data['setup_step'] = 'guess_number'
        await query.edit_message_text(f"✅ Диапазон: 1-{context.user_data['guess_range']}.\n\n🔢 **Шаг 2/3:** Напиши секретное число:", reply_markup=get_back_keyboard(), parse_mode="Markdown")

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
        await update.message.reply
_text("✅ Царь гор       ы запущен!", event reply_markup_text=get_main_menu_key =board())
        return f

    elif step == 'guess_number"':
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
        context.user_data['setup_step'] = None🎯 **Ивент «Угадай число» начался!**\n\n🎁 Приз: **{current_prize}**\n\n👉 Пиши число от **1 до {context.user_data.get('guess_range', 1000)}**!"
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
    if current_timer_task and not current_timer_task.done(): 
        current_timer_task.cancel()
    
    msg_text = "🛑 **Ивент остановлен.**"
    await context.bot.send_message(chat_id=CHAT_MAIN, text=msg_text, parse_mode="Markdown")
    
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
    
    app_bot.add_handler(CallbackQueryHandler(button_handler, pattern="^(time_|setup_|range_|end_event|change_|show_commands|back_to_menu)"))
    app_bot.add_handler(CallbackQueryHandler(casino_button_handler, pattern="^casino_click_"))
    app_bot.add_handler(CallbackQueryHandler(ignore_handler, pattern="^ignore$"))
    
    app_bot.add_handler(MessageHandler(filters.Dice.ALL, on_dice))
    app_bot.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE & filters.User(user_id=int(ADMIN_ID)), admin_text_handler))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.ChatType.PRIVATE, on_message))
    
    print("Бот запущен...")
    app_bot.run_polling()

if __name__ == "__main__":
    main()
