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
    BotCommand,
    MenuButtonWebApp,
)


# ============================================================
# НАСТРОЙКИ
# ============================================================

BOT_TOKEN = os.environ["BOT_TOKEN"]

# Telegram ID администратора.
# Добавим его в Railway Variables.
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))

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


# ============================================================
# ВРЕМЕННОЕ ХРАНИЛИЩЕ
# БД подключим позже
# ============================================================

subscriptions = {}

# VPN-ссылки пользователей
vpn_links = {}

# Состояние ручной выдачи VPN администратором
admin_states = {}


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

    with open(
        "webapp.html",
        "r",
        encoding="utf-8"
    ) as file:

        return file.read()


# ============================================================
# СОЗДАНИЕ INVOICE ИЗ MINI APP
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
                label=(
                    f"ОтвалиVPN — "
                    f"{tariff['days']} дней"
                ),
                amount=tariff["price"]
            )
        ]
    )

    return {
        "ok": True,
        "invoice": invoice_link
    }


# ============================================================
# ЕДИНЫЙ MESSAGE HANDLER
# ============================================================

@dp.message()
async def handle_message(message: types.Message):

    # --------------------------------------------------------
    # УСПЕШНАЯ ОПЛАТА
    # --------------------------------------------------------

    if message.successful_payment:

        payment = message.successful_payment

        payload = payment.invoice_payload

        if (
            not payload.startswith("vpn_")
            or not payload.endswith("_days")
        ):
            return

        tariff_id = (
            payload
            .replace("vpn_", "")
            .replace("_days", "")
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

        if (
            old_expiration
            and old_expiration > now
        ):

            start_from = old_expiration

        else:

            start_from = now

        expiration = (
            start_from
            + timedelta(days=tariff["days"])
        )

        subscriptions[user_id] = expiration

        payment_id = (
            payment.telegram_payment_charge_id
        )

        # Если VPN уже был выдан ранее,
        # пока оставляем существующую ссылку.
        existing_link = vpn_links.get(user_id)

        if existing_link:

            await message.answer(

                "🎉 <b>Оплата прошла успешно!</b>\n\n"

                f"{tariff['name']}\n"
                f"💫 Оплачено: {tariff['price']} ⭐\n\n"

                "🟢 Подписка продлена.\n"

                f"📅 До: "
                f"{expiration.strftime('%d.%m.%Y')}\n\n"

                "🔗 <b>Твоя VPN-подписка:</b>\n"
                f"<code>{existing_link}</code>\n\n"

                "📱 Добавь эту ссылку в Happ или "
                "другое приложение для VPN.",

                parse_mode="HTML"
            )

        else:

            await message.answer(

                "🎉 <b>Оплата прошла успешно!</b>\n\n"

                f"{tariff['name']}\n"
                f"💫 Оплачено: {tariff['price']} ⭐\n\n"

                "🟢 Подписка активирована.\n"

                f"📅 До: "
                f"{expiration.strftime('%d.%m.%Y')}\n\n"

                "🪦 <b>VPN ещё выдаётся вручную.</b>\n\n"

                "После создания VPN-подписки "
                "вы получите ссылку здесь.",

                parse_mode="HTML"
            )

        return


    # --------------------------------------------------------
    # /START
    # --------------------------------------------------------

    if message.text == "/start":

        keyboard = InlineKeyboardMarkup(

            inline_keyboard=[

                [
                    InlineKeyboardButton(
                        text="❄ Открыть ОтвалиVPN",
                        web_app=WebAppInfo(
                            url=WEBAPP_URL
                        )
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
                ],

                [
                    InlineKeyboardButton(
                        text="📜 Условия",
                        callback_data="terms"
                    ),

                    InlineKeyboardButton(
                        text="🛠 Поддержка",
                        callback_data="support"
                    )
                ]
            ]
        )

        await message.answer(

            "👋 Добро пожаловать "
            "в <b>ОтвалиVPN</b>!\n\n"

            "❄ Быстрый и простой VPN\n"
            "🗡 Защищённое соединение\n"
            "🧶 Удобное подключение\n"
            "🪦 Без лишних сложностей\n\n"

            "Выбери действие:",

            reply_markup=keyboard,

            parse_mode="HTML"
        )

        return


    # --------------------------------------------------------
    # /MYID
    # --------------------------------------------------------

    if message.text == "/myid":

        await message.answer(
            f"🆔 Твой Telegram ID:\n\n"
            f"<code>{message.from_user.id}</code>",
            parse_mode="HTML"
        )

        return


    # --------------------------------------------------------
    # /GIVEVPN
    # --------------------------------------------------------

    if message.text == "/givevpn":

        if message.from_user.id != ADMIN_ID:

            await message.answer(
                "⛔ У тебя нет доступа к этой команде."
            )

            return

        admin_states[message.from_user.id] = {
            "step": "user_id"
        }

        await message.answer(

            "👤 <b>Выдача VPN</b>\n\n"

            "Отправь Telegram ID пользователя, "
            "которому нужно выдать VPN.\n\n"

            "Например:\n"
            "<code>123456789</code>\n\n"

            "Для отмены напиши /cancel.",

            parse_mode="HTML"
        )

        return


    # --------------------------------------------------------
    # /CANCEL
    # --------------------------------------------------------

    if message.text == "/cancel":

        if message.from_user.id in admin_states:

            del admin_states[message.from_user.id]

        await message.answer(
            "❌ Операция отменена."
        )

        return


    # --------------------------------------------------------
    # РУЧНАЯ ВЫДАЧА VPN
    # --------------------------------------------------------

    if message.from_user.id == ADMIN_ID:

        state = admin_states.get(
            message.from_user.id
        )

        if state:

            # -----------------------------------------------
            # ШАГ 1 — TELEGRAM ID
            # -----------------------------------------------

            if state["step"] == "user_id":

                try:

                    target_user_id = int(
                        message.text.strip()
                    )

                except:

                    await message.answer(
                        "❌ Неверный Telegram ID.\n\n"
                        "Отправь только цифры."
                    )

                    return

                state["target_user_id"] = (
                    target_user_id
                )

                state["step"] = "vpn_link"

                await message.answer(

                    "🔗 Отлично.\n\n"

                    "Теперь зайди в 3X-UI, "
                    "создай пользователя и скопируй "
                    "его <b>subscription-ссылку</b>.\n\n"

                    "После этого отправь ссылку сюда.\n\n"

                    "Для отмены: /cancel",

                    parse_mode="HTML"
                )

                return


            # -----------------------------------------------
            # ШАГ 2 — VPN LINK
            # -----------------------------------------------

            if state["step"] == "vpn_link":

                vpn_link = message.text.strip()

                if not (
                    vpn_link.startswith("http://")
                    or vpn_link.startswith("https://")
                    or vpn_link.startswith("vless://")
                    or vpn_link.startswith("vmess://")
                ):

                    await message.answer(

                        "❌ Похоже, это не VPN-ссылка.\n\n"

                        "Отправь subscription-ссылку "
                        "из 3X-UI ещё раз."
                    )

                    return

                target_user_id = (
                    state["target_user_id"]
                )

                vpn_links[target_user_id] = vpn_link

                del admin_states[
                    message.from_user.id
                ]

                # Получаем срок подписки
                expiration = subscriptions.get(
                    target_user_id
                )

                if expiration:

                    expiration_text = (
                        expiration.strftime(
                            "%d.%m.%Y"
                        )
                    )

                else:

                    expiration_text = (
                        "срок не найден"
                    )

                # Сообщение админу
                await message.answer(

                    "✅ <b>VPN выдан!</b>\n\n"

                    f"👤 ID: <code>{target_user_id}</code>\n"
                    f"📅 До: {expiration_text}\n\n"

                    "🔗 Ссылка сохранена.",

                    parse_mode="HTML"
                )

                # Отправляем пользователю
                try:

                    await bot.send_message(

                        chat_id=target_user_id,

                        text=(

                            "🪦 <b>ОтвалиVPN активирован!</b>\n\n"

                            "🎉 Твоя VPN-подписка готова.\n\n"

                            f"📅 Действует до: "
                            f"{expiration_text}\n\n"

                            "🔗 <b>Твоя ссылка подписки:</b>\n\n"

                            f"<code>{vpn_link}</code>\n\n"

                            "📱 <b>Как подключиться:</b>\n"
                            "1. Скопируй ссылку.\n"
                            "2. Открой Happ.\n"
                            "3. Добавь подписку по ссылке.\n"
                            "4. Обнови подписку.\n"
                            "5. Подключись.\n\n"

                            "🗡 Не передавай эту ссылку другим людям."
                        ),

                        parse_mode="HTML"
                    )

                except Exception:

                    await message.answer(

                        "⚠️ VPN сохранён, "
                        "но бот не смог отправить "
                        "сообщение пользователю.\n\n"

                        "Возможно, пользователь ещё "
                        "не запускал бота через /start."
                    )

                return


# ============================================================
# КНОПКИ
# ============================================================

@dp.callback_query()
async def callbacks(
    callback: types.CallbackQuery
):

    # --------------------------------------------------------
    # ПОКУПКА
    # --------------------------------------------------------

    if callback.data.startswith("buy_"):

        tariff_id = callback.data.replace(
            "buy_",
            ""
        )

        tariff = TARIFFS.get(tariff_id)

        if not tariff:

            await callback.answer(
                "Тариф не найден",
                show_alert=True
            )

            return

        await bot.send_invoice(

            chat_id=callback.from_user.id,

            title=(
                f"ОтвалиVPN — "
                f"{tariff['days']} дней"
            ),

            description=(
                f"Доступ к ОтвалиVPN "
                f"на {tariff['days']} дней."
            ),

            payload=f"vpn_{tariff_id}_days",

            currency="XTR",

            prices=[

                LabeledPrice(

                    label=(
                        f"ОтвалиVPN — "
                        f"{tariff['days']} дней"
                    ),

                    amount=tariff["price"]
                )
            ]
        )

    # --------------------------------------------------------
    # ПОДПИСКА
    # --------------------------------------------------------

    elif callback.data == "subscription":

        user_id = callback.from_user.id

        expiration = subscriptions.get(
            user_id
        )

        vpn_link = vpn_links.get(
            user_id
        )

        if (
            expiration
            and expiration >
            datetime.now(timezone.utc)
        ):

            remaining = (
                expiration -
                datetime.now(timezone.utc)
            )

            days_left = remaining.days

            text = (

                "🪦 <b>Моя подписка</b>\n\n"

                "🟢 Статус: активна\n"

                f"⏱ Осталось: "
                f"{days_left} дней\n"

                f"📅 До: "
                f"{expiration.strftime('%d.%m.%Y')}\n\n"
            )

            if vpn_link:

                text += (

                    "🔗 <b>VPN-подписка:</b>\n\n"
                    f"<code>{vpn_link}</code>\n\n"
                    "📱 Добавь ссылку в Happ."
                )

            else:

                text += (
                    "⏳ VPN-ссылка ещё "
                    "выдаётся вручную."
                )

            await callback.message.answer(
                text,
                parse_mode="HTML"
            )

        else:

            await callback.message.answer(

                "🪦 <b>Моя подписка</b>\n\n"

                "🔴 Активной подписки нет.\n\n"

                "Выбери тариф выше.",

                parse_mode="HTML"
            )

    # --------------------------------------------------------
    # УСЛОВИЯ
    # --------------------------------------------------------

    elif callback.data == "terms":

        await callback.message.answer(

            "📜 <b>Условия использования "
            "ОтвалиVPN</b>\n\n"

            "После успешной оплаты пользователь "
            "получает доступ к VPN на выбранный срок.\n\n"

            "Срок подписки начинается после "
            "успешного завершения оплаты.\n\n"

            "Не передавайте данные доступа "
            "другим людям.\n\n"

            "Использование VPN должно соответствовать "
            "законодательству вашей страны.\n\n"

            "По вопросам оплаты и доступа "
            "обращайтесь в поддержку.",

            parse_mode="HTML"
        )

    # --------------------------------------------------------
    # ПОДДЕРЖКА
    # --------------------------------------------------------

    elif callback.data == "support":

        await callback.message.answer(

            "🛠 <b>Поддержка ОтвалиVPN</b>\n\n"

            "Если возникла проблема с оплатой, "
            "подпиской или VPN-доступом — "
            "напишите в поддержку.\n\n"

            "Укажите:\n"
            "• ваш Telegram username;\n"
            "• тариф;\n"
            "• описание проблемы;\n"
            "• информацию о платеже, если она есть.",

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

    payload = (
        pre_checkout_query.invoice_payload
    )

    if (
        not payload.startswith("vpn_")
        or not payload.endswith("_days")
    ):

        await pre_checkout_query.answer(

            ok=False,

            error_message=(
                "Неизвестный тариф."
            )
        )

        return

    tariff_id = (
        payload
        .replace("vpn_", "")
        .replace("_days", "")
    )

    tariff = TARIFFS.get(tariff_id)

    if not tariff:

        await pre_checkout_query.answer(

            ok=False,

            error_message=(
                "Этот тариф недоступен."
            )
        )

        return

    if (
        pre_checkout_query.currency
        != "XTR"
    ):

        await pre_checkout_query.answer(

            ok=False,

            error_message=(
                "Неверная валюта."
            )
        )

        return

    if (
        pre_checkout_query.total_amount
        != tariff["price"]
    ):

        await pre_checkout_query.answer(

            ok=False,

            error_message=(
                "Цена тарифа изменилась."
            )
        )

        return

    await pre_checkout_query.answer(
        ok=True
    )


# ============================================================
# КОМАНДЫ
# ============================================================

@dp.message(
    lambda message:
    message.text == "/terms"
)
async def terms_command(
    message: types.Message
):

    await message.answer(

        "📜 <b>Условия использования "
        "ОтвалиVPN</b>\n\n"

        "После успешной оплаты пользователь "
        "получает доступ к VPN на выбранный срок.\n\n"

        "Срок подписки начинается после "
        "успешного завершения оплаты.\n\n"

        "Не передавайте данные доступа "
        "другим людям.\n\n"

        "Использование VPN должно соответствовать "
        "законодательству вашей страны.\n\n"

        "По вопросам оплаты и доступа "
        "обращайтесь в поддержку.",

        parse_mode="HTML"
    )


@dp.message(
    lambda message:
    message.text == "/paysupport"
)
async def paysupport_command(
    message: types.Message
):

    await message.answer(

        "🛠 <b>Поддержка ОтвалиVPN</b>\n\n"

        "Если возникла проблема с оплатой, "
        "подпиской или VPN-доступом — "
        "напишите в поддержку.\n\n"

        "Укажите:\n"
        "• ваш Telegram username;\n"
        "• тариф;\n"
        "• описание проблемы;\n"
        "• информацию о платеже, если она есть.",

        parse_mode="HTML"
    )


# ============================================================
# НАСТРОЙКА МЕНЮ TELEGRAM
# ============================================================

async def setup_bot():

    await bot.set_my_commands(

        commands=[

            BotCommand(
                command="start",
                description="❄ Запустить ОтвалиVPN"
            ),

            BotCommand(
                command="terms",
                description="📜 Условия использования"
            ),

            BotCommand(
                command="paysupport",
                description="🛠 Поддержка по оплате"
            )
        ]
    )

    await bot.set_chat_menu_button(

        menu_button=MenuButtonWebApp(

            text="❄ ОтвалиVPN",

            web_app=WebAppInfo(
                url=WEBAPP_URL
            )
        )
    )


# ============================================================
# ЗАПУСК
# ============================================================

async def start_bot():

    await bot.delete_webhook(
        drop_pending_updates=True
    )

    await setup_bot()

    await dp.start_polling(bot)


@app.on_event("startup")
async def startup():

    asyncio.create_task(
        start_bot()
    )


@app.on_event("shutdown")
async def shutdown():

    await bot.session.close()
