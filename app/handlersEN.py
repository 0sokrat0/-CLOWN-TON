import asyncio
import logging
import re

from aiogram import Bot, Router, F
from aiogram.enums import ChatAction, ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.handlers import show_main_menu
import app.keyboardsEN as kbe
import config as cfg
from database.db import Database
from aiogram.exceptions import TelegramBadRequest

router = Router()
db = Database(cfg.db_config)

english_main_text = (
    "Meme-coins have long turned into one big clown industry 🤡\n\n"
    "<b>But how do you know that you are a clown too?</b>\n\n"
    "➖ You constantly buy at the top and ride on highs\n"
    "➖ Your portfolio consists of shitcoins that have all fallen\n"
    "➖ You think the utility of a token really affects anything\n\n"
    "But being a clown is not shameful, being a poor clown is shameful.\n"
)

async def ensure_db_connection():
    if db.pool is None:
        await db.connect()
        if db.pool is None:
            raise Exception("Failed to connect to the database")
        logging.info("Database connected successfully.")

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

    await state.update_data(user_id=user_id, referer_id=referer_id, tg_name=tg_name)

    # Проверка подписки на основной канал
    if not await check_subscription(message.bot, user_id, cfg.CHANNELS[0][1]):
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Subscribe to $CLOWN | TON", url=cfg.CHANNELS[0][2])],
            [InlineKeyboardButton(text="Check Subscription", callback_data="check_subscription_en")]
        ])
        await message.answer(cfg.NOT_SUB_MESSAGE, reply_markup=keyboard)
        return

    # Если пользователь подписан
    new_user = not await db.user_exists(user_id)
    if new_user:
        await db.add_user(user_id, referer_id, tg_name)
        await db.increment_referral_count(referer_id)
        await db.add_bonus(referer_id, 300)
        await db.add_bonus(user_id, 100)
        await db.mark_bonus_awarded(user_id)

    language = await db.get_user_language(user_id)
    if not language:
        await message.answer(
            "👉 <b>Please select the language to continue:</b>\n"
            "👉 <b>Пожалуйста, выберите язык для продолжения:</b>\n",
            reply_markup=kbe.language_keyboard, parse_mode=ParseMode.HTML
        )
        await state.set_state(LanguageSelection.choosing_language)
    else:
        await show_main_menu(message, language)

@router.callback_query(F.data == "check_subscription_en")
async def check_subscription_handler(callback_query: CallbackQuery, state: FSMContext):
    await ensure_db_connection()
    user_id = callback_query.from_user.id
    data = await state.get_data()
    referer_id = data.get('referer_id')

    if await check_subscription_EN(callback_query.bot, user_id, cfg.CHANNELS[0][1]):
        await callback_query.message.delete()

        # Если пользователь новый
        new_user = not await db.user_exists(user_id)
        if new_user:
            tg_name = data.get('tg_name')
            await db.add_user(user_id, referer_id, tg_name)
            await db.increment_referral_count(referer_id)
            await db.add_bonus(referer_id, 300)
            await db.add_bonus(user_id, 100)
            await db.mark_bonus_awarded(user_id)
        
        # Если пользователь уже существует и бонусы еще не начислены
        elif referer_id and not await db.is_bonus_awarded(user_id):
            await db.increment_referral_count(referer_id)
            await db.add_bonus(referer_id, 300)
            await db.add_bonus(user_id, 100)
            await db.mark_bonus_awarded(user_id)

        await send_welcome(callback_query.message, state)
    else:
        await callback_query.answer("You are not subscribed to the main channel. Please subscribe to continue.")

async def check_subscription_EN(bot: Bot, user_id: int, channel_id: int):
    try:
        member = await bot.get_chat_member(channel_id, user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logging.error(f"Error checking subscription: {e}")
        return False
    

@router.callback_query(F.data == "back_en")
async def back(callback: CallbackQuery):
    await callback.answer("Back")
    try:
        await callback.message.delete()
    except TelegramBadRequest:
        pass
    await show_main_menu(callback.message, "en")

@router.callback_query(F.data == "profile_en")
async def profile(callback: CallbackQuery):
    await callback.bot.send_chat_action(chat_id=callback.from_user.id, action=ChatAction.TYPING)
    await ensure_db_connection()
    user_id = callback.from_user.id
    tg_name = callback.from_user.username or "Not specified"
    num_referrals = await db.count_referals(user_id)
    bonus = await db.get_bonus_points(user_id)

    profile_info = (
        "<b>Hey Clown, here's your profile?!</b>\n\n"
        f"🤡 <b>Name:</b> @{tg_name}\n"
        f"🤝 <b>Number of referrals:</b> {num_referrals}\n"
        f"🎁 <b>Number of bonus points:</b> {bonus}"
    )
    try:
        await callback.message.delete()
    except TelegramBadRequest:
        pass
    await callback.answer("Your profile")
    await callback.message.answer_photo(
        "AgACAgIAAxkBAAM8ZlpVAVFJvyjSuIhIub3rNyI_6gYAAknfMRsGodFKR8es8U2XJaQBAAMCAAN5AAM1BA",
        profile_info, parse_mode=ParseMode.HTML, reply_markup=kbe.english_back
    )

@router.callback_query(F.data == "referal_link_en")
async def referal(callback: CallbackQuery):
    await ensure_db_connection()
    await db.update_last_activity(callback.from_user.id)

    try:
        referral_code = await db.get_referral_code(callback.from_user.id)
        referral_link = f"https://t.me/{cfg.bot_name}?start={referral_code}"
        tg_name = callback.from_user.username or "Not specified"
        num_referals = await db.count_referals(callback.from_user.id)
        bonus = await db.get_bonus_points(callback.from_user.id)

        response_text = (
            f"Invite new clowns! Expand your pockets together!\n\n"
            f"1 referral = 300 points\n"
            f"🔗 **Your referral link:**\n"
            f"`{referral_link}`"
        )

        share_text = (
            f"Join $CLOWN and get bonuses!\n\n"
            f"Register using my link: {referral_link}"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Invite a Clown", switch_inline_query=share_text)],
            [InlineKeyboardButton(text="Back", callback_data="back_en")]
        ])

        await callback.message.delete()
        await callback.message.answer_photo(
            "AgACAgIAAxkBAANvZlpbyTSSnmNt-oz__s9IwoeXP0wAAlDfMRsGodFKz9SV8hvO42kBAAMCAAN5AAM1BA",
            response_text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard
        )
    except Exception as e:
        logging.error(f"Error in referal function: {e}")
        await callback.message.answer("An error occurred while generating your referral link. Please try again later.")
        await callback.answer()

@router.callback_query(F.data == "preseil_en")
async def presell_en(callback: CallbackQuery):
    await callback.bot.send_chat_action(chat_id=callback.from_user.id, action=ChatAction.TYPING)
    await ensure_db_connection()
    await db.update_last_activity(callback.from_user.id)
    response_text = (
        "<b>Presale is closed</b>\n\n"
        "Unfortunately, the presale is currently closed.\n\n"
    )
    try:
        await callback.message.delete()
    except TelegramBadRequest:
        pass
    await callback.message.answer_photo(
        "AgACAgIAAxkBAAO2ZlpnNM2x5HmobL0m8tB9C1TYHlMAAlrfMRsGodFKuQ2jmvis3pABAAMCAAN5AAM1BA",
        response_text, parse_mode=ParseMode.HTML, reply_markup=kbe.english_back
    )

@router.callback_query(F.data == "top10_en")
async def top10(callback: CallbackQuery):
    await db.update_last_activity(callback.from_user.id)
    await callback.bot.send_chat_action(chat_id=callback.from_user.id, action=ChatAction.TYPING)
    await ensure_db_connection()
    await db.update_last_activity(callback.from_user.id)

    top_users = await db.get_top_users(limit=10)
    top_text = "Top 10 points holders!\n\n"
    for i, user in enumerate(top_users, start=1):
        tg_name = user['tg_name'] if user['tg_name'] else "Not specified"
        top_text += f"{i}. @{tg_name} - {user['bonus_points']}\n"
    try:
        await callback.message.delete()
    except TelegramBadRequest:
        pass
    await callback.message.answer_photo(
        "AgACAgIAAxkBAAI4EmZpvdhI85OPwh3Z3pCMGHpxwM87AAJH3zEbpVJQSzW3clwPLOmZAQADAgADeQADNQQ",
        top_text, parse_mode=ParseMode.HTML, reply_markup=kbe.english_back
    )

async def get_task_keyboard_en(user_id):
    await ensure_db_connection()
    task_name_completed = await db.is_task_completed(user_id, "task_name_completed")
    task_subscribe_completed = await db.is_task_completed(user_id, "task_subscribe_completed")
    task_invite_completed = await db.is_task_completed(user_id, "task_invite_completed")
    task_boost_completed = await db.is_task_completed(user_id, "task_boost_completed")

    task_keyboard_en = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"Add $CLOWN to your name [2500 Points]{'✅' if task_name_completed else '❌'}",
                callback_data="task_name_2000_en" if not task_name_completed else "task_already_completed_en"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"Subscribe to $CLOWN | TON [2000 Points]{'✅' if task_subscribe_completed else '❌'}",
                callback_data="task_subscribe_500_en" if not task_subscribe_completed else "task_already_completed_en"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"Invite friends [1000 Points] {'✅' if task_invite_completed else '❌'}",
                callback_data="task_invite_friends_en" if not task_invite_completed else "task_already_completed_en"
            )
        ],
        # [
        #     InlineKeyboardButton(
        #         text=f"Boost chat {'✅' if task_boost_completed else '❌'}",
        #         callback_data="task_boost_2500_en" if not task_boost_completed else "task_already_completed_en"
        #     )
        # ],
        [
            InlineKeyboardButton(text="Back", callback_data="back_en")
        ]
    ])
    return task_keyboard_en

@router.callback_query(F.data == "tasks_en")
async def tasks(callback: CallbackQuery):
    await db.update_last_activity(callback.from_user.id)
    await callback.bot.send_chat_action(chat_id=callback.from_user.id, action=ChatAction.TYPING)
    user_id = callback.from_user.id
    task_keyboard_en = await get_task_keyboard_en(user_id)
    try:
        await callback.message.delete()
    except TelegramBadRequest:
        pass
    await callback.message.answer_photo(
        "AgACAgIAAxkBAAI6lmZp1y4jmaciyEdNVM2BgUDTK8xSAAJI3zEbpVJQSz-sPC72fb16AQADAgADeQADNQQ",
        "Complete tasks and earn points!\n\nCheck them daily and become the richest clown in our circus!",
        reply_markup=task_keyboard_en
    )

@router.callback_query(F.data == "task_name_2000_en")
async def task_name_2000(callback: CallbackQuery):
    user_id = callback.from_user.id
    await ensure_db_connection()
    if await db.is_task_completed(user_id, "task_name_completed"):
        await callback.answer("You have already completed this task.", show_alert=True)
        return

    reward_points = 2000
    task_keyboard = await get_task_keyboard_en(user_id)

    user_profile = await callback.bot.get_chat_member(callback.message.chat.id, user_id)
    if "clown" in (user_profile.user.full_name or "").lower():
        await db.add_bonus(user_id, reward_points)
        await db.mark_task_completed(user_id, "task_name_completed")
        await callback.answer(f"You have successfully added $CLOWN to your name and earned {reward_points} points!", show_alert=True)
        try:
            await callback.message.edit_reply_markup(reply_markup=task_keyboard)
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e):
                raise e
    else:
        await callback.answer("Your name does not contain '$CLOWN'. The task was not completed.", show_alert=True)

async def check_subscription(bot: Bot, user_id: int, channel_id: int):
    try:
        member = await bot.get_chat_member(channel_id, user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logging.error(f"Error checking subscription: {e}")
        return False

async def get_channels_keyboard(bot: Bot, user_id: int):
    await ensure_db_connection()
    is_subscribed_clown_token = await check_subscription(bot, user_id, cfg.CHANNELS[0][1])
    is_subscribed_clown_chat = await check_subscription(bot, user_id, cfg.CHANNELS[1][1])
    is_subscribed_clown_tokenton = await check_subscription(bot, user_id, cfg.CHANNELS[2][1])
    is_subscribed_clown_chat_EN = await check_subscription(bot, user_id, cfg.CHANNELS[3][1])

    channels_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"$CLOWN | TON {'✅' if is_subscribed_clown_token else '❌'}",
                url=cfg.CHANNELS[0][2]
            )
        ],
        [
            InlineKeyboardButton(
                text=f"$CLOWN | TON Chat {'✅' if is_subscribed_clown_chat else '❌'}",
                url=cfg.CHANNELS[1][2]
            )
        ],
        [
            InlineKeyboardButton(
                text=f"$CLOWN | TON (ENG) {'✅' if is_subscribed_clown_tokenton else '❌'}",
                url=cfg.CHANNELS[2][2]
            )
        ],
        [
            InlineKeyboardButton(
                text=f"$CLOWN | TON Chat(EN) {'✅' if is_subscribed_clown_chat_EN else '❌'}",
                url=cfg.CHANNELS[3][2]
            )
        ],
        [InlineKeyboardButton(text="Check subscription", callback_data="checksub_en")],
        [InlineKeyboardButton(text="Back", callback_data="back_en")]
    ])
    return channels_keyboard

@router.callback_query(F.data == "task_subscribe_500_en")
async def task_subscribe_500(callback: CallbackQuery):
    await ensure_db_connection()
    user_id = callback.from_user.id
    if not await db.is_task_completed(user_id, "task_subscribe_completed"):
        await callback.message.answer(
            "Subscribe to the channels, then click 'Check subscription' to earn 500 points.",
            reply_markup=await get_channels_keyboard(callback.bot, user_id)
        )
    else:
        await callback.message.answer("You have already completed this task.")
    await callback.answer()

async def check_and_award_all_subscriptions(bot: Bot, user_id: int, db: Database):
    if await check_all_subscriptions(bot, user_id) and not await db.is_task_completed(user_id, "task_subscribe_completed"):
        bonus_amount = 2000  # Общий бонус за подписку на все каналы
        await db.add_bonus(user_id, bonus_amount)
        await db.mark_task_completed(user_id, "task_subscribe_completed")
        return True
    return False

async def check_all_subscriptions(bot: Bot, user_id: int):
    for _, channel_id, _ in cfg.CHANNELS:
        if not await check_subscription(bot, user_id, channel_id):
            return False
    return True

@router.callback_query(F.data == "checksub_en")
async def check_subscription_handler(callback_query: CallbackQuery):
    await ensure_db_connection()
    user_id = callback_query.from_user.id

    if await check_and_award_all_subscriptions(callback_query.bot, user_id, db):
        message = "You are subscribed to all channels and received 2000 bonus points!"
    else:
        message = "You are not subscribed to all channels. Please subscribe to receive your bonus."
    
    await callback_query.message.answer(message, reply_markup=await get_task_keyboard_en(user_id))
    await callback_query.answer()

@router.callback_query(F.data == "task_invite_friends_en")
async def task_invite_friends(callback: CallbackQuery):
    await ensure_db_connection()
    user_id = callback.from_user.id
    reward_points = 1000
    task_keyboard = await get_task_keyboard_en(user_id)

    referrals_count = await db.count_referals(user_id)
    required_referrals = 5  # Required number of referrals to complete the task
    referral_code = await db.get_referral_code(user_id)
    referral_link = f"https://t.me/{cfg.bot_name}?start={referral_code}"

    if referrals_count >= required_referrals:
        if not await db.is_task_completed(user_id, "task_invite_completed"):
            await db.add_bonus(user_id, reward_points)
            await db.mark_task_completed(user_id, "task_invite_completed")
            response_text = f"You have successfully invited {required_referrals} friends and earned {reward_points} points! Total invited: {referrals_count}."
        else:
            response_text = f"You have already completed this task. Total invited: {referrals_count}."
    else:
        response_text = f"Invite {required_referrals} friends to complete this task. Total invited: {referrals_count}."

    share_text = (
        f"Join $CLOWN and get bonuses!\n\n"
        f"Register using my link: {referral_link}"
    )

    new_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Invite a Clown", switch_inline_query=share_text)],
        [InlineKeyboardButton(text="Back to tasks", callback_data="tasks_en")]
    ])

    try:
        await callback.message.delete()
    except TelegramBadRequest:
        pass

    await callback.message.answer(response_text, reply_markup=new_keyboard, parse_mode=ParseMode.HTML)
    await callback.answer()

@router.callback_query(F.data == "task_boost_2500_en")
async def task_boost_2500(callback: CallbackQuery):
    await ensure_db_connection()
    user_id = callback.from_user.id
    task_keyboard = await get_task_keyboard_en(user_id)

    new_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Boost the chat", url="https://t.me/boost/clown_token")],
        [InlineKeyboardButton(text="Check boost", callback_data="check_boost_en")],
        [InlineKeyboardButton(text="Back", callback_data="tasks_en")]
    ])
    try:
        await callback.message.delete()
    except TelegramBadRequest:
        pass
    await callback.message.answer("Boost the chat and click 'Check boost' to earn 2500 points.",
                                  reply_markup=new_keyboard)

@router.callback_query(F.data == "check_boost_en")
async def check_boost(callback: CallbackQuery):
    await ensure_db_connection()
    user_id = callback.from_user.id
    reward_points = 2500
    task_keyboard = await get_task_keyboard_en(user_id)

    await callback.message.delete()
    if await is_chat_boosted(callback.bot, user_id):
        if not await db.is_task_completed(user_id, "task_boost_completed"):
            await db.add_bonus(user_id, reward_points)
            await db.mark_task_completed(user_id, "task_boost_completed")
            response_text = f"You have successfully boosted the chat and earned {reward_points} points!"
        else:
            response_text = "You have already completed this task."
    else:
        response_text = "You have not boosted the chat. Task not completed."

    await callback.message.answer(response_text, reply_markup=task_keyboard)
    await callback.answer()

@router.callback_query(F.data == "task_already_completed_en")
async def task_already_completed(callback: CallbackQuery):
    await callback.answer("You have already completed this task.", show_alert=True)


@router.message(Command("change_language"))
async def command_change_language(message: Message, state: FSMContext):
    user_id = message.from_user.id

    # Проверка, если пользователь зарегистрирован и подписан на канал
    if await db.user_exists(user_id) and await check_subscription(message.bot, user_id, cfg.CHANNELS[0][1]):
        await message.answer(
            "👉 <b>Please select the language to continue:</b>\n"
            "👉 <b>Пожалуйста, выберите язык для продолжения:</b>\n",
            reply_markup=kbe.language_keyboard, parse_mode=ParseMode.HTML
        )
        await state.set_state(LanguageSelection.choosing_language)
    else:
        await message.answer("You need to be registered and subscribed to change the language.")


async def is_chat_boosted(bot: Bot, user_id: int):
    try:
        chat_member = await bot.get_chat_member(cfg.BOOST_CHAT_ID, user_id)
        if chat_member.status in ["member", "administrator", "creator"]:
            return True
    except Exception as e:
        logging.error(f"Error checking chat boost for user {user_id}: {e}")
    return False
