import os
import logging
import sqlite3
import time
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

API_TOKEN = os.getenv("API_TOKEN")
CHAT_LINK = "https://t.me/ТВОЙ_ЧАТ"  # ← замени

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

# ===== START =====
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

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("👉 Вступить в чат", url=CHAT_LINK))

    await message.answer(
        "🔥 Ты почти завершил(а) регистрацию\n\n"
        "Перейди в чат, чтобы участвовать 👇",
        reply_markup=kb
    )

# ===== ВХОД (+1) =====
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

            cursor.execute("SELECT invites FROM users WHERE user_id=?", (inviter_id,))
            count = cursor.fetchone()[0]

            await bot.send_message(
                inviter_id,
                f"🔥 +1 приглашенный\nТеперь у тебя: {count}"
            )

# ===== ВЫХОД (-1) =====
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

        cursor.execute("SELECT invites FROM users WHERE user_id=?", (inviter_id,))
        count = cursor.fetchone()[0]

        await bot.send_message(
            inviter_id,
            f"❌ Пользователь вышел\nТеперь у тебя: {count}"
        )

# ===== АКТИВНОСТЬ =====
@dp.message_handler(content_types=['text'])
async def track_activity(message: Message):

    if message.from_user.is_bot:
        return

    if message.text.startswith('/'):
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

# ===== СТАТС =====
@dp.message_handler(commands=['stats'])
async def stats(message: Message):
    user_id = message.from_user.id

    cursor.execute("SELECT invites, activity FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    invites = row[0] if row else 0
    activity = row[1] if row else 0

    link = f"https://t.me/{(await bot.get_me()).username}?start={user_id}"

    await message.answer(
        f"🔥 Твоя статистика\n\n"
        f"Приглашено: {invites}\n"
        f"Активность: {activity}\n\n"
        f"Твоя ссылка:\n{link}"
    )

# ===== ТОП =====
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

# ===== ЗАПУСК =====
async def on_startup(dp):
    await bot.delete_webhook(drop_pending_updates=True)

if __name__ == "__main__":
    print("BOT STARTED")
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
