import logging
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from aiogram.dispatcher.middlewares import BaseMiddleware
from aiogram.dispatcher.event.bases import CancelHandler
from config import CHANNELS

class SubscriptionMiddleware(BaseMiddleware):
    def __init__(self, bot: Bot, channel_id: str, channel_link: str):
        self.bot = bot
        self.channel_id = channel_id
        self.channel_link = channel_link
        super().__init__()

    async def __call__(self, handler, event, data):
        if isinstance(event, CallbackQuery):
            user_id = event.from_user.id
        elif isinstance(event, Message):
            user_id = event.from_user.id
        else:
            return await handler(event, data)

        try:
            member = await self.bot.get_chat_member(self.channel_id, user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                raise ValueError
        except:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Subscribe to the channel", url=self.channel_link)],
                [InlineKeyboardButton(text="✅ Check subscription", callback_data="check_subscription")]
            ])
            if isinstance(event, CallbackQuery):
                await event.message.answer(
                    "Чтобы пользоваться ботом, подпишитесь на наш канал.\n"
                    "To use the bot, subscribe to our channel.",
                    reply_markup=keyboard
                )
                raise CancelHandler()
            elif isinstance(event, Message):
                await event.answer(
                    "Чтобы пользоваться ботом, подпишитесь на наш канал.\n"
                    "To use the bot, subscribe to our channel.",
                    reply_markup=keyboard
                )
                raise CancelHandler()

        return await handler(event, data)
