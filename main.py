import asyncio
import os

from fastapi import FastAPI
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = os.environ["BOT_TOKEN"]

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
app = FastAPI()


@dp.message()
async def handle_message(message: types.Message):
    if message.text == "/start":
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="❄ Купить ОтвалиVPN",
                        callback_data="buy"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🪡 Моя подписка",
                        callback_data="subscription"
                    )
                ]
            ]
        )

        await message.answer(
            "👋 Добро пожаловать в <b>ОтвалиVPN</b>!\n\n"
            "❄ Быстрый и стабильный VPN\n"
            "🗡 Защищённое соединение\n"
            "🧶 Удобное подключение\n"
            "🪦 Без лишних сложностей\n\n"
            "Выбери действие ниже:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )


@dp.callback_query()
async def callbacks(callback: types.CallbackQuery):
    if callback.data == "buy":
        await callback.message.answer(
            "❄ <b>Тарифы ОтвалиVPN</b>\n\n"
            "🪡 7 дней — 99 ⭐\n"
            "🧶 30 дней — 299 ⭐\n"
            "🗡 90 дней — 699 ⭐",
            parse_mode="HTML"
        )

    elif callback.data == "subscription":
        await callback.message.answer(
            "🪦 <b>Моя подписка</b>\n\n"
            "У тебя пока нет активной подписки.",
            parse_mode="HTML"
        )

    await callback.answer()


@app.get("/")
async def home():
    return {
        "status": "ok",
        "service": "OtvaliVPN"
    }


async def start_bot():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


@app.on_event("startup")
async def startup():
    asyncio.create_task(start_bot())


@app.on_event("shutdown")
async def shutdown():
    await bot.session.close()
