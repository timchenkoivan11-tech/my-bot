import asyncio
import random
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import Message, CallbackQuery

# --- НАСТРОЙКИ ---
BOT_TOKEN = "ВАШ_ТОКЕН_ЗДЕСЬ"
ADMIN_ID = 123456789  # ВАШ ID (узнать у @userinfobot)

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

# --- ОБРАБОТЧИК ЭМОДЗИ СЛОТОВ ---
# Реагируем на сообщение, если в нем есть эмодзи 🎰
@dp.message(F.text.contains("🎰"))
async def handle_slot_emoji(message: Message):
    # Игнорируем команды бота, если они содержат этот эмодзи
    if message.text.startswith("/"):
        return

    # Имитируем "прокрутку" перед результатом
    await asyncio.sleep(1.5)

    # Шансы: 5% на джекпот (25 ячеек), 25% на обычный выигрыш (3 ячейки)
    # Остальные 70% - проигрыш
    roll = random.random()

    if roll < 0.05:
        # ДЖЕКПОТ
        game_id = f"{message.from_user.id}_{message.message_id}"
        # В 25 ячейках: 3 мишки, 3 кольца, 4 тортика, остальное пусто
        rewards = ["bear"] * 3 + ["ring"] * 3 + ["cake"] * 4 + ["none"] * 15
        random.shuffle(rewards)
        active_games[game_id] = rewards
        
        await message.reply(
            "🎉 **ДЖЕКПОТ 777!** 🎉\n\n"
            "Перед тобой 25 ячеек. Внутри спрятаны ценные призы!\n"
            "Выбирай!",
            reply_markup=get_guess_keyboard(game_id, count=25)
        )
    elif roll < 0.30:
        # ОБЫЧНЫЙ ВЫИГРЫШ
        game_id = f"{message.from_user.id}_{message.message_id}"
        bear_index = random.randint(0, 2)
        rewards = ["none", "none", "none"]
        rewards[bear_index] = "bear"
        active_games[game_id] = rewards
        
        await message.reply(
            "✨ Ты поймал три в ряд!\n\n"
            "Перед тобой 3 ячейки — в одной из них мишка 🐻. Выбирай!",
            reply_markup=get_guess_keyboard(game_id, count=3)
        )
    else:
        await message.reply("😔 Не повезло... Повезёт в следующий раз!")

# --- ОБРАБОТЧИК ВЫБОРА ЯЧЕЙКИ ---
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
    
    # Удаляем игру
    del active_games[game_id]

    prize_name = "Ничего (пусто)"
    if reward == "bear": prize_name = "Мишка 🐻"
    elif reward == "ring": prize_name = "Кольцо 💍"
    elif reward == "cake": prize_name = "Тортик 🎂"

    user_name = f"@{callback.from_user.username}" if callback.from_user.username else callback.from_user.full_name
    chat_title = callback.message.chat.title or "Личные сообщения"

    if reward != "none":
        await callback.message.edit_text(
            f"🎉 Поздравляем, {user_name}! Ты выиграл: **{prize_name}**!\n"
            f"(Администратор уведомлен)",
            reply_markup=None
        )
        # Отчет вам в личку
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
