import asyncio
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.dispatcher.flags import get_flag
from aiogram.types import Message
from cachetools import TTLCache

class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, throttle_time_spin: int, throttle_time_other: int):
        self.caches = {
            "spin": TTLCache(maxsize=10_000, ttl=throttle_time_spin),
            "default": TTLCache(maxsize=10_000, ttl=throttle_time_other)
        }
        self.blocked_users = {}
        self.warnings = {}

    async def __call__(
            self,
            handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
            event: Message,
            data: Dict[str, Any],
    ) -> Any:
        # Проверяем тип чата
        if event.chat.type != "private":
            return await handler(event, data)

        throttling_key = get_flag(data, "throttling_key") or "default"
        user_id = event.chat.id

        if throttling_key in self.caches:
            if user_id in self.blocked_users:
                await event.answer("Вы временно заблокированы за спам!")
                return

            if user_id in self.caches[throttling_key]:
                # Пользователь спамит
                if user_id not in self.warnings:
                    # Первое предупреждение
                    self.warnings[user_id] = 2
                    await event.answer("Слышь клоун, я тебя не понимаю!")
                else:
                    # Второе предупреждение и блокировка
                    self.warnings[user_id] += 1
                    if self.warnings[user_id] >= 3:
                        block_time = self.blocked_users.get(user_id, 10) * 2
                        self.blocked_users[user_id] = block_time
                        self.caches[throttling_key].pop(user_id, None)
                        self.caches[throttling_key][user_id] = None
                        await event.answer(f"Прекрати, клоун! Вы заблокированы на {block_time} секунд.")
                        await asyncio.sleep(block_time)
                        self.blocked_users.pop(user_id, None)
                        self.warnings.pop(user_id, None)
                        return
            else:
                self.caches[throttling_key][user_id] = None

        return await handler(event, data)
