from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import CHANNELS

language_keyboard = InlineKeyboardBuilder()
language_keyboard.add(InlineKeyboardButton(text="Русский", callback_data="language_ru"))
language_keyboard.add(InlineKeyboardButton(text="English", callback_data="language_en"))
language_keyboard = language_keyboard.as_markup()

english_main = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🪪 Profile", callback_data="profile_en"),
    #  InlineKeyboardButton(text="💸 Wallet", callback_data="wallet_en")],
     InlineKeyboardButton(text="📝 Tasks", callback_data="tasks_en")],
    [InlineKeyboardButton(text="🏆 Leaderboard", callback_data="top10_en")],
    [InlineKeyboardButton(text="🔗 Referral link", callback_data="referal_link_en")],
    # [InlineKeyboardButton(text="💰 Presale", callback_data="preseil_en")],
    [InlineKeyboardButton(text="🤡 Website $CLOWN",url='https://clown.meme/')]
])

english_back = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🔙 Back", callback_data="back_en")]
])

main_presell_en = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="20 TON", callback_data="20 TON", url='ton://transfer/UQC9jmCfyIYb_RK3jba8qWMfJOBJlfqQ_hCym0IXd0yObLok?amount=20000000000&text=Donation'),
     InlineKeyboardButton(text="50 TON", callback_data="50 TON", url='ton://transfer/UQC9jmCfyIYb_RK3jba8qWMfJOBJlfqQ_hCym0IXd0yObLok?amount=50000000000&text=Donation'),
     InlineKeyboardButton(text="100 TON", callback_data="100 TON", url='ton://transfer/UQC9jmCfyIYb_RK3jba8qWMfJOBJlfqQ_hCym0IXd0yObLok?amount=100000000000&text=Donation')],
    [InlineKeyboardButton(text="Any amount", url='ton://transfer/UQC9jmCfyIYb_RK3jba8qWMfJOBJlfqQ_hCym0IXd0yObLok')],
    [InlineKeyboardButton(text="🔚 Back to menu", callback_data="back_en")]
], resize_keyboard=True, one_time_keyboard=True)

# task_keyboard = InlineKeyboardMarkup(inline_keyboard=[
#     [InlineKeyboardButton(text="Add $CLOWN to your name [2000 Points]", callback_data="task_name_2000_en")],
#     [InlineKeyboardButton(text="Subscribe to Global Channel [500 Points]", callback_data="task_subscribe_500_en")],
#     [InlineKeyboardButton(text="Boost Channel [2500 Points]", callback_data="task_boost_2500_en")],
#     [InlineKeyboardButton(text="Back", callback_data="back_en")]
# ])

def generate_subscribe_keyboard():
    keyboard = InlineKeyboardBuilder()
    # Add buttons for each channel from the list
    for name, chat_id, url in CHANNELS:
        keyboard.add(InlineKeyboardButton(text=name, url=url))
    # Add button to check subscription
    keyboard.row()  # Can be used to place the next button in a new row
    keyboard.add(InlineKeyboardButton(text="✅ Check subscription", callback_data="checksub_en"), InlineKeyboardButton(text="🔚 Back to menu", callback_data="back_en"))
    return keyboard.adjust(1).as_markup()

subscribe_channels = generate_subscribe_keyboard()

admin = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Analytics", callback_data="admin_analytics")],
    [InlineKeyboardButton(text="Send notification", callback_data="admin_send_notification")],
    [InlineKeyboardButton(text="⬅️ Back", callback_data="back_en")]
])

admin_back = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🔙 Back", callback_data="back_admin")]
])
