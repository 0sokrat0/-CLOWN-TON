import logging
import asyncio
import aiomysql
from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter, TelegramAPIError, TelegramForbiddenError

class SpamService:
    def __init__(self, db_config, redis_config, bot_instance, initial_delay=0.05, max_delay=1.0):
        self.db_config = db_config
        self.redis_config = redis_config
        self.bot = bot_instance
        self.pool = None
        self.delay = initial_delay  # Начальная задержка между отправками сообщений
        self.max_delay = max_delay  # Максимальная задержка между отправками сообщений

    async def connect(self):
        attempt = 0
        while attempt < 5:
            try:
                if not self.pool:
                    logging.info(
                        f"Подключение к базе данных {self.db_config['database']} на хосте {self.db_config['host']}...")
                    self.pool = await aiomysql.create_pool(
                        host=self.db_config['host'],
                        port=self.db_config['port'],
                        user=self.db_config['user'],
                        password=self.db_config['password'],
                        db=self.db_config['database'],
                        minsize=10,
                        maxsize=120
                    )

                    async with self.pool.acquire() as conn:
                        async with conn.cursor() as cursor:
                            await cursor.execute(f"USE {self.db_config['database']};")

                    logging.info("Соединение с базой данных установлено.")
                    break
            except Exception as e:
                attempt += 1
                logging.error(f"Ошибка при подключении к базе данных (попытка {attempt}): {e}")
                await asyncio.sleep(5)

    async def record_message_status(self, user_id, language, message, photo, status, campaign_id):
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "INSERT INTO messages (user_id, language, message, photo, status, campaign_id) VALUES (%s, %s, %s, %s, %s, %s)",
                    (user_id, language, message, photo, status, campaign_id)
                )
                await conn.commit()

    async def update_message_status(self, user_id, status, campaign_id):
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "UPDATE messages SET status=%s WHERE user_id=%s AND campaign_id=%s",
                    (status, user_id, campaign_id)
                )
                await conn.commit()

    async def get_user_ids_by_language(self, language=None):
        query = "SELECT user_id FROM users WHERE language=%s" if language else "SELECT user_id FROM users"
        logging.info(f"Используемый запрос: {query}")
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(query, (language,) if language else ())
                user_ids = [row[0] for row in await cursor.fetchall()]
                logging.info(f"Получены идентификаторы пользователей: {len(user_ids)}")
                return user_ids

    async def send_message(self, user_id, language, caption, photo=None, campaign_id=None, keyboard=None):
        try:
            # Добавляем запись сообщения в базу данных перед отправкой
            await self.record_message_status(user_id, language, caption, photo, "pending", campaign_id)

            # Отправка сообщения с использованием HTML форматирования
            if photo:
                await self.bot.send_photo(user_id, photo=photo, caption=caption, reply_markup=keyboard,
                                          parse_mode="HTML")
            else:
                await self.bot.send_message(user_id, caption, reply_markup=keyboard, parse_mode="HTML")

            # Обновляем статус сообщения в базе данных после успешной отправки
            await self.update_message_status(user_id, "sent", campaign_id)
            logging.info(f"Сообщение успешно отправлено пользователю {user_id}")
            self.delay = max(self.delay / 2, 0.05)  # Снижаем задержку после успешной отправки
        except TelegramRetryAfter as e:
            logging.warning(f"Повторная попытка через {e.retry_after} секунд для пользователя {user_id}")
            self.delay = min(self.delay * 2, self.max_delay)  # Увеличиваем задержку при ошибке по лимитам
            await asyncio.sleep(e.retry_after)
            await self.send_message(user_id, caption, photo, campaign_id, keyboard)
        except TelegramForbiddenError as e:
            logging.error(f"Бот был заблокирован пользователем {user_id}. Пропускаем.")
            await self.update_message_status(user_id, "failed", campaign_id)
        except TelegramAPIError as e:
            logging.error(f"Ошибка API Telegram: {e}. Сообщение пользователю {user_id} не доставлено.")
            await self.update_message_status(user_id, "failed", campaign_id)
        except Exception as e:
            logging.error(f"Не удалось отправить сообщение пользователю {user_id}: {e}")
            await self.update_message_status(user_id, "failed", campaign_id)
        finally:
            await asyncio.sleep(self.delay)  # Используем текущую задержку перед отправкой следующего сообщенияисправь оба кода