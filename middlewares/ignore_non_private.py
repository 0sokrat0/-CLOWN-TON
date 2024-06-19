from aiogram import BaseMiddleware
from aiogram.types import Message

class IgnoreNonPrivateMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Message, data):
        if event.chat.type != "private":
            return 
        return await handler(event, data)
