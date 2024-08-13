import logging
import uuid
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters.state import StateFilter
from spam.dramatiq_tasks import prepare_mass_mailing, spam_service, notify_admins
from aiogram.exceptions import TelegramBadRequest

from config import TOKEN, ADMINS

# Определяем состояние для FSM (Finite State Machine) - конечный автомат
class SpamState(StatesGroup):
    waiting_for_language = State()
    waiting_for_content = State()
    waiting_for_buttons = State()
    waiting_for_button_text = State()
    waiting_for_button_url = State()
    waiting_for_confirmation = State()

# Инициализация маршрутизатора и диспетчера для обработки сообщений
router = Router()
dp = Dispatcher()

# Команда для старта создания рассылки
@router.message(Command("spam"), F.from_user.id.in_(ADMINS))
async def spam_start(message: Message, state: FSMContext):
    languages_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="spam_language_ru")],
        [InlineKeyboardButton(text="🇬🇧 Английский", callback_data="spam_language_en")],
        [InlineKeyboardButton(text="🔃 Все языки", callback_data="spam_language_all")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_spam_creation")]
    ])
    await message.answer("🌐 Выберите язык аудитории для рассылки:", reply_markup=languages_keyboard)
    await state.set_state(SpamState.waiting_for_language)

# Обработка выбора языка
@router.callback_query(F.data.startswith("spam_language_"))
async def select_language(callback_query: CallbackQuery, state: FSMContext):
    language = callback_query.data.split("_")[-1]
    await state.update_data(language=language)

    await callback_query.message.edit_text("✍️ Пожалуйста, отправьте текст и/или фото для рассылки.")
    await state.set_state(SpamState.waiting_for_content)

# Обработка получения контента для рассылки
@router.message(StateFilter(SpamState.waiting_for_content), F.from_user.id.in_(ADMINS))
async def receive_spam_content(message: Message, state: FSMContext):
    data = await state.get_data()
    photo = message.photo[-1].file_id if message.photo else None
    caption = message.html_text or message.caption  # Используем html_text для сохранения форматирования

    if not caption and not photo:
        await message.answer("❗ Пожалуйста, отправьте текст и/или фото для рассылки.")
        return

    await state.update_data(photo=photo, caption=caption)

    add_buttons_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Добавить кнопки", callback_data="add_buttons"),
         InlineKeyboardButton(text="❌ Пропустить", callback_data="skip_buttons")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_language")]
    ])

    await message.answer("➕ Вы хотите добавить кнопки к сообщению?", reply_markup=add_buttons_keyboard)
    await state.set_state(SpamState.waiting_for_buttons)

# Обработка возврата к выбору языка
@router.callback_query(F.data == "back_to_language")
async def back_to_language(callback_query: CallbackQuery, state: FSMContext):
    languages_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="spam_language_ru")],
        [InlineKeyboardButton(text="🇬🇧 Английский", callback_data="spam_language_en")],
        [InlineKeyboardButton(text="🔃 Все языки", callback_data="spam_language_all")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_spam_creation")]
    ])
    await callback_query.message.edit_text("🌐 Выберите язык аудитории для рассылки:", reply_markup=languages_keyboard)
    await state.set_state(SpamState.waiting_for_language)

# Обработка добавления кнопок
@router.callback_query(F.data == "add_buttons")
async def ask_for_buttons(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.edit_text("📝 Пожалуйста, отправьте текст для кнопки.")
    await state.set_state(SpamState.waiting_for_button_text)

# Обработка получения текста кнопки
@router.message(StateFilter(SpamState.waiting_for_button_text), F.from_user.id.in_(ADMINS))
async def receive_button_text(message: Message, state: FSMContext):
    button_text = message.text
    await state.update_data(button_text=button_text)
    await message.answer("🌐 Теперь отправьте URL для этой кнопки.")
    await state.set_state(SpamState.waiting_for_button_url)

# Обработка получения URL кнопки
@router.message(StateFilter(SpamState.waiting_for_button_url), F.from_user.id.in_(ADMINS))
async def receive_button_url(message: Message, state: FSMContext):
    button_url = message.text
    data = await state.get_data()
    button_text = data.get("button_text")

    # Добавление кнопки в список
    keyboard = data.get("keyboard", [])
    keyboard.append([InlineKeyboardButton(text=button_text, url=button_url)])
    await state.update_data(keyboard=keyboard)

    # Формирование строки для отображения списка кнопок
    buttons_list = data.get("buttons_list", "")
    buttons_list += f"\n- <b>{button_text}</b>: {button_url}"
    await state.update_data(buttons_list=buttons_list)

    add_more_buttons_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить еще одну кнопку", callback_data="add_buttons"),
         InlineKeyboardButton(text="✅ Завершить и отправить", callback_data="finish_buttons")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_content")]
    ])

    await message.answer("🔘 Кнопка добавлена. Хотите добавить еще одну кнопку?", reply_markup=add_more_buttons_keyboard)

# Обработка возврата к вводу контента
@router.callback_query(F.data == "back_to_content")
async def back_to_content(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.edit_text("✍️ Пожалуйста, отправьте текст и/или фото для рассылки.")
    await state.set_state(SpamState.waiting_for_content)

# Обработка завершения добавления кнопок
@router.callback_query(F.data == "finish_buttons")
async def finish_buttons(callback_query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    photo = data.get('photo')
    caption = data.get('caption')
    buttons_list = data.get('buttons_list', '')  # Получаем список кнопок
    keyboard = InlineKeyboardMarkup(inline_keyboard=data.get('keyboard', []))

    confirm_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Начать рассылку", callback_data="confirm_spam")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_spam_creation")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_buttons")]
    ])

    final_message = f"📄 Ваше сообщение будет выглядеть так:\n\n{caption}"
    if buttons_list:
        final_message += f"\n\n🔘 Используемые кнопки:{buttons_list}"

    if photo:
        await callback_query.message.answer_photo(photo=photo, caption=caption, parse_mode="HTML")
    await callback_query.message.answer(final_message, reply_markup=confirm_keyboard, parse_mode="HTML")

    await state.set_state(SpamState.waiting_for_confirmation)

# Обработка возврата к добавлению кнопок
@router.callback_query(F.data == "back_to_buttons")
async def back_to_buttons(callback_query: CallbackQuery, state: FSMContext):
    add_more_buttons_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить еще одну кнопку", callback_data="add_more_buttons"),
         InlineKeyboardButton(text="✅ Завершить и отправить", callback_data="finish_buttons")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_content")]
    ])

    # Проверяем наличие текста в сообщении перед его редактированием
    if callback_query.message.text:
        await callback_query.message.edit_text("🔘 Кнопка добавлена. Хотите добавить еще одну кнопку?",
                                               reply_markup=add_more_buttons_keyboard)
    else:
        await callback_query.message.answer("🔘 Кнопка добавлена. Хотите добавить еще одну кнопку?",
                                            reply_markup=add_more_buttons_keyboard)

    await state.set_state(SpamState.waiting_for_buttons)

# Обработка пропуска добавления кнопок
@router.callback_query(F.data == "skip_buttons")
async def skip_buttons(callback_query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    photo = data.get('photo')
    caption = data.get('caption')
    buttons_list = data.get('buttons_list', '')  # Получаем список кнопок

    confirm_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Начать рассылку", callback_data="confirm_spam")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_spam_creation")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_content")]
    ])

    final_message = f"📄 Ваше сообщение будет выглядеть так:\n\n{caption}"
    if buttons_list:
        final_message += f"\n\n🔘 Используемые кнопки:{buttons_list}"

    if photo:
        await callback_query.message.answer_photo(photo=photo, caption=caption, parse_mode="HTML")
    await callback_query.message.answer(final_message, reply_markup=confirm_keyboard, parse_mode="HTML")

    await state.set_state(SpamState.waiting_for_confirmation)

# Обработка подтверждения рассылки
@router.callback_query(F.data == "confirm_spam")
async def confirm_spam(callback_query: CallbackQuery, state: FSMContext):
    try:
        data = await state.get_data()
        language = data.get('language')
        photo = data.get('photo')
        caption = data.get('caption')
        keyboard = data.get('keyboard')
        campaign_id = str(uuid.uuid4())

        if not caption and not photo:
            await callback_query.message.answer("❗ Необходимо предоставить текст или фото для рассылки.")
            return

        # Преобразуем кнопки в словари перед отправкой задачи
        keyboard_data = [[{'text': btn.text, 'url': btn.url} for btn in row] for row in keyboard] if keyboard else None

        # Запуск задачи на отправку рассылки
        prepare_mass_mailing.send(language, photo, caption, campaign_id, keyboard_data)

        await callback_query.message.answer("🚀 Рассылка запущена!", parse_mode="HTML")
    except TelegramBadRequest as e:
        logging.error(f"Skipping BadRequest error: {e}")
        await callback_query.message.answer("⚠️ Произошла ошибка, но рассылка продолжается.", parse_mode="HTML")
    except Exception as e:
        logging.error(f"Unhandled exception: {e}")
        await callback_query.message.answer("❗ Произошла ошибка при запуске рассылки.", parse_mode="HTML")
    finally:
        await state.clear()


