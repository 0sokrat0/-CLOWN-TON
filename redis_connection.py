import redis.asyncio as redis
import logging

class RedisClient:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        self._client = None

    async def connect(self, url):
        try:
            self._client = redis.from_url(url, encoding="utf-8", decode_responses=True)
            await self._client.ping()
            logging.info("Соединение с Redis установлено.")
        except Exception as e:
            logging.exception(f"Ошибка подключения к Redis: {e}")
            raise e

    def get_client(self):
        if not self._client:
            raise Exception("Redis client is not connected.")
        return self._client

    async def close(self):
        if self._client:
            await self._client.close()
            self._client = None
            logging.info("Соединение с Redis закрыто.")

# Инициализация клиента Redis
redis_client = RedisClient()
