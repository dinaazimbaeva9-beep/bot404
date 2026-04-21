import os
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

API_TOKEN = os.getenv("API_TOKEN")

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

CHANNEL_ID = -8634195009

# хранилище (временно в памяти)
users = {}
invites = {}

# ===== START =====
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    user_id = message.from_user.id

    # реферальная ссылка
    ref = message.get_args()
    if ref:
        invites.setdefault(ref, 0)
        invites[ref] += 1

    users[user_id] = True

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("👉 Вступить в чат", url="https://t.me/your_chat_link"))
    kb.add(InlineKeyboardButton("✅ Я вступил", callback_data="check_sub"))

    await message.answer(
        "🔥 Ты почти завершил регистрацию\n\n"
        "Вступи в чат и подтверди 👇",
        reply_markup=kb
    )

# ===== ПРОВЕРКА ПОДПИСКИ =====
@dp.callback_query_handler(lambda c: c.data == "check_sub")
async def check_sub(call: types.CallbackQuery):
    user_id = call.from_user.id

    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)

        if member.status in ["member", "administrator", "creator"]:
            invites_count = invites.get(str(user_id), 0)

            await call.message.answer(
                f"🏆 Ты в системе!\n\n"
                f"Твои приглашения: {invites_count}"
            )
        else:
            await call.message.answer("❌ Ты не вступил в чат")

    except Exception as e:
        await call.message.answer("Ошибка проверки")

# ===== РЕЙТИНГ =====
@dp.message_handler(commands=['rating'])
async def rating(message: types.Message):
    text = "🏆 Рейтинг:\n\n"

    sorted_users = sorted(invites.items(), key=lambda x: x[1], reverse=True)

    for i, (user, count) in enumerate(sorted_users[:10], start=1):
        text += f"{i}. {user} — {count}\n"

    await message.answer(text or "Пока пусто")

# ===== СТАРТ =====
if __name__ == "__main__":
    print("BOT STARTED")
    executor.start_polling(dp, skip_updates=True)
