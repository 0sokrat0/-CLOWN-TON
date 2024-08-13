import asyncio
import logging
from logging.handlers import RotatingFileHandler

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from app import handlers, handlersEN, admin
from config import TOKEN, ADMINS, db_config
from database.db import Database
from spam import handlers as spam
# from middlewares.SubscriptionMiddleware import SubscriptionMiddleware
from middlewares.AntiFloodMiddleware import ThrottlingMiddleware
from middlewares.AntiFloodMiddleware import ThrottlingMiddleware
from middlewares.ignore_non_private import IgnoreNonPrivateMiddleware


import atexit
import psutil



# Создание экземпляра базы данных
db = Database(db_config)

# Создание бота и диспетчера
storage = MemoryStorage()
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=storage)



# Регистрация middleware для проверки подписки
channel_id = "-1002087214352"
channel_link = "https://t.me/clown_token"
# dp.message.middleware(SubscriptionMiddleware(bot, channel_id, channel_link))
throttle_middleware = ThrottlingMiddleware(throttle_time_spin=5, throttle_time_other=2)
dp.message.middleware(throttle_middleware)
dp.message.middleware(IgnoreNonPrivateMiddleware())

# Настройка логирования
def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)  # Устанавливаем уровень логирования на INFO

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    file_handler = RotatingFileHandler('bot.log', maxBytes=5*1024*1024, backupCount=2)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

async def notify_admins(message: str):
    for admin_id in ADMINS:
        try:
            await bot.send_message(admin_id, message)
        except Exception as e:
            logging.exception(f"Failed to send message to admin {admin_id}: {e}")

async def on_startup():
    try:
        await db.connect()
        logging.info("Database connected successfully.")
    except Exception as e:
        await notify_admins(f"Error connecting to the database: {e}")
        logging.exception(f"Error connecting to the database: {e}")
async def startup(ctx):
    ctx['bot'] = bot
    logging.info("Bot started successfully.")



async def on_shutdown():
    try:
        await db.disconnect()
        logging.info("Database disconnected successfully.")
    except Exception as e:
        await notify_admins(f"Error disconnecting from the database: {e}")
        logging.exception(f"Error disconnecting from the database: {e}")



async def main():
    setup_logging()

    dp.include_routers(handlers.router, handlersEN.router, admin.router,spam.router)
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)




    try:
        await dp.start_polling(bot)
    except Exception as e:
        await notify_admins(f"Bot stopped unexpectedly: {e}")
        logging.exception(f"Bot stopped unexpectedly: {e}")
        raise
    finally:
        await bot.session.close()
        await db.disconnect()

def exit_handler():
    loop = asyncio.get_event_loop_policy().get_event_loop()
    try:
        loop.run_until_complete(notify_admins("Bot is shutting down. Please check the system."))
        loop.run_until_complete(db.disconnect())
    except Exception as e:
        logging.exception(f"Error during exit handling: {e}")
    finally:
        loop.close()

if __name__ == "__main__":
    atexit.register(exit_handler)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot stopped by user")
        asyncio.run(notify_admins("Bot was stopped by user"))
    except Exception as e:
        logging.exception(f"Unexpected error: {e}")
        asyncio.run(notify_admins(f"‼️Bot stopped due to an error: {e}"))
