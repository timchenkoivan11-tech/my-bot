import asyncio
import random
import logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import Message, CallbackQuery

# --- НАСТРОЙКИ ---
BOT_TOKEN = "9180887429:AAH4-Lny3omAwAklfnfwBSq12KfPIyQIV74"
ADMIN_ID =  5522110735 # ВАШ Telegram ID (узнать можно у @userinfobot)

# Хранилище активных игр
active_games = {}

# --- ИНИЦИАЛИЗАЦИЯ ---
logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- КЛАВИАТУРЫ ---
def get_guess_keyboard(game_id: str, count: int = 3):
    builder = InlineKeyboardBuilder()
    if count == 3:
        builder.button(text="🐻", callback_data=f"guess_{game_id}_0")
        builder.button(text="❌", callback_data=f"guess_{game_id}_1")
        builder.button(text="❌", callback_data=f"guess_{game_id}_2")
        builder.adjust(3)
    else:
        for i in range(25):
            builder.button(text="🎁", callback_data=f"guess_{game_id}_{i}")
        builder.adjust(5)
    return builder.as_markup()

# --- УВЕДОМЛЕНИЕ АДМИНУ ---
async def notify_admin(winner_name: str, prize: str, chat_title: str):
    try:
        await bot.send_message(
            ADMIN_ID,
            f"🎰 **Новый выигрыш в казино!**\n\n"
            f"👤 Победитель: {winner_name}\n"
            f"🎁 Приз: {prize}\n"
            f"💬 Чат: {chat_title}"
        )
    except Exception as e:
        logging.error(f"Не удалось отправить уведомление админу: {e}")

# --- ОБРАБОТЧИКИ ---
@dp.message(Command("slot"))
async def cmd_slot(message: Message):
    dice_msg = await message.answer_dice(emoji="🎰")
    await asyncio.sleep(3)

    dice_value = dice_msg.dice.value
    
    # 64 - это джекпот (777). Остальные - обычный шанс 20%
    is_jackpot = (dice_value == 64)
    is_win = is_jackpot or (random.random() < 0.2)

    if is_jackpot:
        game_id = f"{message.from_user.id}_{dice_msg.message_id}"
        # В джекпоте 25 ячеек, гарантированно есть мишка и другие призы
        rewards = ["bear", "ring", "cake", "none"] * 6 + ["bear"]
        random.shuffle(rewards)
        active_games[game_id] = rewards
        
        await message.answer(
            "🎉 **ДЖЕКПОТ 777!** 🎉\n\n"
            "Перед тобой 25 ячеек. В одной из них точно спрятан мишка 🐻!\n"
            "Выбирай!",
            reply_markup=get_guess_keyboard(game_id, count=25)
        )
    elif is_win:
        game_id = f"{message.from_user.id}_{dice_msg.message_id}"
        bear_index = random.randint(0, 2)
        rewards = ["none", "none", "none"]
        rewards[bear_index] = "bear"
        active_games[game_id] = rewards
        
        await message.answer(
            "✨ Ты поймал три в ряд!\n\n"
            "Перед тобой 3 ячейки — в одной из них мишка 🐻. Выбирай!",
            reply_markup=get_guess_keyboard(game_id, count=3)
        )
    else:
        await message.answer("😔 Не повезло... Повезёт в следующий раз!")

@dp.callback_query(F.data.startswith("guess_"))
async def process_guess(callback: CallbackQuery):
    data = callback.data.split("_")
    game_id = data[1]
    chosen_index = int(data[2])

    if game_id not in active_games:
        await callback.answer("Игра устарела или не найдена.", show_alert=True)
        return

    rewards = active_games[game_id]
    if chosen_index >= len(rewards):
        await callback.answer("Ошибка выбора.", show_alert=True)
        return

    reward = rewards[chosen_index]
    
    # Удаляем игру после выбора
    del active_games[game_id]

    # Определяем название приза для уведомления
    prize_name = "Ничего (пусто)"
    if reward == "bear": prize_name = "Мишка 🐻"
    elif reward == "ring": prize_name = "Кольцо 💍"
    elif reward == "cake": prize_name = "Тортик 🎂"

    user_name = f"@{callback.from_user.username}" if callback.from_user.username else callback.from_user.full_name
    chat_title = callback.message.chat.title or "Личные сообщения"

    if reward != "none":
        # Сообщение в чат
        await callback.message.edit_text(
            f"🎉 Поздравляем, {user_name}! Ты выиграл: **{prize_name}**!\n"
            f"(Администратор уведомлен)",
            reply_markup=None
        )
        # Уведомление вам в личку
        await notify_admin(user_name, prize_name, chat_title)
    else:
        await callback.message.edit_text(
            f"❌ Не повезло, {user_name}...\nПовезёт в следующий раз!",
            reply_markup=None
        )
    
    await callback.answer()

# --- ЗАПУСК ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
