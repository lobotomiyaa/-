import asyncio
import os
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from aiogram import Bot, Dispatcher, types
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo,
    LabeledPrice,
)

BOT_TOKEN = os.environ["BOT_TOKEN"]

WEBAPP_URL = "https://sweet-rejoicing-production.up.railway.app/app"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
app = FastAPI()

# Временное хранилище подписок
subscriptions = {}


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
                        text="⭐ Купить 30 дней — 299",
                        callback_data="buy_30"
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

    if callback.data == "buy_30":

        await bot.send_invoice(
            chat_id=callback.from_user.id,
            title="ОтвалиVPN — 30 дней",
            description="Доступ к ОтвалиVPN на 30 дней.",
            payload="vpn_30_days",
            currency="XTR",
            prices=[
                LabeledPrice(
                    label="ОтвалиVPN — 30 дней",
                    amount=299
                )
            ]
        )

    elif callback.data == "subscription":

        user_id = callback.from_user.id
        expiration = subscriptions.get(user_id)

        if expiration and expiration > datetime.now(timezone.utc):

            remaining = expiration - datetime.now(timezone.utc)
            days = remaining.days

            await callback.message.answer(
                "🪡 <b>Моя подписка</b>\n\n"
                "🟢 Активна\n"
                f"⏱ Осталось примерно: {days} дней\n"
                f"📅 До: {expiration.strftime('%d.%m.%Y')}",
                parse_mode="HTML"
            )

        else:

            await callback.message.answer(
                "🪦 <b>Моя подписка</b>\n\n"
                "У тебя нет активной подписки.",
                parse_mode="HTML"
            )

    await callback.answer()


# Проверяем платёж перед списанием
@dp.pre_checkout_query()
async def process_pre_checkout(
    pre_checkout_query: types.PreCheckoutQuery
):

    if (
        pre_checkout_query.invoice_payload == "vpn_30_days"
        and pre_checkout_query.currency == "XTR"
        and pre_checkout_query.total_amount == 299
    ):
        await pre_checkout_query.answer(ok=True)

    else:
        await pre_checkout_query.answer(
            ok=False,
            error_message="Ошибка тарифа. Попробуйте оформить покупку заново."
        )


# Получаем подтверждённый платёж
@dp.message()
async def process_payment(message: types.Message):

    if not message.successful_payment:
        return

    payment = message.successful_payment

    if (
        payment.invoice_payload == "vpn_30_days"
        and payment.currency == "XTR"
        and payment.total_amount == 299
    ):

        expiration = datetime.now(timezone.utc) + timedelta(days=30)

        subscriptions[message.from_user.id] = expiration

        await message.answer(
            "🎉 <b>Оплата прошла успешно!</b>\n\n"
            "❄ ОтвалиVPN активирован.\n\n"
            "🧶 Тариф: 30 дней\n"
            f"📅 Действует до: {expiration.strftime('%d.%m.%Y')}\n\n"
            "🗡 VPN-конфигурацию подключим следующим этапом.",
            parse_mode="HTML"
        )


async def start_bot():

    await bot.delete_webhook(drop_pending_updates=True)

    await dp.start_polling(bot)


@app.on_event("startup")
async def startup():

    asyncio.create_task(start_bot())


@app.on_event("shutdown")
async def shutdown():

    await bot.session.close()
