import asyncio
import os
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

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


# ============================================================
# ТАРИФЫ
# ============================================================

TARIFFS = {
    "7": {
        "days": 7,
        "price": 59,
        "name": "🪡 7 дней",
    },
    "30": {
        "days": 30,
        "price": 129,
        "name": "❄ 30 дней",
    },
    "90": {
        "days": 90,
        "price": 399,
        "name": "🧶 90 дней",
    },
}


# Временное хранилище.
# БД подключим в самом конце.
subscriptions = {}


# ============================================================
# WEB
# ============================================================

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


# ============================================================
# СОЗДАНИЕ INVOICE ДЛЯ MINI APP
# ============================================================

class InvoiceRequest(BaseModel):
    tariff: str


@app.post("/create-invoice")
async def create_invoice(data: InvoiceRequest):

    tariff = TARIFFS.get(data.tariff)

    if not tariff:
        return {
            "ok": False,
            "error": "Тариф не найден"
        }

    payload = f"vpn_{data.tariff}_days"

    invoice_link = await bot.create_invoice_link(
        title=f"ОтвалиVPN — {tariff['days']} дней",
        description=(
            f"Доступ к ОтвалиVPN "
            f"на {tariff['days']} дней."
        ),
        payload=payload,
        currency="XTR",
        prices=[
            LabeledPrice(
                label=f"ОтвалиVPN — {tariff['days']} дней",
                amount=tariff["price"]
            )
        ]
    )

    return {
        "ok": True,
        "invoice": invoice_link
    }


# ============================================================
# TELEGRAM /START
# ============================================================

@dp.message()
async def handle_message(message: types.Message):
    if message.text == "/terms":

        await message.answer(
            "📜 <b>Условия использования ОтвалиVPN</b>\n\n"
            "1. После успешной оплаты пользователь получает "
            "доступ к VPN на выбранный срок.\n\n"
            "2. Срок подписки начинается после успешного "
            "завершения оплаты.\n\n"
            "3. Не передавайте данные доступа другим людям.\n\n"
            "4. При возникновении проблем с оплатой или "
            "доступом обратитесь в поддержку через /paysupport.\n\n"
            "5. Использование VPN должно соответствовать "
            "законодательству вашей страны.\n\n"
            "🪦 ОтвалиVPN",
            parse_mode="HTML"
        )

        return


    if message.text == "/paysupport":

        await message.answer(
            "🛠 <b>Поддержка ОтвалиVPN</b>\n\n"
            "Если проблема связана с оплатой, подпиской "
            "или доступом к VPN — напишите в поддержку.\n\n"
            "Укажите:\n"
            "• ваш Telegram username;\n"
            "• какой тариф покупали;\n"
            "• описание проблемы;\n"
            "• если есть — данные платежа.\n\n"
            "🪦 ОтвалиVPN",
            parse_mode="HTML"
        )

        return
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
                        text="🪡 7 дней — 59 ⭐",
                        callback_data="buy_7"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="❄ 30 дней — 129 ⭐",
                        callback_data="buy_30"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🧶 90 дней — 399 ⭐",
                        callback_data="buy_90"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🪦 Моя подписка",
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
            "Выбери тариф:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )


# ============================================================
# ПОКУПКА И ПОДПИСКА
# ============================================================

@dp.callback_query()
async def callbacks(callback: types.CallbackQuery):

    if callback.data.startswith("buy_"):

        tariff_id = callback.data.replace("buy_", "")
        tariff = TARIFFS.get(tariff_id)

        if not tariff:
            await callback.answer(
                "Тариф не найден",
                show_alert=True
            )
            return

        await bot.send_invoice(
            chat_id=callback.from_user.id,
            title=f"ОтвалиVPN — {tariff['days']} дней",
            description=(
                f"Доступ к ОтвалиVPN "
                f"на {tariff['days']} дней."
            ),
            payload=f"vpn_{tariff_id}_days",
            currency="XTR",
            prices=[
                LabeledPrice(
                    label=f"ОтвалиVPN — {tariff['days']} дней",
                    amount=tariff["price"]
                )
            ]
        )

    elif callback.data == "subscription":

        user_id = callback.from_user.id
        expiration = subscriptions.get(user_id)

        if expiration and expiration > datetime.now(timezone.utc):

            remaining = expiration - datetime.now(timezone.utc)
            days_left = remaining.days

            await callback.message.answer(
                "🪦 <b>Моя подписка</b>\n\n"
                "🟢 Статус: активна\n"
                f"⏱ Осталось: {days_left} дней\n"
                f"📅 До: {expiration.strftime('%d.%m.%Y')}",
                parse_mode="HTML"
            )

        else:

            await callback.message.answer(
                "🪦 <b>Моя подписка</b>\n\n"
                "🔴 Активной подписки нет.\n\n"
                "Выбери тариф через /start.",
                parse_mode="HTML"
            )

    await callback.answer()


# ============================================================
# PRE-CHECKOUT
# ============================================================

@dp.pre_checkout_query()
async def process_pre_checkout(
    pre_checkout_query: types.PreCheckoutQuery
):

    payload = pre_checkout_query.invoice_payload

    if not payload.startswith("vpn_") or not payload.endswith("_days"):

        await pre_checkout_query.answer(
            ok=False,
            error_message="Неизвестный тариф."
        )
        return

    tariff_id = payload.replace(
        "vpn_", ""
    ).replace(
        "_days", ""
    )

    tariff = TARIFFS.get(tariff_id)

    if not tariff:

        await pre_checkout_query.answer(
            ok=False,
            error_message="Этот тариф недоступен."
        )
        return

    if pre_checkout_query.currency != "XTR":

        await pre_checkout_query.answer(
            ok=False,
            error_message="Неверная валюта."
        )
        return

    if pre_checkout_query.total_amount != tariff["price"]:

        await pre_checkout_query.answer(
            ok=False,
            error_message="Цена тарифа изменилась."
        )
        return

    await pre_checkout_query.answer(ok=True)


# ============================================================
# УСПЕШНАЯ ОПЛАТА
# ============================================================

@dp.message()
async def process_payment(message: types.Message):

    if not message.successful_payment:
        return

    payment = message.successful_payment

    payload = payment.invoice_payload

    if not payload.startswith("vpn_") or not payload.endswith("_days"):
        return

    tariff_id = payload.replace(
        "vpn_", ""
    ).replace(
        "_days", ""
    )

    tariff = TARIFFS.get(tariff_id)

    if not tariff:
        return

    if payment.currency != "XTR":
        return

    if payment.total_amount != tariff["price"]:
        return

    user_id = message.from_user.id

    now = datetime.now(timezone.utc)

    old_expiration = subscriptions.get(user_id)

    if old_expiration and old_expiration > now:
        start_from = old_expiration
    else:
        start_from = now

    expiration = start_from + timedelta(
        days=tariff["days"]
    )

    subscriptions[user_id] = expiration

    payment_id = payment.telegram_payment_charge_id

    await message.answer(
        "🎉 <b>Оплата прошла успешно!</b>\n\n"
        f"{tariff['name']}\n"
        f"💫 Оплачено: {tariff['price']} ⭐\n\n"
        "🟢 Подписка активирована.\n"
        f"📅 Действует до: {expiration.strftime('%d.%m.%Y')}\n\n"
        "🗡 VPN-доступ подключим следующим этапом.",
        parse_mode="HTML"
    )


# ============================================================
# ЗАПУСК
# ============================================================

async def start_bot():

    await bot.delete_webhook(
        drop_pending_updates=True
    )

    await dp.start_polling(bot)


@app.on_event("startup")
async def startup():

    asyncio.create_task(start_bot())


@app.on_event("shutdown")
async def shutdown():

    await bot.session.close()
