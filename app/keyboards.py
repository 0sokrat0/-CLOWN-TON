from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import CHANNELS

language_keyboard = InlineKeyboardBuilder()
language_keyboard.add(InlineKeyboardButton(text="Русский", callback_data="language_ru"))
language_keyboard.add(InlineKeyboardButton(text="English", callback_data="language_en"))
language_keyboard = language_keyboard.as_markup()


russian_main = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🪪 Профиль", callback_data="profile_ru"),
    #  InlineKeyboardButton(text="💸 Кошелек", callback_data="wallet_ru")],
     InlineKeyboardButton(text="📝 Задания", callback_data="tasks_ru")],
    [InlineKeyboardButton(text="🏆 Таблица лидеров", callback_data="top10_ru")],
    [InlineKeyboardButton(text="🔗 Реферальная ссылка",callback_data="referal_link_ru")],
    # [InlineKeyboardButton(text="💰 Пресейл", callback_data="preseil_ru")],
    [InlineKeyboardButton(text="🤡 Сайт $CLOWN",url='https://clown.meme/')]

])

russian_back = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🔙 Назад", callback_data="back_ru")],
])




# main_presell_ru = InlineKeyboardMarkup(inline_keyboard=[
#     [InlineKeyboardButton(text="20 TON ", callback_data="20 TON",url='ton://transfer/UQC9jmCfyIYb_RK3jba8qWMfJOBJlfqQ_hCym0IXd0yObLok?amount=20000000000&text=Donation'),
#      InlineKeyboardButton(text="50 TON ", callback_data="50 TON",url='ton://transfer/UQC9jmCfyIYb_RK3jba8qWMfJOBJlfqQ_hCym0IXd0yObLok?amount=50000000000 &text=Donation'),
#      InlineKeyboardButton(text="100 TON ", callback_data="100 TON",url='ton://transfer/UQC9jmCfyIYb_RK3jba8qWMfJOBJlfqQ_hCym0IXd0yObLok?amount=100000000000&text=Donation')],
#     [InlineKeyboardButton(text="Любое кол-во ",url='ton://transfer/UQC9jmCfyIYb_RK3jba8qWMfJOBJlfqQ_hCym0IXd0yObLok')],
#     [InlineKeyboardButton(text="🔚 Вернуться в меню",callback_data="back_ru")]
# ], resize_keyboard=True, one_time_keyboard=True
# )


# task_keyboard = InlineKeyboardMarkup(inline_keyboard=[
#     [InlineKeyboardButton(text="Добавьте к имени $CLOWN[2000 Points]", callback_data="task_name_2000")],
#     [InlineKeyboardButton(text="Подпишитесь на Global Channel[500 Points]", callback_data="task_subscribe_500")],
#     [InlineKeyboardButton(text="Boost Канал[2500 Points]", callback_data="task_boost_2500")],
#     [InlineKeyboardButton(text="Назад", callback_data="back_ru")]
# ])

# def generate_subscribe_keyboard():
#     keyboard = InlineKeyboardBuilder()
#     # Добавляем кнопки для каждого канала из списка
#     for name, chat_id, url in CHANNELS:
#         keyboard.add(InlineKeyboardButton(text=name, url=url))
#     # Добавляем кнопку для проверки подписки
#     keyboard.row()  # Можно использовать для размещения следующей кнопки в новой строке
#     keyboard.add(InlineKeyboardButton(text="✅ Проверить подписку", callback_data="checksub"), InlineKeyboardButton(text="🔚Назад в меню",callback_data="back_menu"))
#     return keyboard.adjust(1).as_markup()
#
# subscribe_channels = generate_subscribe_keyboard()
#
#
# def generate_subscribe_keyboard():
#     keyboard = InlineKeyboardBuilder()
#     # Добавляем кнопки для каждого канала из списка
#     for name, chat_id, url in CHANNELS:
#         keyboard.add(InlineKeyboardButton(text=name, url=url))
#     # Добавляем кнопку для проверки подписки
#     keyboard.row()  # Можно использовать для размещения следующей кнопки в новой строке
#     keyboard.add(InlineKeyboardButton(text="✅ Проверить подписку", callback_data="checksub"), InlineKeyboardButton(text="🔚Назад в меню",callback_data="back_menu"))
#     return keyboard.adjust(1).as_markup()
#
# subscribe_channels = generate_subscribe_keyboard()
#



admin = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Пользовательская аналитика", callback_data="admin_analytics")],
    [InlineKeyboardButton(text="Список пользователей", callback_data="admin_user_list:0")],
    [InlineKeyboardButton(text="Экспорт таблицы пользователей", callback_data="export_users")],
    [InlineKeyboardButton(text="Назад в меню", callback_data="back_ru")]
])

admin_back = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Назад", callback_data="admin_panel_back")]
])