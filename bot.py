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
PRANK_LINK = "https://t.me/xucosy" 
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
        [InlineKeyboardButton("🤡 Создать пранк-оффер", callback_data='prank_setup')],
        [InlineKeyboardButton("⏱ 30 сек", callback_data='time_30'), InlineKeyboardButton("⏱ 1 мин", callback_data='time_60')],
        [InlineKeyboardButton("⏱ 3 мин", callback_data='time_180'), InlineKeyboardButton("⏱ 5 мин", callback_data='time_300')],
        [InlineKeyboardButton("🎲 Шанс мишки", callback_data='change_chance')],
        [InlineKeyboardButton("⏱ Кулдаун мишки", callback_data='change_cooldown')],
        [InlineKeyboardButton("📖 Все команды", callback_data='show_commands')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_range_keyboard():
    keyboard = [[InlineKeyboardButton("1 - 100", callback_data='range_100')], [InlineKeyboardButton("1 - 1000", callback_data='range_1000')]]
    return InlineKeyboardMarkup(keyboard)

def get_back_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад в меню", callback_data='back_to_menu')]])

async def run_timer(chat_id, user_id, user_name, seconds, prize, context):
    global current_king_id, current_king_name, active_event
    try:
        if seconds > 30:
            await asyncio.sleep(seconds - 30)
            await context.bot.send_message(chat_id, f"⏳ <b>Осталось 30 секунд!</b>\nКорону держит {user_name}. Успей перебить!", parse_mode="HTML")
        if seconds > 20:
            await asyncio.sleep(10)
            await context.bot.send_message(chat_id, f"⏳ <b>Осталось 20 секунд!</b>", parse_mode="HTML")
        if seconds > 10:
            await asyncio.sleep(10)
            await context.bot.send_message(chat_id, f"🚨 <b>Внимание! Осталось 10 секунд!</b>", parse_mode="HTML")
        for i in range(5, 0, -1):
            await asyncio.sleep(1)
            await context.bot.send_message(chat_id, f"🔥 <b>{i}</b>...", parse_mode="HTML")
        await asyncio.sleep(1)
        text = f"👑 <b>ИВЕНТ ЗАВЕРШЕН!</b> 👑\n\n🏆 Победитель: {user_name}\n🎁 Он забирает приз: <b>{prize}</b>!\n\n🎉 Поздравляем!"
        msg = await context.bot.send_message(chat_id, text, parse_mode="HTML")
        try: await context.bot.pin_chat_message(chat_id=chat_id, message_id=msg.message_id, disable_notification=True)
        except Exception: pass
        active_event = None 
    except asyncio.CancelledError: pass
    except Exception as e: logging.error(f"Ошибка: {e}")

async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_timer_task, current_king_id, current_king_name, active_event, secret_number, current_prize
    
    msg = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    
    if not msg or not msg.text or not user or not chat: return
    chat_id = chat.id
    if chat_id not in [CHAT_MAIN, CHAT_CASINO]: return
    
    text = msg.text.strip()
    if user.id == ADMIN_ID: return
    
    try:
        member = await context.bot.get_chat_member(chat_id, user.id)
        if member.status in ['administrator', 'creator', ChatMember.ADMINISTRATOR, ChatMember.CREATOR]: return  
    except Exception: pass
    
    display_name = f"@{user.username}" if user.username else html.escape(user.first_name)
    user_link = f"<a href='tg://user?id={user.id}'>{display_name}</a>"
    
    if chat_id == CHAT_CASINO: return

    if active_event == 'king':
        seconds = data.get("timer", DEFAULT_TIMER)
        if current_timer_task and not current_timer_task.done():
            current_timer_task.cancel()
            if current_king_id != user.id:
                await msg.reply_text(f"⚔️ <b>{display_name} перебивает {current_king_name}!</b>\nОн забирает корону. Новый таймер на {seconds} сек. пошел!", parse_mode="HTML")
        else:
            await msg.reply_text(f"👑 <b>{display_name} первый!</b>\nОн держит корону. Пошел таймер на {seconds} сек.! Успейте перебить!", parse_mode="HTML")
        current_king_id = user.id
        current_king_name = display_name
        current_timer_task = asyncio.create_task(run_timer(chat_id, user.id, display_name, seconds, current_prize, context))
        return 

    elif active_event == 'guess':
        if text.isdigit():
            guess = int(text)
            if guess == secret_number:
                win_text = f"🎯 <b>БИНГО!</b> 🎯\n\n🏆 {user_link} угадал загаданное число (<b>{secret_number}</b>)!\n🎁 Победитель забирает приз: <b>{current_prize}</b>!\n\n🎉 Поздравляем!"
                m = await context.bot.send_message(chat_id, win_text, parse_mode="HTML")
                try: await context.bot.pin_chat_message(chat_id=chat_id, message_id=m.message_id, disable_notification=True)
                except Exception: pass
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
            if now - last_time < timedelta(minutes=current_cooldown): return
    if random.random() * 100 < current_chance:
        cooldowns[key] = now.isoformat()
        data["cooldowns"] = cooldowns
        save_data(data)
        
        text_win = f"🎊🎉 <b>ПОЗДРАВЛЯЮ!</b> 🎉🎊\n\n🧸 {user_link}, ты выиграл <b>мишку</b>!\n\n✅ Подарок отправится в течение 2 часов 🕒"
        bear_photo = "https://i.postimg.cc/pXvngzR7/72BE0C1A-3E12-494D-895E-369895A4E8FF.png"
        try: m = await msg.reply_photo(photo=bear_photo, caption=text_win, parse_mode="HTML")
        except Exception: m = await msg.reply_text(text_win, parse_mode="HTML")
        try:
            await context.bot.pin_chat_message(chat_id=chat_id, message_id=m.message_id, disable_notification=True)
            await context.bot.send_message(ADMIN_ID, text=f"🔔 <b>Уведомление!</b>\n\n{user_link} выиграл мишку в основном чате!", parse_mode="HTML")
        except Exception: pass

async def on_dice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global active_event, lucky777_prize
    msg = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    
    if not msg or not msg.dice or not user or not chat: return
    chat_id = chat.id
    if chat_id not in [CHAT_MAIN, CHAT_CASINO]: return
    if user.id == ADMIN_ID: return
    
    try:
        member = await context.bot.get_chat_member(chat_id, user.id)
        if member.status in ['administrator', 'creator', ChatMember.ADMINISTRATOR, ChatMember.CREATOR]: return  
    except Exception: pass
    
    display_name = f"@{user.username}" if user.username else html.escape(user.first_name)
    user_link = f"<a href='tg://user?id={user.id}'>{display_name}</a>"
    dice = msg.dice

    if chat_id == CHAT_CASINO:
        if dice.emoji == '🎰':
            val = dice.value
            if val in [1, 22, 43]:
                prizes = ['❌', '❌', '🧸']
                random.shuffle(prizes)
                buttons = [InlineKeyboardButton("❓", callback_data=f"casino_click_{i}") for i in range(3)]
                m = await msg.reply_text(
                    f"✨ {user_link} поймал три в ряд — бар / лимон / виноград!\n\n<blockquote>Перед тобой 3 ячейки — в одной из них мишка 🧸. Выбирай!</blockquote>",
                    reply_markup=InlineKeyboardMarkup([buttons]), parse_mode="HTML"
                )
                casino_games[m.message_id] = {'user_id': user.id, 'user_name': display_name, 'user_link': user_link, 'prizes': prizes, 'type': 'regular', 'bear_index': prizes.index('🧸')}
            elif val == 64:
                prizes = ['🧸_15']*12 + ['💖_25']*4 + ['🌹_50']*3 + ['💍_100']*2 + ['🎁_150']*2 + ['🚀_200']*1 + ['💎_100']*1
                random.shuffle(prizes)
                buttons, row = [], []
                for i, p in enumerate(prizes):
                    row.append(InlineKeyboardButton("❓", callback_data=f"casino_click_{i}"))
                    if len(row) == 5:
                        buttons.append(row)
                        row = []
                if row: buttons.append(row)
                m = await msg.reply_text(
                    f"🔥✨ {user_link} поймал ДЖЕКПОТ 777! 🎰🔥\n\n<blockquote>Перед тобой 25 ячеек. Открой любую — и гарантированно забери свой приз 🏆</blockquote>",
                    reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML"
                )
                casino_games[m.message_id] = {'user_id': user.id, 'user_name': display_name, 'user_link': user_link, 'prizes': prizes, 'type': 'jackpot'}
        return 

    if chat_id == CHAT_MAIN:
        if active_event == 'lucky777' and dice.emoji == '🎰':
            if dice.value == 64:
                win_text = f"🎰 <b>ДЖЕКПОТ 777!</b> 🎰\n\n🏆 {user_link} выбил три семерки и забирает приз:\n🎁 <b>{lucky777_prize}</b>!\n\n🎉 Поздравляем!"
                m = await msg.reply_text(win_text, parse_mode="HTML")
                try:
                    await context.bot.pin_chat_message(chat_id=chat_id, message_id=m.message_id, disable_notification=True)
                    await context.bot.send_message(ADMIN_ID, text=f"🔔 <b>Джекпот!</b>\n\n{user_link} выбил 777: {lucky777_prize}", parse_mode="HTML")
                except Exception: pass
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
        await query.answer("Это не твоя игра!", show_alert=False)
        return
    if game.get('active') == False:
        await query.answer("Ты уже сделал выбор!", show_alert=False)
        return
    game['active'] = False
    await query.answer()
    click_index = int(query.data.split('_')[-1])
    prizes = game['prizes']
    clicked_prize = prizes[click_index]
    new_buttons, row, won, won_prize_text = [], [], False, ""

    for p in prizes:
        btn_text = p.split('_')[0] if game['type'] == 'jackpot' else p
        row.append(InlineKeyboardButton(btn_text, callback_data="ignore"))
        if game['type'] == 'jackpot' and len(row) == 5:
            new_buttons.append(row); row = []
        elif game['type'] == 'regular' and len(row) == 3:
            new_buttons.append(row); row = []
    if row: new_buttons.append(row)
    new_keyboard = InlineKeyboardMarkup(new_buttons)

    if game['type'] == 'regular':
        if click_index == game['bear_index']: won, won_prize_text = True, "🧸 Мишка (15 ⭐)"
    else:
        won = True
        emoji, price = clicked_prize.split('_')[0], clicked_prize.split('_')[1]
        won_prize_text = f"{emoji} (Стоимость: {price} ⭐)"

    try: await query.message.edit_reply_markup(reply_markup=new_keyboard)
    except Exception: pass

    if won:
        win_text = f"🎉🥳 <b>ПОБЕДА!</b> 🥳🎉\n\n🏆 {game['user_link']} открыл ячейку и забирает:\n🎁 <b>{won_prize_text}</b>\n\n📩 Свяжитесь с админом! @твой_ник_админа"
        try: await context.bot.send_message(chat_id=query.message.chat_id, text=win_text, parse_mode="HTML")
        except Exception: pass
        try: await context.bot.send_message(ADMIN_ID, text=f"🎰 <b>ВЫИГРЫШ В КАЗИНО!</b>\n\n🏆 {game['user_link']} выиграл {won_prize_text}.", parse_mode="HTML")
        except Exception: pass
    else:
        lose_text = f"💔 Не повезло, {game['user_link']}...\nПовезёт в следующий раз!"
        try: await context.bot.send_message(chat_id=query.message.chat_id, text=lose_text, parse_mode="HTML")
        except Exception: pass
            
    if msg_id in casino_games: del casino_games[msg_id]

async def ignore_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or update.effective_user.id != ADMIN_ID: return
    context.user_data['setup_step'] = None 
    await msg.reply_text(f"👑 <b>Админ-панель</b> 👑\n\n⏱ Время: <b>{data.get('timer')} сек.</b>\n🧸 Шанс: <b>{data.get('win_chance')}%</b>\n⌛ Кулдаун: <b>{data.get('cooldown')} мин.</b>\n\n👇 Выбери действие:", reply_markup=get_main_menu_keyboard(), parse_mode="HTML")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != CHAT_MAIN and update.effective_chat.type != 'private': return
    await update.effective_message.reply_text(f"🎲 Шанс: <b>{data.get('win_chance')}%</b>\n⏱ Кулдаун: <b>{data.get('cooldown')} мин.</b>", parse_mode="HTML")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global active_event
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID: return

    if query.data.startswith('time_'):
        new_time = int(query.data.split('_')[1])
        data["timer"] = new_time; save_data(data)
        await query.edit_message_text(text=f"✅ Таймер: <b>{new_time} сек.</b>", reply_markup=get_main_menu_keyboard(), parse_mode="HTML")
    elif query.data == 'setup_king':
        if active_event: await query.answer("⚠️ Другой ивент уже идет!", show_alert=True); return
        context.user_data['setup_step'] = 'king_prize'
        await query.edit_message_text("🎁 Напиши приз для «Царя горы»:", reply_markup=get_back_keyboard())
    elif query.data == 'setup_guess':
        if active_event: await query.answer("⚠️ Другой ивент уже идет!", show_alert=True); return
        context.user_data['setup_step'] = 'guess_range'
        await query.edit_message_text("🎯 Выбери диапазон:", reply_markup=get_range_keyboard())
    elif query.data == 'setup_lucky777':
        if active_event: await query.answer("⚠️ Другой ивент уже идет!", show_alert=True); return
        context.user_data['setup_step'] = 'lucky777_prize'
        await query.edit_message_text("🎁 Напиши приз для «Лудки 777»:", reply_markup=get_back_keyboard())
    elif query.data == 'prank_setup':
        context.user_data['setup_step'] = 'prank_nft'
        await query.edit_message_text("🤡 <b>Настройка пранка</b>\n\nШаг 1: Отправь мне картинку NFT (или напиши его название):", parse_mode="HTML", reply_markup=get_back_keyboard())
    elif query.data in ['range_100', 'range_1000']:
        context.user_data['guess_range'] = 100 if query.data == 'range_100' else 1000
        context.user_data['setup_step'] = 'guess_number'
        await query.edit_message_text(f"✅ Диапазон 1-{context.user_data['guess_range']}.\n\nНапиши число:", reply_markup=get_back_keyboard())
    elif query.data == 'end_event':
        active_event = None
        if current_timer_task and not current_timer_task.done(): current_timer_task.cancel()
        await query.message.edit_text("🛑 <b>Ивент завершен.</b>", parse_mode="HTML")
    elif query.data == 'change_chance':
        await query.edit_message_text(text="🎲 Напиши число для шанса:", reply_markup=get_back_keyboard())
        context.user_data['setup_step'] = 'set_chance'
    elif query.data == 'change_cooldown':
        await query.edit_message_text(text="⏱ Напиши число минут (0 = выкл):", reply_markup=get_back_keyboard())
        context.user_data['setup_step'] = 'set_cooldown'
    elif query.data == 'show_commands':
        await query.edit_message_text(text="📚 Команды:\n\n/startguess\n/startking\n/stop\n/stats\n/price 5", reply_markup=get_back_keyboard())
    elif query.data == 'back_to_menu':
        context.user_data['setup_step'] = None
        await query.edit_message_text(text=f"👑 <b>Админ-панель</b>\n\nВремя: <b>{data.get('timer')} сек.</b>\nШанс: <b>{data.get('win_chance')}%</b>\nКулдаун: <b>{data.get('cooldown')} мин.</b>", reply_markup=get_main_menu_keyboard(), parse_mode="HTML")
    elif query.data == 'prank_accept':
        await query.edit_message_caption(caption="✅ <b>Сделка инициирована!</b>\n\nПодарок зарезервирован. Чтобы получить оплату, отправьте ваш NFT нашему гаранту (нажмите кнопку ниже):", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💎 Перейти к гаранту", url=PRANK_LINK)]]), parse_mode="HTML")
    elif query.data == 'prank_reject':
        await query.edit_message_caption(caption="❌ Вы отклонили предложение.", parse_mode="HTML")

async def admin_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global active_event, secret_number, current_prize, current_king_id, current_king_name, lucky777_prize
    msg = update.effective_message
    if not msg or update.effective_user.id != ADMIN_ID or update.effective_chat.type != 'private': return
    step = context.user_data.get('setup_step')
    text = msg.text.strip()

    if step == 'set_chance':
        try:
            new_chance = float(text.replace(',', '.'))
            data["win_chance"] = new_chance; save_data(data)
            await msg.reply_text(f"✅ Шанс: {new_chance}%.", reply_markup=get_main_menu_keyboard())
            context.user_data['setup_step'] = None
        except ValueError: await msg.reply_text("❌ Это не число.", reply_markup=get_back_keyboard())
        return
    if step == 'set_cooldown':
        try:
            new_cd = int(text)
            if new_cd < 0: raise ValueError
            data["cooldown"] = new_cd; save_data(data)
            await msg.reply_text(f"✅ Кулдаун: {new_cd} мин.", reply_markup=get_main_menu_keyboard())
            context.user_data['setup_step'] = None
        except ValueError: await msg.reply_text("❌ Нужно число минут.", reply_markup=get_back_keyboard())
        return
    if step == 'king_prize':
        current_prize = text; active_event = 'king'; current_king_id = None; current_king_name = None
        context.user_data['setup_step'] = None
        seconds = data.get("timer", DEFAULT_TIMER)
        end_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🛑 Завершить", callback_data='end_event')]])
        m = await context.bot.send_message(chat_id=CHAT_MAIN, text=f"📣 <b>Ивент «Царь горы» начался!</b>\n\n⏳ Цель: <b>{seconds} сек.</b>\n\n🎁 Приз: <b>{current_prize}</b>", reply_markup=end_keyboard, parse_mode="HTML")
        try: await context.bot.pin_chat_message(chat_id=CHAT_MAIN, message_id=m.message_id, disable_notification=True)
        except: pass
        await msg.reply_text("✅ Запущено!", reply_markup=get_main_menu_keyboard())
        return
    elif step == 'guess_number':
        if not text.isdigit(): return
        num = int(text)
        if num < 1 or num > context.user_data.get('guess_range', 1000): return
        secret_number = num; context.user_data['setup_step'] = 'guess_prize'
        await msg.reply_text("✅ Число принято!\n\n🎁 Напиши приз:", reply_markup=get_back_keyboard())
        return
    elif step == 'guess_prize':
        current_prize = text; active_event = 'guess'; context.user_data['setup_step'] = None
        end_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🛑 Завершить", callback_data='end_event')]])
        m = await context.bot.send_message(chat_id=CHAT_MAIN, text=f"🎯 <b>Ивент «Угадай число» начался!</b>\n\n🎁 Приз: <b>{current_prize}</b>", reply_markup=end_keyboard, parse_mode="HTML")
        try: await context.bot.pin_chat_message(chat_id=CHAT_MAIN, message_id=m.message_id, disable_notification=True)
        except: pass
        await msg.reply_text(f"✅ Запущено! Загадано: {secret_number}", reply_markup=get_main_menu_keyboard())
        return
    elif step == 'lucky777_prize':
        context.user_data['lucky777_prize'] = text; context.user_data['setup_step'] = 'lucky777_price'
        await msg.reply_text("✅ Приз принят!\n\n💰 Напиши цену:", reply_markup=get_back_keyboard())
        return
    elif step == 'lucky777_price':
        lucky777_prize = context.user_data.get('lucky777_prize', 'Секретный приз'); active_event = 'lucky777'; context.user_data['setup_step'] = None
        end_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🛑 Завершить", callback_data='end_event')]])
        m = await context.bot.send_message(chat_id=CHAT_MAIN, text=f"🎰 <b>Лудка 777 запущена!</b>\n\n🎁 Приз: <b>{lucky777_prize}</b>\n⭐ Цена: {text}", reply_markup=end_keyboard, parse_mode="HTML")
        try: await context.bot.pin_chat_message(chat_id=CHAT_MAIN, message_id=m.message_id, disable_notification=True)
        except: pass
        await msg.reply_text("✅ Запущено!", reply_markup=get_main_menu_keyboard())
        return
    elif step == 'prank_nft':
        context.user_data['prank_nft_name'] = text
        context.user_data['prank_photo'] = None 
        context.user_data['setup_step'] = 'prank_price'
        await msg.reply_text("✅ Название принято!\n\n💰 Шаг 2: Напиши точную сумму и валюту (например: 200 ⭐, 5 TON, 10 грамм):", reply_markup=get_back_keyboard())
        return
    elif step == 'prank_price':
        context.user_data['prank_price'] = text
        context.user_data['setup_step'] = None
        await msg.reply_text("✅ Настройка готова!\n\nТеперь зайди в чат, ответь на сообщение друга и напиши команду /send_offer.", reply_markup=get_main_menu_keyboard())
        return

async def admin_photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or update.effective_user.id != ADMIN_ID or update.effective_chat.type != 'private': return
    if context.user_data.get('setup_step') == 'prank_nft':
        context.user_data['prank_photo'] = msg.photo[-1].file_id
        context.user_data['prank_nft_name'] = "Крутой NFT"
        context.user_data['setup_step'] = 'prank_price'
        await msg.reply_text("✅ Картинка сохранена!\n\n💰 Шаг 2: Напиши точную сумму и валюту (например: 200 ⭐, 5 TON, 10 грамм):", reply_markup=get_back_keyboard())

async def cmd_send_offer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or update.effective_user.id != ADMIN_ID: return
    
    if not msg.reply_to_message:
        await msg.reply_text("❌ Эта команда должна быть ответом на сообщение друга в чате!")
        return
    
    target_name = msg.reply_to_message.from_user.first_name
    target_id = msg.reply_to_message.message_id
    chat_id = msg.chat_id
    
    business_id = getattr(msg, 'business_connection_id', None)
    
    nft = context.user_data.get('prank_nft_name', 'Ценный NFT')
    price = context.user_data.get('prank_price', '200 ⭐')
    photo = context.user_data.get('prank_photo')
    
    text = f"<b>Пользователь {target_name} предлагает\nВам {price} за подарок\n{nft}.</b>"
    
    keyboard = [[
        InlineKeyboardButton("❌ Отклонить", callback_data="prank_reject"),
        InlineKeyboardButton("✅ Принять", callback_data="prank_accept")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        if photo:
            await context.bot.send_photo(
                chat_id=chat_id, photo=photo, caption=text, 
                reply_markup=reply_markup, parse_mode="HTML", 
                reply_to_message_id=target_id,
                business_connection_id=business_id
            )
        else:
            await context.bot.send_message(
                chat_id=chat_id, text=text, 
                reply_markup=reply_markup, parse_mode="HTML", 
                reply_to_message_id=target_id,
                business_connection_id=business_id
            )
        await msg.reply_text("🚀 Оффер успешно отправлен в чат!", business_connection_id=business_id)
    except Exception as e:
        await msg.reply_text(f"❌ Ошибка отправки: {e}", business_connection_id=business_id)

async def cmd_start_guess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID or active_event: return
    context.user_data['setup_step'] = 'guess_range'
    await update.effective_message.reply_text("🎯 Выбери диапазон:", reply_markup=get_range_keyboard())

async def cmd_start_king(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID or active_event: return
    context.user_data['setup_step'] = 'king_prize'
    await update.effective_message.reply_text("🎁 Напиши приз:", reply_markup=get_back_keyboard())

async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global active_event, secret_number, current_timer_task
    if update.effective_user.id != ADMIN_ID or not active_event: return
    active_event = None; secret_number = None
    if current_timer_task and not current_timer_task.done(): current_timer_task.cancel()
    await context.bot.send_message(chat_id=CHAT_MAIN, text="🛑 <b>Ивент остановлен.</b>", parse_mode="HTML")
    await update.effective_message.reply_text("✅ Ивент остановлен.", reply_markup=get_main_menu_keyboard())

async def announce_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID or not context.args: return
    await context.bot.send_message(chat_id=CHAT_MAIN, text=f"📢 <b>ВНИМАНИЕ!</b>\n\nЦена сообщения: <b>{context.args[0]} ⭐</b>.", parse_mode="HTML")
    await update.effective_message.reply_text("✅ Отправлено.")

def main():
    Thread(target=run_flask).start()
    app_bot = Application.builder().token(BOT_TOKEN).build()
    app_bot.add_handler(CommandHandler("start", start_cmd))
    app_bot.add_handler(CommandHandler("startguess", cmd_start_guess))
    app_bot.add_handler(CommandHandler("startking", cmd_start_king))
    app_bot.add_handler(CommandHandler("stop", cmd_stop))
    app_bot.add_handler(CommandHandler("stats", stats)) 
    app_bot.add_handler(CommandHandler("price", announce_price))
    app_bot.add_handler(CommandHandler("send_offer", cmd_send_offer))
    app_bot.add_handler(CallbackQueryHandler(button_handler, pattern="^(time_|setup_|range_|end_event|change_|show_commands|back_to_menu|prank_)"))
    app_bot.add_handler(CallbackQueryHandler(casino_button_handler, pattern="^casino_click_"))
    app_bot.add_handler(CallbackQueryHandler(ignore_handler, pattern="^ignore$"))
    app_bot.add_handler(MessageHandler(filters.Dice.ALL, on_dice))
    app_bot.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE & filters.User(user_id=int(ADMIN_ID)), admin_text_handler))
    app_bot.add_handler(MessageHandler(filters.PHOTO & filters.ChatType.PRIVATE & filters.User(user_id=int(ADMIN_ID)), admin_photo_handler))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.ChatType.PRIVATE, on_message))
    print("Бот запущен...")
    app_bot.run_polling()

if __name__ == "__main__":
    main()
