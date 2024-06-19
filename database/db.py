import aiomysql
import logging
import uuid
from datetime import datetime


class Database:
    def __init__(self, db_config):
        self.db_config = db_config
        self.pool = None

    async def connect(self):
        logging.info("Connecting to the database...")
        self.pool = await aiomysql.create_pool(
            host=self.db_config['host'],
            port=self.db_config.get('port', 3306),
            user=self.db_config['user'],
            password=self.db_config['password'],
            db=self.db_config['database'],
            minsize=self.db_config.get('minsize', 10),
            maxsize=self.db_config.get('maxsize', 120)
        )
        logging.info("Database connection established.")
        await self.ensure_indexes()

    async def ensure_indexes(self):
        index_queries = [
            ("users", "idx_user_id", "user_id"),
            ("users", "idx_tg_name", "tg_name"),
            ("users", "idx_last_activity", "last_activity"),
            ("users", "idx_referral_code", "referral_code")
        ]
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                for table, index_name, column in index_queries:
                    await cursor.execute(
                        f"SELECT COUNT(1) IndexIsThere FROM INFORMATION_SCHEMA.STATISTICS "
                        f"WHERE table_schema=DATABASE() AND table_name='{table}' AND index_name='{index_name}'")
                    index_is_there = await cursor.fetchone()
                    if index_is_there[0] == 0:
                        await cursor.execute(f"CREATE INDEX {index_name} ON {table} ({column})")
                await conn.commit()

    async def disconnect(self):
        logging.info("Disconnecting from the database...")
        self.pool.close()
        await self.pool.wait_closed()
        logging.info("Database disconnected.")

    async def ensure_connected(self):
        if self.pool is None:
            await self.connect()

    async def user_exists(self, user_id):
        await self.ensure_connected()
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                query = "SELECT 1 FROM users WHERE user_id = %s"
                await cursor.execute(query, (user_id,))
                result = await cursor.fetchone()
                return bool(result)

    async def add_user(self, user_id, referer_id=None, tg_name=None):
        await self.ensure_connected()
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                referral_code = str(uuid.uuid4())
                query = (
                    "INSERT INTO users (user_id, referer_id, tg_name, referral_code, bonus_points, registration_date) "
                    "VALUES (%s, %s, %s, %s, 0, NOW())"
                )
                await cursor.execute(query, (user_id, referer_id, tg_name, referral_code))
                await conn.commit()

    async def get_referral_code(self, user_id):
        await self.ensure_connected()
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                query = "SELECT referral_code FROM users WHERE user_id = %s"
                await cursor.execute(query, (user_id,))
                result = await cursor.fetchone()
                if result and result[0]:
                    return result[0]
                else:
                    new_referral_code = str(uuid.uuid4())
                    update_query = "UPDATE users SET referral_code = %s WHERE user_id = %s"
                    await cursor.execute(update_query, (new_referral_code, user_id))
                    await conn.commit()
                    return new_referral_code

    async def get_user_by_referral_code(self, referral_code):
        await self.ensure_connected()
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                query = "SELECT user_id FROM users WHERE referral_code = %s"
                await cursor.execute(query, (referral_code,))
                result = await cursor.fetchone()
                return result[0] if result else None

    async def add_bonus(self, user_id, bonus_amount):
        await self.ensure_connected()
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                try:
                    logging.info(f"Добавление {bonus_amount} бонусных очков пользователю {user_id}")
                    query = "UPDATE users SET bonus_points = bonus_points + %s WHERE user_id = %s"
                    await cursor.execute(query, (bonus_amount, user_id))
                    await conn.commit()
                    logging.info(f"Успешно добавлено {bonus_amount} бонусных очков пользователю {user_id}")
                except Exception as e:
                    logging.error(f"Ошибка при добавлении бонусных очков пользователю {user_id}: {e}")
                    raise e

    async def get_bonus_points(self, user_id):
        await self.ensure_connected()
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                query = "SELECT bonus_points FROM users WHERE user_id = %s"
                await cursor.execute(query, (user_id,))
                result = await cursor.fetchone()
                return result[0] if result else 0

    async def update_user_tg_name(self, user_id, tg_name):
        await self.ensure_connected()
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                query = "UPDATE users SET tg_name = %s WHERE user_id = %s"
                await cursor.execute(query, (tg_name, user_id))
                await conn.commit()

    async def get_user_info(self, user_id):
        await self.ensure_connected()
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                query = "SELECT * FROM users WHERE user_id = %s"
                await cursor.execute(query, (user_id,))
                return await cursor.fetchone()

    async def count_referals(self, user_id):
        await self.ensure_connected()
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                query = "SELECT COUNT(*) FROM users WHERE referer_id = %s"
                await cursor.execute(query, (user_id,))
                result = await cursor.fetchone()
                return result[0] if result else 0

    async def delete_user(self, user_id):
        await self.ensure_connected()
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                query = "DELETE FROM users WHERE user_id = %s"
                await cursor.execute(query, (user_id,))
                await conn.commit()

    async def has_received_bonus_for_channel(self, user_id, channel_id):
        await self.ensure_connected()
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                query = "SELECT bonus_received FROM subscriptions WHERE user_id = %s AND channel_id = %s"
                await cursor.execute(query, (user_id, channel_id))
                result = await cursor.fetchone()
                return result[0] if result else False

    async def mark_bonus_received_for_channel(self, user_id, channel_id):
        await self.ensure_connected()
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                query = (
                    "INSERT INTO subscriptions (user_id, channel_id, bonus_received) "
                    "VALUES (%s, %s, TRUE) ON DUPLICATE KEY UPDATE bonus_received = TRUE"
                )
                await cursor.execute(query, (user_id, channel_id))
                await conn.commit()

    async def count_users_registered_between(self, start_date, end_date):
        await self.ensure_connected()
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                query = "SELECT COUNT(*) FROM users WHERE registration_date BETWEEN %s AND %s"
                await cursor.execute(query, (start_date, end_date))
                result = await cursor.fetchone()
                return result[0] if result else 0

    async def increment_referral_count(self, user_id):
        await self.ensure_connected()
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                query = "UPDATE users SET referral_count = referral_count + 1 WHERE user_id = %s"
                await cursor.execute(query, (user_id,))
                await conn.commit()

    async def get_referral_count(self, user_id):
        await self.ensure_connected()
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                query = "SELECT referral_count FROM users WHERE user_id = %s"
                await cursor.execute(query, (user_id,))
                result = await cursor.fetchone()
                return result[0] if result else 0

    async def update_last_login(self, user_id):
        now = datetime.now()
        await self.ensure_connected()
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                query = "UPDATE users SET last_login = %s WHERE user_id = %s"
                await cursor.execute(query, (now, user_id))
                await conn.commit()

    async def update_last_activity(self, user_id):
        """ Обновляет время последней активности пользователя """
        now = datetime.now()
        await self.ensure_connected()
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "UPDATE users SET last_activity = %s WHERE user_id = %s",
                    (now, user_id)
                )
                await conn.commit()

    async def is_subscribed_to_notifications(self, user_id):
        await self.ensure_connected()
        async with self.pool.acquire() as connection:
            async with connection.cursor() as cursor:
                await cursor.execute("SELECT subscribed FROM user_notifications WHERE user_id = %s", (user_id,))
                result = await cursor.fetchone()
                return result[0] if result else False

    async def subscribe_to_notifications(self, user_id):
        await self.ensure_connected()
        async with self.pool.acquire() as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    "INSERT INTO user_notifications (user_id, subscribed) VALUES (%s, TRUE) "
                    "ON DUPLICATE KEY UPDATE subscribed = TRUE", (user_id,))
                await connection.commit()

    async def unsubscribe_from_notifications(self, user_id):
        await self.ensure_connected()
        async with self.pool.acquire() as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    "INSERT INTO user_notifications (user_id, subscribed) VALUES (%s, FALSE) "
                    "ON DUPLICATE KEY UPDATE subscribed = FALSE", (user_id,))
                await connection.commit()

    async def save_notification(self, photo=None, caption=None):
        await self.ensure_connected()
        async with self.pool.acquire() as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    "INSERT INTO notifications (photo, caption) VALUES (%s, %s)", (photo, caption))
                await connection.commit()

                await cursor.execute("SELECT LAST_INSERT_ID()")
                result = await cursor.fetchone()
                return result[0]

    async def get_notification(self, notification_id):
        await self.ensure_connected()
        async with self.pool.acquire() as connection:
            async with connection.cursor() as cursor:
                await cursor.execute("SELECT photo, caption FROM notifications WHERE id = %s", (notification_id,))
                return await cursor.fetchone()

    async def get_detailed_user_statistics(self):
        await self.ensure_connected()
        statistics = {}
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT COUNT(*) FROM users")
                statistics['total_users'] = (await cursor.fetchone())[0]

                await cursor.execute("SELECT COUNT(*) FROM users WHERE last_activity >= NOW() - INTERVAL 7 DAY")
                statistics['active_users'] = (await cursor.fetchone())[0]

                await cursor.execute("SELECT COUNT(*) FROM users WHERE registration_date >= NOW() - INTERVAL 7 DAY")
                statistics['new_users'] = (await cursor.fetchone())[0]

                await cursor.execute("SELECT AVG(bonus_points) FROM users")
                statistics['average_bonus_per_user'] = (await cursor.fetchone())[0]

                await cursor.execute("SELECT SUM(bonus_points) FROM users")
                statistics['total_bonus'] = (await cursor.fetchone())[0]

                task_columns = [
                    "task_name_completed",
                    "task_subscribe_completed",
                    "task_invite_completed",
                    "task_repost_completed",
                    "task_boost_completed"
                ]
                for task in task_columns:
                    await cursor.execute(f"SELECT COUNT(*) FROM users WHERE {task} = TRUE")
                    statistics[task] = (await cursor.fetchone())[0]
        return statistics

    async def get_top_users(self, limit=10):
        await self.ensure_connected()
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                query = "SELECT user_id, tg_name, bonus_points FROM users ORDER BY bonus_points DESC LIMIT %s"
                await cursor.execute(query, (limit,))
                return await cursor.fetchall()

    async def update_user_language(self, user_id, language):
        await self.ensure_connected()
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                query = "UPDATE users SET language = %s WHERE user_id = %s"
                await cursor.execute(query, (language, user_id))
                await conn.commit()

    async def get_user_language(self, user_id):
        await self.ensure_connected()
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                query = "SELECT language FROM users WHERE user_id = %s"
                await cursor.execute(query, (user_id,))
                result = await cursor.fetchone()
                return result[0] if result else None

    async def is_task_completed(self, user_id, task_column):
        await self.ensure_connected()
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                query = f"SELECT {task_column} FROM users WHERE user_id = %s"
                await cursor.execute(query, (user_id,))
                result = await cursor.fetchone()
                return result[0] if result else False

    async def mark_task_completed(self, user_id, task_column):
        await self.ensure_connected()
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                try:
                    logging.info(f"Пометка задания '{task_column}' как выполненного для пользователя {user_id}")
                    query = f"UPDATE users SET {task_column} = TRUE WHERE user_id = %s"
                    await cursor.execute(query, (user_id,))
                    await conn.commit()
                    logging.info(f"Задание '{task_column}' успешно помечено как выполненное для пользователя {user_id}")
                except Exception as e:
                    logging.error(f"Ошибка при пометке задания '{task_column}' как выполненного для пользователя {user_id}: {e}")
                    raise e

    async def is_chat_boosted(self, user_id):
        await self.ensure_connected()
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                query = "SELECT boosted FROM chat_boosts WHERE user_id = %s"
                await cursor.execute(query, (user_id,))
                result = await cursor.fetchone()
                return result and result[0]

    async def update_bonus_value(self, new_bonus_value):
        await self.ensure_connected()
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                query = "UPDATE settings SET bonus_value = %s WHERE id = 1"
                await cursor.execute(query, (new_bonus_value,))
                await conn.commit()

    async def update_limit_value(self, new_limit_value):
        await self.ensure_connected()
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                query = "UPDATE settings SET limit_value = %s WHERE id = 1"
                await cursor.execute(query, (new_limit_value,))
                await conn.commit()

    async def get_all_users(self):
        await self.ensure_connected()
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                query = "SELECT user_id, tg_name, bonus_points FROM users"
                await cursor.execute(query)
                return await cursor.fetchall()

    async def get_user_count(self):
        await self.ensure_connected()
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                query = "SELECT COUNT(*) FROM users"
                await cursor.execute(query)
                result = await cursor.fetchone()
                return result[0]

    async def get_users_paginated(self, offset, limit):
        await self.ensure_connected()
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                query = "SELECT user_id, tg_name, bonus_points FROM users LIMIT %s OFFSET %s"
                await cursor.execute(query, (limit, offset))
                return await cursor.fetchall()
            
    async def save_chat_boost(self, user_id, chat_id, boost_id, add_date, expiration_date):
        query = """
        INSERT INTO chat_boosts (user_id, chat_id, boost_id, add_date, expiration_date)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (user_id, chat_id) DO UPDATE
        SET boost_id = EXCLUDED.boost_id,
            add_date = EXCLUDED.add_date,
            expiration_date = EXCLUDED.expiration_date
        """
        await self.execute(query, user_id, chat_id, boost_id, add_date, expiration_date)

    async def is_chat_boosted(self, user_id, chat_id):
        query = "SELECT 1 FROM chat_boosts WHERE user_id = $1 AND chat_id = $2 AND expiration_date > NOW()"
        return await self.fetchval(query, user_id, chat_id) is not None
    

    async def total_referrals_count(self):
        """ Возвращает общее количество рефералов """
        await self.ensure_connected()
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT COUNT(*) FROM users WHERE referer_id IS NOT NULL")
                return (await cursor.fetchone())[0]

    async def active_referrers_count(self):
        """ Возвращает количество активных рефереров """
        await self.ensure_connected()
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    SELECT COUNT(DISTINCT referer_id)
                    FROM users
                    WHERE referer_id IS NOT NULL AND last_activity > NOW() - INTERVAL '7 DAYS'
                """)
                return (await cursor.fetchone())[0]
                

    async def calculate_total_referral_bonuses(self):
        await self.ensure_connected()
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                query = """
                SELECT SUM(bonus_points)
                FROM users
                WHERE referer_id IS NOT NULL
                """
                await cursor.execute(query)
                result = await cursor.fetchone()
                return result[0] if result else 0

    async def count_total_referrals(self):
        await self.ensure_connected()
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                query = """
                SELECT COUNT(*)
                FROM users
                WHERE referer_id IS NOT NULL
                """
                await cursor.execute(query)
                result = await cursor.fetchone()
                return result[0] if result else 0
            
    async def count_active_referrers(self):
        await self.ensure_connected()
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                query = """
                SELECT COUNT(DISTINCT referer_id)
                FROM users
                WHERE referer_id IS NOT NULL
                AND last_activity >= NOW() - INTERVAL 30 DAY
                """
                await cursor.execute(query)
                result = await cursor.fetchone()
                return result[0] if result else 0

    async def is_bonus_awarded(self, user_id: int) -> bool:
        await self.ensure_connected()
        query = "SELECT bonus_awarded FROM users WHERE user_id = %s"
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(query, (user_id,))
                result = await cursor.fetchone()
                return result[0] if result else False

    async def mark_bonus_awarded(self, user_id: int):
        await self.ensure_connected()
        query = "UPDATE users SET bonus_awarded = TRUE WHERE user_id = %s"
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(query, (user_id,))
                await conn.commit()


