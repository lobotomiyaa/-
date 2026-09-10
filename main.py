import asyncio
import os

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from aiogram import Bot, Dispatcher, types
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo
)

BOT_TOKEN = os.environ["BOT_TOKEN"]

WEBAPP_URL = "https://sweet-rejoicing-production.up.railway.app/app"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
app = FastAPI()


@app.get("/")
async def home():
    return {
        "status": "ok",
        "service": "OtvaliVPN"
    }


@app.get("/app", response_class=HTMLResponse)
async def webapp():
    with open("webapp.html", "r", encoding="utf-8") as file:
        return file.read()


@dp.message()
async def handle_message(message: types.Message):

    if message.text == "/start":

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="❄ Открыть ОтвалиVPN",
                        web_app=WebAppInfo(url=WEBAPP_URL)
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
            "Открой приложение ниже:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )


@dp.callback_query()
async def callbacks(callback: types.CallbackQuery):

    if callback.data == "subscription":
        await callback.message.answer(
            "🪦 <b>Моя подписка</b>\n\n"
            "У тебя пока нет активной подписки.",
            parse_mode="HTML"
        )

    await callback.answer()


async def start_bot():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


@app.on_event("startup")
async def startup():
    asyncio.create_task(start_bot())


@app.on_event("shutdown")
async def shutdown():
    await bot.session.close()
