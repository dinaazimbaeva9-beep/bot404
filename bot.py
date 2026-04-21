import logging
import sqlite3
import time
import os
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

# ===== НАСТРОЙКИ =====
API_TOKEN = os.getenv("API_TOKEN") or "8634195009:AAHg9Cbk8D6H2BlTwh-hsHtT5Vs4VWQ0mvI"
CHAT_ID = -8634195009      
CHAT_LINK = "https://t.me/+JURnZ-vcL_hlYzVi" 

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# ===== БАЗА =====
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

# анти-спам активности
last_message_time = {}

# ===== /start =====
@dp.message_handler(commands=['start'])
async def start(message: Message):
    user_id = message.from_user.id
    args = message.get_args()

    # создаём/обновляем пользователя
    cursor.execute("""
    INSERT OR IGNORE INTO users (user_id, name, username)
    VALUES (?, ?, ?)
    """, (
        user_id,
        message.from_user.first_name,
        message.from_user.username
    ))

    # реферал
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

    bot_username = (await bot.get_me()).username
    ref_link = f"https://t.me/{bot_username}?start={user_id}"

    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("👉 Вступить в чат", url=CHAT_LINK),
        InlineKeyboardButton("📊 Моя статистика", callback_data="stats")
    )

    await message.answer(
        f"🔥 Ты почти завершил(а) регистрацию\n\n"
        f"1) Вступи в чат\n"
        f"2) Делись своей ссылкой\n\n"
        f"🔗 Твоя ссылка:\n{ref_link}",
        reply_markup=kb
    )

# ===== CALLBACK статистика =====
@dp.callback_query_handler(lambda c: c.data == "stats")
async def stats_cb(callback: types.CallbackQuery):
    user_id = callback.from_user.id

    cursor.execute("SELECT invites, activity FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()

    invites = row[0] if row else 0
    activity = row[1] if row else 0

    await callback.message.answer(
        f"📊 Твоя статистика\n\n"
        f"Приглашено: {invites}\n"
        f"Активность: {activity}"
    )

# ===== ВХОД В ЧАТ (+1) =====
@dp.message_handler(content_types=['new_chat_members'])
async def new_member(message: types.Message):
    # работаем только в нужном чате
    if message.chat.id != CHAT_ID:
        return

    for user in message.new_chat_members:
        user_id = user.id

        # убедимся, что юзер есть в базе
        cursor.execute("""
        INSERT OR IGNORE INTO users (user_id, name, username)
        VALUES (?, ?, ?)
        """, (user_id, user.first_name, user.username))

        # кто пригласил
        cursor.execute("SELECT invited_by FROM users WHERE user_id=?", (user_id,))
        row = cursor.fetchone()

        if row and row[0]:
            inviter_id = row[0]

            # отмечаем что зашёл
            cursor.execute("UPDATE users SET joined=1 WHERE user_id=?", (user_id,))
            # +1 инвайт
            cursor.execute("UPDATE users SET invites = invites + 1 WHERE user_id=?", (inviter_id,))
            conn.commit()

            # сколько стало
            cursor.execute("SELECT invites FROM users WHERE user_id=?", (inviter_id,))
            count = cursor.fetchone()[0]

            # уведомление пригласившему
            try:
                await bot.send_message(
                    inviter_id,
                    f"🔥 +1 приглашённый\nТеперь у тебя: {count}"
                )
            except:
                pass

# ===== ВЫХОД ИЗ ЧАТА (-1) =====
@dp.message_handler(content_types=['left_chat_member'])
async def left_member(message: types.Message):
    if message.chat.id != CHAT_ID:
        return

    user = message.left_chat_member
    user_id = user.id

    cursor.execute("SELECT invited_by FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()

    if row and row[0]:
        inviter_id = row[0]

        # -1 инвайт (не уходим в минус)
        cursor.execute("""
        UPDATE users
        SET invites = CASE WHEN invites > 0 THEN invites - 1 ELSE 0 END
        WHERE user_id=?
        """, (inviter_id,))
        conn.commit()

        cursor.execute("SELECT invites FROM users WHERE user_id=?", (inviter_id,))
        count = cursor.fetchone()[0]

        # уведомление пригласившему
        try:
            await bot.send_message(
                inviter_id,
                f"❌ Пользователь вышел из чата\nТеперь у тебя: {count}"
            )
        except:
            pass

# ===== АКТИВНОСТЬ В ЧАТЕ =====
@dp.message_handler(content_types=['text'])
async def track_activity(message: Message):
    if message.chat.id != CHAT_ID:
        return

    if message.from_user.is_bot:
        return

    if message.text.startswith('/'):
        return

    user_id = message.from_user.id
    now = time.time()

    # анти-спам: 1 раз в 5 сек
    if user_id in last_message_time and now - last_message_time[user_id] < 5:
        return

    last_message_time[user_id] = now

    # гарантируем наличие пользователя
    cursor.execute("""
    INSERT OR IGNORE INTO users (user_id, name, username)
    VALUES (?, ?, ?)
    """, (
        user_id,
        message.from_user.first_name,
        message.from_user.username
    ))

    cursor.execute(
        "UPDATE users SET activity = activity + 1 WHERE user_id=?",
        (user_id,)
    )
    conn.commit()

# ===== /stats (в личке или в чате) =====
@dp.message_handler(commands=['stats'])
async def stats(message: Message):
    user_id = message.from_user.id

    cursor.execute("SELECT invites, activity FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()

    invites = row[0] if row else 0
    activity = row[1] if row else 0

    bot_username = (await bot.get_me()).username
    ref_link = f"https://t.me/{bot_username}?start={user_id}"

    await message.answer(
        f"📊 Твоя статистика\n\n"
        f"Приглашено: {invites}\n"
        f"Активность: {activity}\n\n"
        f"Твоя ссылка:\n{ref_link}"
    )

# ===== /404stat (ТОП В ЧАТЕ) =====
@dp.message_handler(commands=['404stat'])
async def top(message: Message):
    # чтобы писалось именно в чате
    if message.chat.id != CHAT_ID:
        return

    cursor.execute("""
    SELECT name, invites, activity FROM users
    ORDER BY invites DESC
    LIMIT 10
    """)
    rows = cursor.fetchall()

    if not rows:
        await message.answer("Пока нет данных")
        return

    text = "🏆 ТОП 10 УЧАСТНИКОВ\n\n"
    for i, row in enumerate(rows, start=1):
        name, invites, activity = row
        text += f"{i}. {name} — {invites} инвайтов | {activity} активность\n"

    await message.answer(text)

# ===== СТАРТ =====
async def on_startup(dp):
    # чистим старые апдейты
    await bot.delete_webhook(drop_pending_updates=True)

if __name__ == "__main__":
    print("BOT STARTED")
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
