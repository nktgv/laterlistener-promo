import asyncio
import re
import os
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
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
        await message.answer("Ты уже в списке!")
        return
    await loop.run_in_executor(None, save_contact, user_id, text)
    
    # Отправляем текстовое сообщение
    await message.answer(
        """
        🔥 Ура, ты в списке первых пользователей!

Спасибо, что поддержал наш проект — это очень важно для нас.  
Ты получаешь +100 к карме и ранний доступ к боту, который мы сделали своими руками, с заботой и вниманием к деталям.

Хочешь помочь нам ещё больше? Поделись ботом с другом — это сильно нас поддержит:
🔗 @laterlistener_promo_bot

А вот тебе бонус — мини-гайд с 10 нейросетями, которые мы сами используем в учёбе и работе:
        """
    )
    
    # Отправляем файл мануала
    try:
        manual_file = FSInputFile("LaterListener Бесплатные нейросети.pdf", filename="LaterListener Бесплатные нейросети.pdf")
        await message.answer_document(
            document=manual_file,
            caption="📚 Мини-гайд: 10 полезных нейросетей для учёбы и работы"
        )
    except FileNotFoundError:
        await message.answer("📚 Мини-гайд: 10 полезных нейросетей для учёбы и работы\n(Файл временно недоступен)")
    except Exception as e:
        logger.error(f"Ошибка при отправке файла: {e}")
        await message.answer("📚 Мини-гайд: 10 полезных нейросетей для учёбы и работы\n(Файл временно недоступен)")

dp = Dispatcher()

@dp.message(CommandStart())
async def cmd_start(message: Message):
    username = message.from_user.username
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="ОТПРАВИТЬ СВОЙ ТЕЛЕГРАММ 🚀", callback_data="send_telegram")]]
    )
    await message.answer(
        """
        👋 Привет! Мы приглашаем поучаствовать в мега крутом проекте, который умеет делать:

— расшифровку текста  
— краткое саммари  
— возможность редактировать и сохранять результат

Сейчас мы тестируем первую версию — оставь свой контакт (email или Telegram), чтобы получить ранний доступ, как только всё будет готово ✍️

Например: youremail@example.com или @example
        """,
        reply_markup=kb
    )
@dp.callback_query(lambda c: c.data == "send_telegram")
async def handle_telegram_button(callback: CallbackQuery):
    user_id = callback.from_user.id
    username = callback.from_user.username
    if username:
        await callback.message.answer(f"@{username}")
        await answer_message(message=callback.message, user_id=user_id, text=f"@{username}")
    else:
        await callback.message.answer("У вас не установлен username в Telegram. Пожалуйста, задайте его в настройках Telegram и попробуйте снова.")
    await callback.answer()

@dp.message()
async def handle_message(message: Message):
    if not message.from_user:
        await message.answer("Ошибка: не удалось получить данные пользователя.")
        return
    user_id = message.from_user.id
    text = message.text.strip() if message.text else ""
    if EMAIL_REGEX.match(text) or TG_REGEX.match(text):
        await answer_message(message=message, user_id=user_id, text=text)
    else:
        await message.answer("Отправь, пожалуйста, корректный email или Telegram-контакт.\nПример: youremail@example.com или @example")

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