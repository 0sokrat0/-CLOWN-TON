import logging
import asyncio
import dramatiq
from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter, TelegramAPIError, TelegramForbiddenError
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dramatiq.brokers.redis import RedisBroker
from config import db_config, redis_config, TOKEN, ADMINS
from spam.spam_service import SpamService
import time

# Настройка Dramatiq с использованием Redis как брокера
redis_broker = RedisBroker(host=redis_config['host'], port=redis_config['port'], password=redis_config['password'])
dramatiq.set_broker(redis_broker)

# Инициализация бота и сервиса рассылки
bot = Bot(token=TOKEN)
spam_service = SpamService(db_config, redis_config, bot)

# Проверка нагрузки на бота
async def check_bot_limits():
    try:
        start_time = time.time()
        await bot.get_me()  # Запрос к Telegram API для проверки скорости ответа
        elapsed_time = time.time() - start_time
        return elapsed_time
    except Exception as e:
        logging.error(f"Ошибка при проверке лимитов бота: {e}")
        return None

# Задача для подготовки и отправки массовой рассылки
async def prepare_mass_mailing_task(language, photo, caption, campaign_id, keyboard_data):
    await spam_service.connect()
    user_ids = await spam_service.get_user_ids_by_language(language if language != 'all' else None)
    logging.info(f"Selected users for language '{language}'. Total users: {len(user_ids)}")

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(**btn) for btn in row] for row in keyboard_data
    ]) if keyboard_data else None

    sent_count = 0
    error_count = 0

    for user_id in user_ids:
        try:
            await spam_service.send_message(user_id, language, caption, photo, campaign_id, keyboard)
            sent_count += 1
        except TelegramForbiddenError:
            error_count += 1
            logging.error(f"Bot was blocked by user {user_id}. Skipping.")
        except TelegramRetryAfter as e:
            logging.warning(f"Retry after {e.retry_after} seconds for user {user_id}")
            await asyncio.sleep(e.retry_after)
            try:
                await spam_service.send_message(user_id, language, caption, photo, campaign_id, keyboard)
                sent_count += 1
            except Exception as e:
                error_count += 1
                logging.error(f"Failed to send message to user {user_id} after retry: {e}")
        except Exception as e:
            error_count += 1
            logging.error(f"Failed to send message to user {user_id}: {e}")

    # Уведомляем администраторов о завершении рассылки
    await notify_admins(f"Рассылка с ID {campaign_id} завершена. Сообщения отправлены: {sent_count}, ошибки: {error_count}.")

async def send_notification_task(user_id, photo, caption, campaign_id, delay):
    try:
        await spam_service.send_message(user_id, caption, photo, campaign_id)
        await asyncio.sleep(delay)  # Задержка для управления скоростью отправки
    except TelegramRetryAfter as e:
        logging.warning(f"Retry after {e.retry_after} seconds for user {user_id}")
        await asyncio.sleep(e.retry_after)
        await send_notification_task(user_id, photo, caption, campaign_id, delay)
    except TelegramForbiddenError:
        logging.error(f"Bot was blocked by user {user_id}. Skipping.")
        await spam_service.update_message_status(user_id, "failed", campaign_id)
    except TelegramAPIError as e:
        logging.error(f"Telegram API error: {e}. Message to user {user_id} failed.")
        await spam_service.update_message_status(user_id, "failed", campaign_id)
    except Exception as e:
        logging.error(f"Failed to send message to user {user_id}: {e}")
        await spam_service.update_message_status(user_id, "failed", campaign_id)

# Уведомление администраторов о ходе рассылки
async def notify_admins(message):
    for admin_id in ADMINS:
        await bot.send_message(admin_id, message)

# Уведомление пользователя об ошибке
async def notify_user_about_error(user_id, message):
    try:
        await bot.send_message(user_id, message)
    except Exception as e:
        logging.error(f"Не удалось уведомить пользователя {user_id} об ошибке: {e}")

# Акторы Dramatiq для обработки задач в очереди
@dramatiq.actor(max_retries=5, time_limit=300000)  # Увеличьте время до 300000 мс (5 минут)
def prepare_mass_mailing(language, photo, caption, campaign_id, keyboard_data):
    asyncio.run(prepare_mass_mailing_task(language, photo, caption, campaign_id, keyboard_data))


@dramatiq.actor(max_retries=5, time_limit=300000)  # Увеличьте время до 300000 мс (5 минут)
def send_notification(user_id, photo, caption, campaign_id):
    asyncio.run(send_notification_task(user_id, photo, caption, campaign_id))