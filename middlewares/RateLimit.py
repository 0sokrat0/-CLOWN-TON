from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.types import Message
from redis.asyncio import Redis
import logging
from aiogram.dispatcher.event.bases import CancelHandler
import asyncio

class RateLimitMiddleware(BaseMiddleware):
    def __init__(self, redis: Redis, rate_limit: int = 5, period: int = 60):
        super().__init__()
        self.redis = redis
        self.rate_limit = rate_limit
        self.period = period
        self.queue = {}

    async def __call__(self, handler, event, data):
        user_id = event.from_user.id
        key = f"rate_limit:{user_id}"

        try:
            current_count = await self.redis.get(key)
            if current_count:
                current_count = int(current_count)
            else:
                current_count = 0

            if current_count >= self.rate_limit:
                if user_id not in self.queue:
                    self.queue[user_id] = []
                self.queue[user_id].append((handler, event, data))
                logging.warning(f"Пользователь {user_id} превысил лимит запросов: {self.rate_limit} запросов за {self.period} секунд. Сообщение добавлено в очередь.")
                raise CancelHandler("Превышен лимит запросов")

            await self.redis.incr(key)
            await self.redis.expire(key, self.period)

            logging.info(f"Пользователь {user_id} сделал {current_count + 1} запросов за последние {self.period} секунд.")
            return await handler(event, data)
        except CancelHandler:
            logging.info(f"Лимит запросов для пользователя {user_id} достигнут. Запрос ставится в очередь.")
            raise
        except Exception as e:
            logging.error(f"Ошибка в RateLimitMiddleware: {e}")
            raise

    async def process_queue(self, bot):
        while True:
            for user_id, events in list(self.queue.items()):
                if events:
                    handler, event, data = events.pop(0)
                    try:
                        logging.info(f"Обработка сообщения из очереди для пользователя {user_id}. Оставшихся сообщений в очереди: {len(events)}.")
                        await handler(event, data)
                        await bot.send_message(user_id, "Ваше сообщение было обработано.")
                    except Exception as e:
                        logging.error(f"Ошибка при обработке очереди для пользователя {user_id}: {e}")
                if not events:
                    del self.queue[user_id]
            await asyncio.sleep(1)
