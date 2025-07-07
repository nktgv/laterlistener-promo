import asyncio
import re
import os
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor

load_dotenv()

API_TOKEN = os.getenv('BOT_TOKEN')
PG_DSN = os.getenv('POSTGRES_DSN')

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

EMAIL_REGEX = re.compile(r"^[\w\.-]+@[\w\.-]+\.\w+$")
TG_REGEX = re.compile(r"^@([A-Za-z0-9_]{5,32})$")

def init_db():
    with psycopg2.connect(PG_DSN, cursor_factory=RealDictCursor) as conn:
        with conn.cursor() as cur:
            cur.execute('''
                CREATE TABLE IF NOT EXISTS contacts (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT,
                    contact TEXT
                )
            ''')
            cur.execute('''
                CREATE UNIQUE INDEX IF NOT EXISTS idx_user_contact ON contacts(user_id, contact)
            ''')
            conn.commit()

def contact_exists(user_id: int, contact: str) -> bool:
    with psycopg2.connect(PG_DSN) as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT 1 FROM contacts WHERE user_id = %s AND contact = %s', (user_id, contact))
            return cur.fetchone() is not None

def save_contact(user_id: int, contact: str):
    with psycopg2.connect(PG_DSN) as conn:
        with conn.cursor() as cur:
            cur.execute('INSERT INTO contacts (user_id, contact) VALUES (%s, %s)', (user_id, contact))
            conn.commit()

async def answer_message(message, user_id, text):
    loop = asyncio.get_running_loop()
    exists = await loop.run_in_executor(None, contact_exists, user_id, text)
    if exists:
        await message.answer("На этот адрес уже зарегистрировано сообщение.")
        return
    await loop.run_in_executor(None, save_contact, user_id, text)
    await message.answer(
        """
        🔥 Ура! Ты в списке! Спасибо, что оказался в рядах первых — для нас это очень важно. Теперь нас не отчислят с вуза 😅 А тебе +100 к карме и ранний доступ к полезному сервису, который мы сделали с любовью и своими руками
        
        Если хочешь помочь ещё больше — поделись этим ботом со своим другом 👇
        🔗 @laterlistener_bot
        
        Кстати вот держи бесплатный мануал по 10 полезным нейросетям для учёбы и работы, которыми мы и сами регулярно пользуемся
        [ПРИКРЕПЛЁННЫЙ МАНУАЛ]
        """
    )

dp = Dispatcher()

@dp.message(CommandStart())
async def cmd_start(message: Message):
    username = message.from_user.username
    if username:
        kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=f"Отправить мой Telegram")]],
        resize_keyboard=True
        )
    await message.answer(
        """
        👋 Привет! Мы тестируем Telegram-бота, который превращает голосовые, аудио и видео в понятный текст и краткое саммари. Оставь нам свой контакт, где тебе удобнее будет получить информацию, как бот заработает✏️
        
        @example или youremail@example.com
        """,
        reply_markup=kb
    )

@dp.message()
async def handle_message(message: Message):
    if not message.from_user:
        await message.answer("Ошибка: не удалось получить данные пользователя.")
        return
    user_id = message.from_user.id
    text = message.text.strip() if message.text else ""
    # Если пользователь нажал кнопку, подставляем username
    if text == "Отправить мой Telegram":
        username = message.from_user.username
        if username:
            await message.answer(f"@{username}")
            await answer_message(message=message, user_id=user_id, text=username)
        else:
            await message.answer("У вас не установлен username в Telegram. Пожалуйста, задайте его в настройках Telegram и попробуйте снова.")
        return
    # Проверяем контакт
    if EMAIL_REGEX.match(text) or TG_REGEX.match(text):
        await answer_message(message=message, user_id=user_id, text=text)
    else:
        await message.answer("Пожалуйста, отправьте корректный email или Telegram-контакт (например, youremail@example.com или @example)")

async def main():
    if not API_TOKEN:
        raise RuntimeError('Не задан BOT_TOKEN в переменных окружения!')
    if not PG_DSN:
        raise RuntimeError('Не задан POSTGRES_DSN в переменных окружения!')
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, init_db)
    bot = Bot(token=API_TOKEN)
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main()) 