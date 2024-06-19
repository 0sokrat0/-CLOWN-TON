import logging
from aiogram import F, Router, Bot
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
import config as cfg
from app.handlers import show_main_menu
from database.db import Database
import app.keyboards as kb
import pandas as pd
from datetime import datetime
from config import TOKEN, ADMINS
from redis.asyncio import Redis

db = Database(cfg.db_config)
router = Router()


async def ensure_db_connection():
    if db.pool is None:
        await db.connect()
        if db.pool is None:
            raise Exception("Failed to connect to the database")
        print("Database connected successfully.")

@router.message(Command("admin_panel"), F.from_user.id.in_(cfg.ADMINS))
async def admin_panel(message: Message):
    await ensure_db_connection()
    logging.info(f"Admin command accessed by {message.from_user.id}")
    await message.answer("Добро пожаловать в админ-панель:", reply_markup=kb.admin)

@router.callback_query(F.data == "admin_analytics")
async def admin_analytics(callback: CallbackQuery):
    await callback.answer("Admin Analytics")
    try:
        stats = await db.get_detailed_user_statistics()
        total_referral_bonus = await db.calculate_total_referral_bonuses()
        total_referrals = await db.count_total_referrals()
        active_referrers = await db.count_active_referrers()  # Подсчет активных реферов
        
        analytics_data = (
            "📊 <b>Пользовательская аналитика:</b>\n\n"
            f"👥 <b>Всего пользователей:</b> {stats['total_users']}\n"
            f"🟢 <b>Активные пользователи (за последнюю неделю):</b> {stats['active_users']}\n"
            f"🆕 <b>Новые пользователи (за последнюю неделю):</b> {stats['new_users']}\n"
            f"💰 <b>Среднее количество бонусов на пользователя:</b> {stats['average_bonus_per_user']:.2f}\n"
            f"🏅 <b>Всего бонусов:</b> {stats['total_bonus']}\n"
            f"🔗 <b>Общая сумма бонусов по рефералам:</b> {total_referral_bonus}\n"
            f"👫 <b>Общее число рефералов:</b> {total_referrals}\n"
            f"🤝 <b>Активные реферы (кто привлёк хотя бы одного реферала):</b> {active_referrers}\n"
            f"✅ <b>Выполненные задачи (добавить $CLOWN к имени):</b> {stats['task_name_completed']}\n"
            f"✅ <b>Выполненные задачи (подписка на канал):</b> {stats['task_subscribe_completed']}\n"
            f"✅ <b>Выполненные задачи (пригласить друзей):</b> {stats['task_invite_completed']}"
        )
        await callback.message.edit_text(analytics_data, parse_mode=ParseMode.HTML, reply_markup=kb.admin_back)
    except Exception as e:
        logging.error(f"Error fetching analytics: {str(e)}")
        await callback.message.edit_text(f"Ошибка при получении аналитики: {str(e)}")

@router.callback_query(F.data == "admin_panel_back")
async def back_admin(callback: CallbackQuery):
    await callback.answer("Back")
    await callback.message.edit_text("Вы вернулись в админ панель", reply_markup=kb.admin)

from aiogram.fsm.state import StatesGroup, State

class NotificationState(StatesGroup):
    waiting_for_content = State()


@router.callback_query(F.data == "back_admin")
async def back_admin(callback: CallbackQuery):
    await callback.answer("Back")
    await callback.message.edit_text("Вы вернулись в админ панель", reply_markup=kb.admin)

@router.callback_query(F.data == "admin_send_notification")
async def admin_send_notification_prompt(callback_query: CallbackQuery, state: FSMContext):
    await ensure_db_connection()
    await db.update_last_activity(callback_query.from_user.id)
    await callback_query.message.answer("Пожалуйста, отправьте текст и/или фото для уведомления.")
    await state.set_state(NotificationState.waiting_for_content)
    await callback_query.answer()

@router.message(F.from_user.id.in_(cfg.ADMINS))
async def get_text_or_photo(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state == NotificationState.waiting_for_content:
        photo = message.photo[-1].file_id if message.photo else None
        caption = message.text or message.caption

        # Сохранение уведомления в базе данных
        notification_id = await db.save_notification(photo, caption)

        # Подтверждение администратором
        confirm_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Одобрить", callback_data=f"approve_notification:{notification_id}")],
            [InlineKeyboardButton(text="Отклонить", callback_data="reject_notification")]
        ])

        if photo:
            await message.answer_photo(photo=photo, caption=caption, reply_markup=confirm_keyboard)
        else:
            await message.answer(text=caption, reply_markup=confirm_keyboard)

        await state.clear()

@router.callback_query(F.data.startswith("approve_notification:"))
async def approve_notification(callback_query: CallbackQuery):
    await ensure_db_connection()
    notification_id = int(callback_query.data.split(":")[1])
    photo, caption = await db.get_notification(notification_id)

    await callback_query.message.edit_reply_markup()
    await callback_query.message.answer("Уведомление одобрено. Отправляю всем пользователям...")

    async with db.pool.acquire() as connection:
        async with connection.cursor() as cursor:
            await cursor.execute("SELECT user_id FROM users")
            user_ids = await cursor.fetchall()
            for user_id in user_ids:
                try:
                    if photo:
                        await callback_query.bot.send_photo(user_id[0], photo=photo, caption=caption)
                    else:
                        await callback_query.bot.send_message(user_id[0], text=caption)
                except Exception as e:
                    logging.exception(f"Failed to send notification to user {user_id[0]}: {e}")

    # Отправка уведомления администратору
    for admin_id in cfg.ADMINS:
        try:
            await callback_query.bot.send_message(admin_id,
                                                  "Уведомление успешно отправлено всем пользователям.")
        except Exception as e:
            logging.exception(f"Failed to send success message to admin {admin_id}: {e}")

@router.callback_query(F.data == "reject_notification")
async def reject_notification(callback_query: CallbackQuery):
    await callback_query.message.edit_reply_markup()
    await callback_query.message.answer("Уведомление отклонено.")
    await callback_query.answer()


@router.callback_query(F.data.startswith("admin_user_list"))
async def admin_user_list(callback: CallbackQuery):
    await callback.answer("User List")
    try:
        await ensure_db_connection()
        page = int(callback.data.split(":")[1]) if ":" in callback.data else 0
        limit = 50
        offset = page * limit

        total_users = await db.get_user_count()
        users = await db.get_users_paginated(offset, limit)

        user_list = "📋 <b>Список пользователей:</b>\n\n"
        for user in users:
            user_list += f"👤 <b>ID:</b> {user['user_id']}, <b>Name:</b> @{user['tg_name']}, <b>Bonus Points:</b> {user['bonus_points']}\n"

        pagination_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data=f"admin_user_list:{page - 1}" if page > 0 else "noop"
                ),
                InlineKeyboardButton(
                    text="Вперед ➡️",
                    callback_data=f"admin_user_list:{page + 1}" if (offset + limit) < total_users else "noop"
                ),
            ],
            [InlineKeyboardButton(text="Назад", callback_data="back_admin")]
        ])

        await callback.message.edit_text(user_list, parse_mode=ParseMode.HTML, reply_markup=pagination_keyboard)
    except Exception as e:
        logging.error(f"Error fetching user list: {str(e)}")
        await callback.message.edit_text(f"Ошибка при получении списка пользователей: {str(e)}")

@router.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery):
    await callback.answer()

@router.callback_query(F.data == "export_users")
async def export_users(callback: CallbackQuery):
    try:
        await ensure_db_connection()
        query = "SELECT * FROM users"

        async with db.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(query)
                data = await cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]

        if data:
            df = pd.DataFrame(data, columns=columns)
            file_path = 'users_export.xlsx'
            df.to_excel(file_path, index=False)
            file = FSInputFile(file_path)
            await callback.message.answer_document(
                document=file,
                caption=f'Актуальный на <b>{datetime.now().strftime("%d-%m-%Y")}</b>',
                parse_mode='HTML'
            )
        else:
            await callback.message.answer("Нет данных для экспорта.")
    except Exception as e:
        await callback.message.answer(f"Ошибка при экспорте данных: {str(e)}")


