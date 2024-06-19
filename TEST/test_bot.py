import asyncio
import random
import time
import uuid
from aiogram import Bot, Dispatcher, types, Router
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Chat, Message, Update, User, CallbackQuery
from aiomysql import create_pool
import pytest
from unittest.mock import AsyncMock, patch

db_config = {
    'host': '127.0.0.1',
    'user': 'root',
    'password': 'f1s22731S',
    'db': 'tgdb'
}

# Подключение к базе данных
async def init_db():
    pool = await create_pool(**db_config, minsize=10, maxsize=50)
    return pool

# Инициализация пула соединений
db_pool = None

async def setup_database():
    global db_pool
    db_pool = await init_db()

async def save_user_to_db(user_id, tg_name, chat_id, retry_count=5):
    if db_pool is None:
        raise Exception("Database pool is not initialized")
    for attempt in range(retry_count):
        try:
            async with db_pool.acquire() as conn:
                async with conn.cursor() as cur:
                    # Проверка на существование пользователя
                    await cur.execute("SELECT 1 FROM users WHERE user_id = %s", (user_id,))
                    if await cur.fetchone():
                        return
                    referral_code = str(uuid.uuid4())
                    await cur.execute(
                        """
                        INSERT INTO users (
                            user_id, tg_name, referer_id, referral_code, bonus_points, registration_date
                        ) VALUES (%s, %s, %s, %s, 0, NOW())
                        """,
                        (user_id, tg_name, None, referral_code)
                    )
                    await conn.commit()
                    return
        except Exception as e:
            if attempt < retry_count - 1:
                await asyncio.sleep(0.1)
            else:
                raise

async def delete_test_users():
    if db_pool is None:
        raise Exception("Database pool is not initialized")
    async with db_pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("DELETE FROM users WHERE tg_name LIKE 'user%'")
            await conn.commit()
    print("All test users deleted")

@pytest.mark.asyncio
async def test_stress_test():
    global db_pool
    await setup_database()  # Убедитесь, что инициализация пула соединений выполнена
    if db_pool is None:
        raise Exception("Database pool is not initialized")

    # Инициализация бота и диспетчера
    bot = Bot(token="7064172633:AAF15iarel4nQtcm4V0FcKRfstNIQ-7HLSA", parse_mode="HTML")  # Использование фиктивного токена для мока
    storage = MemoryStorage()
    dp = Dispatcher(bot=bot, storage=storage)
    router = Router()

    # Пример регистрации обработчика для команды /start
    @router.message(lambda message: message.text == "/start")
    async def start_command_handler(message: Message):
        # Запись пользователя в реальную базу данных
        await save_user_to_db(
            message.from_user.id,
            message.from_user.username,
            message.chat.id
        )
        await message.answer("Hello, this is a start command response")

    # Пример обработки callback-запросов
    @router.callback_query(lambda callback_query: True)
    async def handle_callback_query(callback_query: CallbackQuery):
        await callback_query.answer("Button clicked")
        await callback_query.message.answer("Button click processed")

    dp.include_router(router)

    # Создание рандомных пользователей
    num_random_users = 10000
    random_users = [random.randint(1000000000, 9999999999) for _ in range(num_random_users)]

    async def send_start_command(user_id):
        user = User(id=user_id, is_bot=False, first_name=f"User{user_id}", username=f"user{user_id}")
        chat = Chat(id=user_id, type="private")
        message = Message(message_id=user_id, date=0, chat=chat, text="/start", from_user=user)
        update = Update(update_id=user_id, message=message)
        start_time = time.time()
        try:
            await dp.feed_update(bot, update)
            end_time = time.time()
            response_time = end_time - start_time
            return True, response_time
        except Exception as e:
            end_time = time.time()
            response_time = end_time - start_time
            print(f"Failed to send start command for user {user_id}: {e}")
            return False, response_time

    async def send_callback_query(user_id):
        user = User(id=user_id, is_bot=False, first_name=f"User{user_id}", username=f"user{user_id}")
        callback_query = CallbackQuery(
            id=str(uuid.uuid4()),
            from_user=user,
            chat_instance=str(uuid.uuid4()),
            message=Message(message_id=user_id, date=0, chat=Chat(id=user_id, type="private"), text="test"),
            data="test"
        )
        start_time = time.time()
        try:
            await dp.feed_update(bot, Update(update_id=user_id, callback_query=callback_query))
            end_time = time.time()
            response_time = end_time - start_time
            return True, response_time
        except Exception as e:
            end_time = time.time()
            response_time = end_time - start_time
            print(f"Failed to send callback query for user {user_id}: {e}")
            return False, response_time

    async def batch_send_commands(batch):
        tasks = []
        for user_id in batch:
            if random.choice([True, False]):
                tasks.append(send_start_command(user_id))
            else:
                tasks.append(send_callback_query(user_id))
        results = await asyncio.gather(*tasks)
        return results

    total_success = 0
    total_failures = 0
    total_response_time = 0
    total_requests = 0

    with patch('aiogram.Bot.send_message', new_callable=AsyncMock), \
         patch('aiogram.Bot.answer_callback_query', new_callable=AsyncMock), \
         patch('aiogram.Bot.send_chat_action', new_callable=AsyncMock), \
         patch('aiogram.Bot.send_photo', new_callable=AsyncMock), \
         patch('aiogram.Bot.send_document', new_callable=AsyncMock), \
         patch('aiogram.Bot.send_sticker', new_callable=AsyncMock):
        batch_size = 1000  # Размер батча
        for i in range(0, len(random_users), batch_size):
            batch = random_users[i:i + batch_size]
            results = await batch_send_commands(batch)
            for success, response_time in results:
                total_requests += 1
                total_response_time += response_time
                if success:
                    total_success += 1
                else:
                    total_failures += 1
            await asyncio.sleep(0.1)  # Задержка между батчами

    avg_response_time = total_response_time / total_requests if total_requests else 0

    await dp.storage.close()

    # Корректное закрытие пула соединений
    db_pool.close()
    await db_pool.wait_closed()

    print(f"Total requests: {total_requests}")
    print(f"Total successes: {total_success}")
    print(f"Total failures: {total_failures}")
    print(f"Average response time: {avg_response_time:.4f} seconds")

    # Вердикт
    if total_failures == 0:
        print("All requests were successful. The bot can handle a large number of users.")
    else:
        print(f"There were {total_failures} failures out of {total_requests} requests. "
              f"The bot might need optimization to handle a large number of users more reliably.")

# Запуск теста
if __name__ == '__main__':
    import logging
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_stress_test())
    asyncio.run(delete_test_users())
