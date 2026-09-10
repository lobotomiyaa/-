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
# Базу данных подключим в самом конце.
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
# START
# ============================================================

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
# ПОКУПКА ТАРИФА
# ============================================================

@dp.callback_query()
async def callbacks(callback: types.CallbackQuery):

    # --------------------------------------------------------
    # ПОКУПКА
    # --------------------------------------------------------

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
                f"Доступ к ОтвалиVPN на "
                f"{tariff['days']} дней."
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

    # --------------------------------------------------------
    # МОЯ ПОДПИСКА
    # --------------------------------------------------------

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
# ПРОВЕРКА ПЕРЕД ОПЛАТОЙ
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

    tariff_id = payload.replace("vpn_", "").replace("_days", "")
    tariff = TARIFFS.get(tariff_id)

    if not tariff:
        await pre_checkout_query.answer(
            ok=False,
            error_message="Этот тариф больше недоступен."
        )
        return

    if pre_checkout_query.currency != "XTR":
        await pre_checkout_query.answer(
            ok=False,
            error_message="Неверная валюта платежа."
        )
        return

    if pre_checkout_query.total_amount != tariff["price"]:
        await pre_checkout_query.answer(
            ok=False,
            error_message="Цена тарифа изменилась. Оформите покупку заново."
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

    tariff_id = payload.replace("vpn_", "").replace("_days", "")
    tariff = TARIFFS.get(tariff_id)

    if not tariff:
        return

    # Проверяем реальную оплату
    if payment.currency != "XTR":
        return

    if payment.total_amount != tariff["price"]:
        return

    user_id = message.from_user.id

    now = datetime.now(timezone.utc)

    old_expiration = subscriptions.get(user_id)

    # Если подписка ещё активна —
    # продлеваем её от старой даты.
    if old_expiration and old_expiration > now:
        start_from = old_expiration
    else:
        start_from = now

    expiration = start_from + timedelta(
        days=tariff["days"]
    )

    subscriptions[user_id] = expiration

    # Сохраняем ID платежа.
    # В будущем он будет нужен для БД/возвратов.
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
