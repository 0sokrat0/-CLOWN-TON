import asyncio
from aiogram.fsm.storage.redis import RedisStorage


async def start():
    storage = RedisStorage.from_url("redis://default:4#Yh@KA1bT$)H!)H!@147.45.249.97:6379/1")

    