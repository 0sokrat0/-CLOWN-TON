import asyncio
import logging
from aiogram import Bot, Router, F
from aiogram.enums import ChatAction, ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
import app.keyboards as kb
import app.keyboardsEN as kbe
import config as cfg
from database.db import Database
from aiogram.exceptions import TelegramBadRequest

router = Router()
db = Database(cfg.db_config)

russian_main_text = (
    "Мем-коины давно превратились в одну большую клоунскую индустрию 🤡\n\n"
    "<b>Но как понять, что ты тоже клоун?</b>\n\n"
    "➖ Постоянно покупаешь на хаях и катаешься на хуях\n"
    "➖ Твой портфель состоит из щиткоинов, которые все упали\n"
    "➖ Думаешь, что ютилити токена реально на что-то влияет\n\n"
    "Но быть клоуном не стыдно, стыдно быть нищим клоуном.\n"
)

english_main_text = (
    "Meme-coins have long turned into one big clown industry 🤡\n\n"
    "<b>But how do you know that you are a clown too?</b>\n\n"
    "➖ You constantly buy at the top and ride on highs\n"
    "➖ Your portfolio consists of shitcoins that have all fallen\n"
    "➖ You think the utility of a token really affects anything\n\n"
    "But being a clown is not shameful, being a poor clown is shameful.\n"
)

main_channel_id = "-1002087214352"
main_channel_url = "https://t.me/clown_token"

async def ensure_db_connection():
    if db.pool is None:
        await db.connect()
        if db.pool is None:
            raise Exception("Failed to connect to the database")
        print("Database connected successfully.")

class LanguageSelection(StatesGroup):
    choosing_language = State()

@router.message(CommandStart())
async def send_welcome(message: Message, state: FSMContext):
    await db.update_last_activity(message.from_user.id)
    await ensure_db_connection()
    user_id = message.from_user.id
    tg_name = message.from_user.username
    args = message.text.split()

    referer_id = None
    if len(args) > 1:
        referral_code = args[1]
        referer_id = await db.get_user_by_referral_code(referral_code)
        logging.info(f"Referral code provided: {referral_code}, Referer ID: {referer_id}")

    # Сохранение состояния пользователя, даже если он не подписан на канал
    await state.update_data(user_id=user_id, referer_id=referer_id, tg_name=tg_name)

    # Проверка подписки на основной канал
    if not await check_subscription_main(message.bot, user_id, main_channel_id):
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Subscribe to $CLOWN | TON", url=main_channel_url)],
            [InlineKeyboardButton(text="Check Subscription", callback_data="check_subscription")]
        ])
        await message.answer(cfg.NOT_SUB_MESSAGE, reply_markup=keyboard)
        return

    # Если пользователь подписан
    new_user = not await db.user_exists(user_id)
    if new_user:
        logging.info(f"Adding new user: {user_id}, Referer ID: {referer_id}")
        await db.add_user(user_id, referer_id, tg_name)

    # Начисление бонусов при подписке
    if referer_id and (new_user or not await db.is_bonus_awarded(user_id)):
        logging.info(f"User {user_id} is now subscribed. Adding referral bonuses.")
        await db.increment_referral_count(referer_id)
        await db.add_bonus(referer_id, 300)  # Начисление бонусов рефереру
        await db.add_bonus(user_id, 100)  # Начисление бонусов рефералу
        await db.mark_bonus_awarded(user_id)  # Отметить, что бонусы были начислены

    language = await db.get_user_language(user_id)
    if not language:
        await message.answer(
            "👉 <b>Пожалуйста, выберите язык для продолжения:</b>\n"
            "👉 <b>Please select the language to continue:</b>\n",
            reply_markup=kb.language_keyboard, parse_mode=ParseMode.HTML
        )
        await state.set_state(LanguageSelection.choosing_language)
    else:
        await show_main_menu(message, language)

@router.callback_query(F.data == "check_subscription")
async def check_subscription_handler_main(callback_query: CallbackQuery, state: FSMContext):
    await ensure_db_connection()
    user_id = callback_query.from_user.id
    data = await state.get_data()
    referer_id = data.get('referer_id')

    logging.info(f"Checking subscription for user {user_id}. Referer ID: {referer_id}")

    if await check_subscription_main(callback_query.bot, user_id, main_channel_id):
        await callback_query.message.delete()

        # Если пользователь подписан на канал, но реферал не добавлен
        new_user = not await db.user_exists(user_id)
        if new_user:
            tg_name = data.get('tg_name')
            logging.info(f"Adding new user: {user_id}, Referer ID: {referer_id}")
            await db.add_user(user_id, referer_id, tg_name)

        if referer_id and not await db.is_bonus_awarded(user_id):
            logging.info(f"User {user_id} is now subscribed. Adding referral bonuses.")
            await db.increment_referral_count(referer_id)
            await db.add_bonus(referer_id, 300)  # Начисление бонусов рефереру
            await db.add_bonus(user_id, 100)  # Начисление бонусов рефералу
            await db.mark_bonus_awarded(user_id)  # Отметить, что бонусы были начислены

        await send_welcome(callback_query.message, state)  # Call the welcome function again after successful subscription
    else:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Subscribe to $CLOWN | TON", url=main_channel_url)],
            [InlineKeyboardButton(text="Check Subscription", callback_data="check_subscription")]
        ])
        await callback_query.message.answer("Доступ есть только клоунам\nOnly clowns have access 🤡", reply_markup=keyboard)
        await callback_query.answer()

async def check_subscription_main(bot: Bot, user_id: int, channel_id: int):
    try:
        member = await bot.get_chat_member(channel_id, user_id)
        logging.info(f"User {user_id} status in channel {channel_id}: {member.status}")
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logging.error(f"Ошибка при проверке подписки для пользователя {user_id} в канале {channel_id}: {e}")
        return False

@router.message(Command("change_language"))
async def command_change_language(message: Message, state: FSMContext):
    user_id = message.from_user.id

    # Проверка, если пользователь зарегистрирован и подписан на канал
    if await db.user_exists(user_id) and await check_subscription_main(message.bot, user_id, main_channel_id):
        await message.answer(
            "👉 <b>Пожалуйста, выберите язык для продолжения:</b>\n"
            "👉 <b>Please select the language to continue:</b>\n",
            reply_markup=kb.language_keyboard, parse_mode=ParseMode.HTML
        )
        await state.set_state(LanguageSelection.choosing_language)
    else:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Subscribe to $CLOWN | TON", url=main_channel_url)],
            [InlineKeyboardButton(text="Check Subscription", callback_data="check_subscription")]
        ])
        await message.answer("Доступ есть только клоунам\nOnly clowns have access 🤡", reply_markup=keyboard)

async def show_main_menu(message: Message, language: str):
    if language == "ru":
        await message.bot.send_chat_action(chat_id=message.from_user.id, action=ChatAction.TYPING)
        await asyncio.sleep(0.2)
        await message.answer_photo(
            "AgACAgIAAxkBAAIo2mZoU8ce7iy4zFDbUSoENq0ibY4XAALT3DEbxxtAS9Mo5fWcsxoUAQADAgADeQADNQQ",
            russian_main_text, parse_mode="HTML", reply_markup=kb.russian_main
        )
    elif language == "en":
        await message.bot.send_chat_action(chat_id=message.from_user.id, action=ChatAction.TYPING)
        await asyncio.sleep(0.2)
        await message.answer_photo(
            "AgACAgIAAxkBAAIo2mZoU8ce7iy4zFDbUSoENq0ibY4XAALT3DEbxxtAS9Mo5fWcsxoUAQADAgADeQADNQQ",
            english_main_text, parse_mode="HTML", reply_markup=kbe.english_main
        )
        
@router.callback_query(F.data == "language_ru")
async def set_language_ru(callback: CallbackQuery, state: FSMContext):
    await ensure_db_connection()
    await db.update_user_language(callback.from_user.id, "ru")
    await state.clear()
    await callback.message.delete()
    await show_main_menu(callback.message, "ru")

@router.callback_query(F.data == "language_en")
async def set_language_en(callback: CallbackQuery, state: FSMContext):
    await ensure_db_connection()
    await db.update_user_language(callback.from_user.id, "en")
    await state.clear()
    await callback.message.delete()
    await show_main_menu(callback.message, "en")



@router.callback_query(F.data == "back_ru")
async def back(callback: CallbackQuery):
    await callback.answer("Назад")
    await callback.message.delete()
    await show_main_menu(callback.message, "ru")

@router.callback_query(F.data == "profile_ru")
async def profile(callback: CallbackQuery):
    await db.update_last_activity(callback.from_user.id)
    await callback.bot.send_chat_action(chat_id=callback.from_user.id, action=ChatAction.TYPING)
    await asyncio.sleep(0.2)
    await ensure_db_connection()
    await db.update_last_activity(callback.from_user.id)
    user_id = callback.from_user.id
    tg_name = callback.from_user.username or "Не указано"
    num_referals = await db.count_referals(user_id)
    bonus = await db.get_bonus_points(user_id)

    profile_info = (
        "<b>Эй, Клоун, вот твой профиль?!</b>\n\n"
        f"🤡 <b>Имя:</b> @{tg_name}\n"
        f"🤝 <b>Количество рефералов:</b> {num_referals}\n"
        f"🎁 <b>Количество бонусов:</b> {bonus}"
    )
    await callback.message.delete()
    await callback.answer("Ваш профиль")
    await callback.message.answer_photo(
        "AgACAgIAAxkBAAM8ZlpVAVFJvyjSuIhIub3rNyI_6gYAAknfMRsGodFKR8es8U2XJaQBAAMCAAN5AAM1BA",
        profile_info, parse_mode=ParseMode.HTML, reply_markup=kb.russian_back
    )

# @router.callback_query(F.data == "wallet_ru")
# async def wallet(callback: CallbackQuery):
#     await db.update_last_activity(callback.from_user.id)
#     await callback.bot.send_chat_action(chat_id=callback.from_user.id, action=ChatAction.TYPING)
#     await asyncio.sleep(0.2)
#     text = (
#         "<u>Ваш кошелек:</u>\n\n"
#         "<b>Вам нужно привязать НЕкастодиальный кошелек сети TON -  рекомендуем - Tonkeeper/Tonhub/MyTonWallet</b>"
#     )
#     await callback.message.delete()
#     await callback.message.answer_photo(
#         "AgACAgIAAxkBAANhZlpZfgPxgGWJ8SeQRZiyv25aCFsAAk_fMRsGodFKQh2TJL8pSbIBAAMCAAN5AAM1BA",
#         text, parse_mode=ParseMode.HTML, reply_markup=kb.russian_back
#     )

@router.callback_query(F.data == "referal_link_ru")
async def referal(callback: CallbackQuery):
    await db.update_last_activity(callback.from_user.id)
    await callback.bot.send_chat_action(chat_id=callback.from_user.id, action=ChatAction.TYPING)
    await asyncio.sleep(0.2)
    await ensure_db_connection()
    await db.update_last_activity(callback.from_user.id)
    referral_code = await db.get_referral_code(callback.from_user.id)
    referral_link = f"https://t.me/{cfg.bot_name}?start={referral_code}"
    tg_name = callback.from_user.username or "Не указано"
    num_referals = await db.count_referals(callback.from_user.id)
    bonus = await db.get_bonus_points(callback.from_user.id)

    response_text = (
        "Приглашай новых Клоунов! Расширяйте карманы вместе!\n\n"
        "1 реферал = 300 points\n\n"
        "🔗 **Твоя реферальная ссылка:**\n"
        f"`{referral_link}`"
    )

    share_text = (
        f"Присоединяйся к $CLOWN и получи бонусы!\n\n"
        f"Регистрация по моей ссылке: {referral_link}"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пригласить Клоуна", switch_inline_query=share_text)],
        [InlineKeyboardButton(text="Назад", callback_data="back_ru")]
    ])

    await callback.message.delete()
    await callback.message.answer_photo(
        "AgACAgIAAxkBAANvZlpbyTSSnmNt-oz__s9IwoeXP0wAAlDfMRsGodFKz9SV8hvO42kBAAMCAAN5AAM1BA",
        response_text, parse_mode="Markdown", reply_markup=keyboard
    )

# @router.callback_query(F.data == "preseil_ru")
# async def presell_ru(callback: CallbackQuery):
#     await db.update_last_activity(callback.from_user.id)
#     await callback.bot.send_chat_action(chat_id=callback.from_user.id, action=ChatAction.TYPING)
#     await asyncio.sleep(0.2)
#     await ensure_db_connection()
#     await db.update_last_activity(callback.from_user.id)
#     pay_address = "UQC9jmCfyIYb_RK3jba8qWMfJOBJlfqQ_hCym0IXd0yObLok"

#     response_text = (
#         "<b>Расти большой, не будь лапшой</b>\n\n"
#         "🤡 <u>Детали пресейла:</u>\n\n"
#         "Отправляете TON, чтобы получить <b>$CLOWN</b>\n\n"
#         "<b>Min</b>: 20 ton \n"
#         "<b>Max</b>: годовой бюджет цирка\n\n"
#         "<b>Используйте только<u>TonKeeper</u></b>\n\n"
#         f"<code>{pay_address}</code>\n\n"
#         "Больше информации на сайте:\n"
#         "<a href='https://clown.meme'>https://clown.meme</a>"
#     )
#     await callback.message.delete()
#     await callback.message.answer_photo(
#         "AgACAgIAAxkBAAOSZlpfeTXdXJfhDLfzXRWqlxySKZcAAlPfMRsGodFK-iNBcvnV8ykBAAMCAAN5AAM1BA",
#         response_text, reply_markup=kb.main_presell_ru, parse_mode=ParseMode.HTML
#     )

@router.callback_query(F.data == "top10_ru")
async def top10(callback: CallbackQuery):
    await callback.bot.send_chat_action(chat_id=callback.from_user.id, action=ChatAction.TYPING)
    await ensure_db_connection()

    top_users = await db.get_top_users(limit=10)
    top_text = "Топ-10 Клоунов в нашем цирке:\n\n"
    for i, user in enumerate(top_users, start=1):
        tg_name = user['tg_name'] if user['tg_name'] else "Не указано"
        top_text += f"{i}. @{tg_name} - {user['bonus_points']}\n"

    await callback.message.delete()
    await callback.message.answer_photo(
        "AgACAgIAAxkBAAI4EmZpvdhI85OPwh3Z3pCMGHpxwM87AAJH3zEbpVJQSzW3clwPLOmZAQADAgADeQADNQQ",
        top_text, parse_mode=ParseMode.HTML, reply_markup=kb.russian_back
    )

# class TaskState(StatesGroup):
#     waiting_for_repost_link = State()

async def ensure_db_connection():
    if db.pool is None:
        await db.connect()
        if db.pool is None:
            raise Exception("Failed to connect to the database")
        print("Database connected successfully.")

async def check_and_award_all_subscriptions(bot: Bot, user_id: int, db: Database):
    if await check_all_subscriptions(bot, user_id) and not await db.is_task_completed(user_id, "task_subscribe_completed"):
        bonus_amount = 2000  # Общий бонус за подписку на все каналы
        await db.add_bonus(user_id, bonus_amount)
        await db.mark_task_completed(user_id, "task_subscribe_completed")
        return True
    return False

async def check_all_subscriptions(bot: Bot, user_id: int):
    all_subscribed = True
    for _, channel_id, _ in cfg.CHANNELS:
        member = await bot.get_chat_member(channel_id, user_id)
        if member.status not in ["member", "administrator", "creator"]:
            all_subscribed = False
            break
    return all_subscribed


async def is_chat_boosted(bot: Bot, user_id: int):
    try:
        chat_member = await bot.get_chat_member(cfg.BOOST_CHAT_ID, user_id)
        if chat_member.status in ["member", "administrator", "creator"]:
            return True
    except Exception as e:
        logging.error(f"Error checking chat boost for user {user_id}: {e}")
    return False

async def get_task_keyboard(user_id):
    await ensure_db_connection()
    task_name_completed = await db.is_task_completed(user_id, "task_name_completed")
    task_subscribe_completed = await db.is_task_completed(user_id, "task_subscribe_completed")
    task_invite_completed = await db.is_task_completed(user_id, "task_invite_completed")
    # task_repost_completed = await db.is_task_completed(user_id, "task_repost_completed")
    task_boost_completed = await db.is_task_completed(user_id, "task_boost_completed")

    task_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"Добавьте к имени $CLOWN [2500 Points]{'✅' if task_name_completed else '❌'}",
                callback_data="task_name_2000" if not task_name_completed else "task_already_completed"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"Подпишитесь на $CLOWN | TON [2000 Points]{'✅' if task_subscribe_completed else '❌'}",
                callback_data="task_subscribe_500" if not task_subscribe_completed else "task_already_completed"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"Пригласите 5 друзей [1000 Points] {'✅' if task_invite_completed else '❌'}",
                callback_data="task_invite_friends" if not task_invite_completed else "task_already_completed"
            )
        ],
        # [
        #     InlineKeyboardButton(
        #         text=f"Сделайте репост в Twitter {'✅' if task_repost_completed else '❌'}",
        #         callback_data="task_repost_1000" if not task_repost_completed else "task_already_completed"
        #     )
        # ],
        # [
        #     InlineKeyboardButton(
        #         text=f"Сделайте Boost канала {'✅' if task_boost_completed else '❌'}",
        #         callback_data="task_boost_2500" if not task_boost_completed else "task_already_completed"
        #     )
        # ],
        [
            InlineKeyboardButton(text="Назад", callback_data="back_ru")
        ]
    ])
    return task_keyboard

@router.callback_query(F.data == "tasks_ru")
async def tasks(callback: CallbackQuery):
    user_id = callback.from_user.id
    task_keyboard = await get_task_keyboard(user_id)

    await callback.bot.send_chat_action(chat_id=callback.from_user.id, action=ChatAction.TYPING)
    await callback.message.delete()
    await callback.message.answer_photo(
        "AgACAgIAAxkBAAI6lmZp1y4jmaciyEdNVM2BgUDTK8xSAAJI3zEbpVJQSz-sPC72fb16AQADAgADeQADNQQ",
        "Выполняй задания и получай поинты!\n\nПроверяй их ежедневно и стань самым богатым клоуном на диком западе!",
        reply_markup=task_keyboard
    )
    await callback.answer()

# @router.message(F.photo)
# async def handle_photo(message: Message):
#     # Получаем ID самой большой (высокого разрешения) фотографии в массиве
#     photo_id = message.photo[-1].file_id
#     await message.answer(f"ID отправленного вами фото: {photo_id}")

# Остальной ваш код остается без изменений


@router.callback_query(F.data == "task_name_2000")
async def task_name_2000(callback: CallbackQuery):
    user_id = callback.from_user.id
    await ensure_db_connection()
    if await db.is_task_completed(user_id, "task_name_completed"):
        await callback.answer("This task has already been completed.", show_alert=True)
        return

    reward_points = 2000
    task_keyboard = await get_task_keyboard(user_id)

    user_profile = await callback.bot.get_chat_member(callback.message.chat.id, user_id)
    if "clown" in (user_profile.user.full_name or "").lower():
        await db.add_bonus(user_id, reward_points)
        await db.mark_task_completed(user_id, "task_name_completed")
        await callback.answer(f"Вы успешно добавили $CLOWN к своему имени и заработали баллы {reward_points}.", show_alert=True)
        try:
            await callback.message.edit_reply_markup(reply_markup=task_keyboard)
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e):
                raise e
    else:
        await callback.answer("В вашем имени нет $CLOWN Задание не было выполнено.", show_alert=True)


@router.callback_query(F.data == "task_subscribe_500")
async def task_subscribe_500(callback: CallbackQuery):
    await ensure_db_connection()
    user_id = callback.from_user.id
    if not await db.is_task_completed(user_id, "task_subscribe_completed"):
        await callback.bot.send_chat_action(chat_id=callback.from_user.id, action=ChatAction.TYPING)
        await callback.message.delete()
        channels_keyboard = await get_channels_keyboard(callback.bot, user_id)
        await callback.message.answer(
            "Подпишитесь на каналы, затем нажмите 'Проверить подписку', чтобы заработать 2000 очков.",
            reply_markup=channels_keyboard
        )
    else:
        await callback.message.answer("Вы уже выполнили это задание.")
    await callback.answer()

@router.callback_query(F.data == "checksub")
async def check_subscription_handler(callback_query: CallbackQuery):
    await ensure_db_connection()
    user_id = callback_query.from_user.id

    if await check_and_award_all_subscriptions(callback_query.bot, user_id, db):
        message = "Вы подписаны на все каналы и получили 2000 бонусных очков!"
        await callback_query.message.answer(message, reply_markup=await get_task_keyboard(user_id))
    else:
        message = "Вы не подписаны на все каналы. Пожалуйста, подпишитесь для получения бонуса."
        await callback_query.message.answer(message, reply_markup=await get_task_keyboard(user_id))

    await callback_query.answer()

@router.callback_query(F.data == "task_invite_friends")
async def task_invite_friends(callback: CallbackQuery):
    await ensure_db_connection()
    user_id = callback.from_user.id
    reward_points = 1000
    task_keyboard = await get_task_keyboard(user_id)

    referals_count = await db.count_referals(user_id)
    required_referals = 5  # Требуемое количество рефералов для выполнения задания
    referral_code = await db.get_referral_code(user_id)
    referral_link = f"https://t.me/{cfg.bot_name}?start={referral_code}"

    if referals_count >= required_referals:
        if not await db.is_task_completed(user_id, "task_invite_completed"):
            await db.add_bonus(user_id, reward_points)
            await db.mark_task_completed(user_id, "task_invite_completed")
            response_text = f"Вы успешно пригласили {required_referals} друзей и заработали {reward_points} очков! Всего приглашено: {referals_count}."
        else:
            response_text = f"Вы уже выполнили это задание. Всего приглашено: {referals_count}."
    else:
        response_text = f"Пригласите {required_referals} друзей, чтобы выполнить это задание. Всего приглашено: {referals_count}."

    share_text = (
        f"Присоединяйся к $CLOWN и получи бонусы!\n\n"
        f"Регистрация по моей ссылке: {referral_link}"
    )

    new_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пригласить Клоуна", switch_inline_query=share_text)],
        [InlineKeyboardButton(text="Назад к заданиям", callback_data="tasks_ru")]
    ])

    await callback.message.delete()
    await callback.message.answer(response_text, reply_markup=new_keyboard, parse_mode=ParseMode.HTML)
    await callback.answer()


@router.callback_query(F.data == "task_already_completed")
async def task_already_completed(callback: CallbackQuery):
    await callback.answer("Это задание уже выполнено.", show_alert=True)

# @router.callback_query(F.data == "task_repost_1000")
# async def task_repost_1000(callback: CallbackQuery, state: FSMContext):
#     user_id = callback.from_user.id
#     if await db.is_task_completed(user_id, "task_repost_completed"):
#         await callback.answer("Это задание уже выполнено.", show_alert=True)
#         return

#     await ensure_db_connection()
#     task_keyboard = await get_task_keyboard(user_id)

#     new_keyboard = InlineKeyboardMarkup(inline_keyboard=[
#         [InlineKeyboardButton(text="Перейти к посту", url="https://x.com/clown_ton/status/1791460990413877328?s=46")],
#         [InlineKeyboardButton(text="Проверить репост", callback_data="check_repost")],
#         [InlineKeyboardButton(text="Назад", callback_data="tasks_ru")]
#     ])

#     await callback.message.delete()
#     new_message = await callback.message.answer("Сделайте репост нашего поста в Twitter и нажмите 'Проверить репост'.",
#                                                 reply_markup=new_keyboard)
#     await state.update_data(message_id=new_message.message_id)
#     await state.set_state(TaskState.waiting_for_repost_link)
#     await callback.answer()

# @router.callback_query(F.data == "check_repost")
# async def check_repost(callback: CallbackQuery, state: FSMContext):
#     data = await state.get_data()
#     if 'message_id' in data:
#         try:
#             await callback.bot.delete_message(callback.message.chat.id, data['message_id'])
#         except TelegramBadRequest:
#             pass

#     await callback.bot.send_chat_action(chat_id=callback.from_user.id, action=ChatAction.TYPING)
#     await asyncio.sleep(0.2)
#     new_message = await callback.message.answer("Пожалуйста, отправьте ссылку на ваш репост.")
#     await state.update_data(message_id=new_message.message_id)
#     await state.set_state(TaskState.waiting_for_repost_link)
#     await callback.answer()

# @router.message(TaskState.waiting_for_repost_link)
# async def receive_repost_link(message: Message, state: FSMContext):
#     user_id = message.from_user.id
#     repost_link = message.text.strip()
#     required_channel = "clown_ton"
#     reward_points = 1000

#     match = re.match(r"https://x\.com/[^/]+/status/\d+", repost_link)
#     data = await state.get_data()
#     if 'message_id' in data:
#         try:
#             await message.bot.delete_message(message.chat.id, data['message_id'])
#         except Exception as e:
#             logging.error(f"Failed to delete message: {e}")

#     if match and required_channel in repost_link:
#         if not await db.is_task_completed(user_id, "task_repost_completed"):
#             await db.add_bonus(user_id, reward_points)
#             await db.mark_task_completed(user_id, "task_repost_completed")
#             response_message = await message.answer(f"Репост проверен успешно! Вы заработали {reward_points} очков!",
#                                                     reply_markup=await get_task_keyboard(user_id))
#         else:
#             response_message = await message.answer("Вы уже выполнили это задание.",
#                                                     reply_markup=await get_task_keyboard(user_id))
#     else:
#         response_message = await message.answer("Ссылка на репост неверна. Попробуйте еще раз.",
#                                                 reply_markup=await get_task_keyboard(user_id))

#     await state.update_data(message_id=response_message.message_id)
#     await state.clear()

async def is_chat_boosted(bot, user_id):
    chat_id = "-1002087214352"  # ID вашего чата
    try:
        chat_member = await bot.get_chat_member(chat_id, user_id)
        if chat_member.is_boosted:
            return True
    except Exception as e:
        logging.error(f"Error checking chat boost for user {user_id}: {e}")
    return False

from aiogram.types import ChatBoostUpdated

@router.chat_boost()
async def chat_boost_handler(chat_boost: ChatBoostUpdated):
    try:
        user_id = chat_boost.boost.source.user_id  # Предположим, что у источника есть поле user_id
        chat_id = chat_boost.chat.id
        boost_id = chat_boost.boost.boost_id
        add_date = chat_boost.boost.add_date
        expiration_date = chat_boost.boost.expiration_date

        # Сохраните информацию о бусте в базе данных
        await db.save_chat_boost(user_id, chat_id, boost_id, add_date, expiration_date)

        logger.info(f"Boost updated: user {user_id}, chat {chat_id}, boost_id {boost_id}")

    except Exception as e:
        logger.error(f"Error processing chat boost: {e}")


@router.callback_query(F.data == "task_boost_2500")
async def task_boost_2500(callback: CallbackQuery):
    user_id = callback.from_user.id
    await ensure_db_connection()
    if await db.is_task_completed(user_id, "task_boost_completed"):
        await callback.answer("Это задание уже выполнено.", show_alert=True)
        return

    task_keyboard = await get_task_keyboard(user_id)
    new_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Проголосовать", url="https://t.me/boost/clown_token")],
        [InlineKeyboardButton(text="Проверить голос", callback_data="check_boost")],
        [InlineKeyboardButton(text="Назад", callback_data="tasks_ru")]
    ])

    await callback.message.delete()
    await callback.message.answer("Сделайте буст чата и нажмите 'Проверить буст'.",
                                  reply_markup=new_keyboard)
    await callback.answer()

logger = logging.getLogger(__name__)

from aiogram import Bot
from aiogram.types import ChatBoost, ChatBoostSourcePremium

async def get_chat_boosters(bot: Bot, chat_id: int):
    try:
        chat = await bot.get_chat(chat_id)
        if hasattr(chat, 'boosters'):
            return [booster.user.id for booster in chat.boosters if isinstance(booster.source, ChatBoostSourcePremium)]
        return []
    except Exception as e:
        logger.error(f"Error fetching chat boosters: {e}")
        return []
    
async def is_user_boosting_chat(bot: Bot, user_id: int, chat_id: int):
    boosters = await get_chat_boosters(bot, chat_id)
    return user_id in boosters


@router.callback_query(F.data == "check_boost")
async def check_boost(callback: CallbackQuery):
    await ensure_db_connection()
    user_id = callback.from_user.id
    reward_points = 2500
    task_keyboard = await get_task_keyboard(user_id)
    chat_id = -1002087214352  # ID вашего чата

    try:
        if await is_user_boosting_chat(callback.bot, user_id, chat_id):
            if not await db.is_task_completed(user_id, "task_boost_completed"):
                await db.add_bonus(user_id, reward_points)
                await db.mark_task_completed(user_id, "task_boost_completed")
                response_text = f"Буст успешно проверен! Вы заработали {reward_points} очков!"
                logger.info(f"User {user_id} received {reward_points} bonus points for boosting the chat.")
            else:
                response_text = "Вы уже выполнили это задание."
        else:
            response_text = "Буст не найден. Пожалуйста, попробуйте снова после выполнения буста."
            logger.info(f"User {user_id} did not boost the chat.")
    except Exception as e:
        logger.error(f"Error during boost check for user {user_id}: {e}")
        response_text = "Произошла ошибка при проверке буста. Пожалуйста, попробуйте снова позже."

    new_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назад к заданиям", callback_data="tasks_ru")]
    ])

    await callback.message.delete()
    await callback.message.answer(response_text, reply_markup=new_keyboard, parse_mode=ParseMode.HTML)
    await callback.answer()


async def check_subscription(bot: Bot, user_id: int, channel_id: int):
    try:
        member = await bot.get_chat_member(channel_id, user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logging.error(f"Ошибка при проверке подписки: {e}")
        return False

async def get_channels_keyboard(bot: Bot, user_id: int):
    await ensure_db_connection()
    is_subscribed_clown_token = await check_subscription(bot, user_id, '-1002087214352')
    is_subscribed_clown_chat = await check_subscription(bot, user_id, '-1002212790090')
    is_subscribed_clown_tokenton = await check_subscription(bot, user_id, '-1002178525662')
    is_subscribed_clown_chat_EN = await check_subscription(bot, user_id, '-1002197074859')

    channels_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"$CLOWN | TON {'✅' if is_subscribed_clown_token else '❌'}",
                url="https://t.me/clown_token"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"$CLOWN | TON Chat {'✅' if is_subscribed_clown_chat else '❌'}",
                url="https://t.me/clowntonchat"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"$CLOWN | TON (ENG) {'✅' if is_subscribed_clown_tokenton else '❌'}",
                url="https://t.me/clown_tokenton"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"$CLOWN | TON Chat(EN) {'✅' if is_subscribed_clown_chat_EN else '❌'}",
                url="https://t.me/clowntonchateng"
            )
        ],
        [InlineKeyboardButton(text="Проверить подписку", callback_data="checksub")],
        [InlineKeyboardButton(text="Назад", callback_data="back_ru")]
    ])
    return channels_keyboard