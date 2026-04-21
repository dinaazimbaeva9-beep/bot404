import logging
import sqlite3
import time
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

API_TOKEN = "8634195009:AAHg9Cbk8D6H2BlTwh-hsHtT5Vs4VWQ0mvI"
CHAT_LINK = "https://t.me/+JURnZ-vcL_hlYzVi"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# база
conn = sqlite3.connect('users.db')
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    name TEXT,
    username TEXT,
    invited_by INTEGER,
    invites INTEGER DEFAULT 0,
    joined INTEGER DEFAULT 0,
    activity INTEGER DEFAULT 0
)
""")
conn.commit()

last_message_time = {}

# СТАРТ
@dp.message_handler(commands=['start'])
async def start(message: Message):
    user_id = message.from_user.id
    args = message.get_args()

    cursor.execute("""
    INSERT OR IGNORE INTO users (user_id, name, username)
    VALUES (?, ?, ?)
    """, (
        user_id,
        message.from_user.first_name,
        message.from_user.username
    ))

    if args:
        try:
            inviter = int(args)
            if inviter != user_id:
                cursor.execute(
                    "UPDATE users SET invited_by=? WHERE user_id=?",
                    (inviter, user_id)
                )
        except:
            pass

    conn.commit()

    link = f"https://t.me/{(await bot.get_me()).username}?start={user_id}"

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("👉 Вступить в чат", url=CHAT_LINK))

    await message.answer(
        f"🔥 Ты участвуешь в конкурсе\n\n"
        f"Твоя ссылка:\n{link}\n\n"
        f"Приглашай друзей 👇",
        reply_markup=kb
    )

# ВСТУПИЛ В ЧАТ
@dp.message_handler(content_types=['new_chat_members'])
async def new_member(message: types.Message):
    for user in message.new_chat_members:
        user_id = user.id

        cursor.execute("SELECT invited_by FROM users WHERE user_id=?", (user_id,))
        row = cursor.fetchone()

        if row and row[0]:
            inviter_id = row[0]

            cursor.execute("UPDATE users SET joined=1 WHERE user_id=?", (user_id,))
            cursor.execute("UPDATE users SET invites = invites + 1 WHERE user_id=?", (inviter_id,))
            conn.commit()

            await bot.send_message(inviter_id, "🔥 +1 приглашённый")

# ВЫШЕЛ
@dp.message_handler(content_types=['left_chat_member'])
async def left_member(message: types.Message):
    user = message.left_chat_member
    user_id = user.id

    cursor.execute("SELECT invited_by FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()

    if row and row[0]:
        inviter_id = row[0]

        cursor.execute(
            "UPDATE users SET invites = CASE WHEN invites > 0 THEN invites - 1 ELSE 0 END WHERE user_id=?",
            (inviter_id,)
        )
        conn.commit()

        await bot.send_message(inviter_id, "❌ Один участник вышел")

# АКТИВНОСТЬ
@dp.message_handler(content_types=['text'])
async def activity(message: Message):

    if message.chat.type == "private":
        return

    if message.from_user.is_bot:
        return

    user_id = message.from_user.id
    now = time.time()

    if user_id in last_message_time and now - last_message_time[user_id] < 5:
        return

    last_message_time[user_id] = now

    cursor.execute(
        "UPDATE users SET activity = activity + 1 WHERE user_id=?",
        (user_id,)
    )
    conn.commit()

# СТАТА
@dp.message_handler(commands=['stats'])
async def stats(message: Message):
    user_id = message.from_user.id

    cursor.execute("SELECT invites, activity FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()

    invites = row[0] if row else 0
    activity = row[1] if row else 0

    await message.answer(
        f"📊 Твоя статистика\n\n"
        f"Приглашено: {invites}\n"
        f"Активность: {activity}"
    )

# ТОП
@dp.message_handler(commands=['404stat'])
async def top(message: Message):

    cursor.execute("""
    SELECT name, invites, activity FROM users
    WHERE joined = 1
    ORDER BY invites DESC
    LIMIT 10
    """)

    rows = cursor.fetchall()

    text = "🏆 ТОП 10\n\n"

    for i, row in enumerate(rows, start=1):
        text += f"{i}. {row[0]} — {row[1]} | {row[2]}\n"

    await message.answer(text)

# ЗАПУСК
async def on_startup(dp):
    await bot.delete_webhook(drop_pending_updates=True)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
