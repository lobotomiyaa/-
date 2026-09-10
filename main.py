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

# Твой Telegram ID.
# Он уже должен быть добавлен в Railway Variables.
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
#
# БД НЕ НУЖНА.
#
# 3X-UI сама хранит VPN-клиента и срок его действия.
# Здесь мы временно храним данные, которые нужны боту.
# ============================================================

subscriptions = {}

vpn_links = {}

# Состояние администратора при выдаче VPN
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
# ГЛАВНЫЙ MESSAGE HANDLER
# ============================================================

@dp.message()
async def handle_message(message: types.Message):

    user_id = message.from_user.id
    text = message.text or ""


    # ========================================================
    # УСПЕШНАЯ ОПЛАТА
    # ========================================================

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


        now = datetime.now(timezone.utc)

        old_expiration = subscriptions.get(
            user_id
        )


        # Если подписка ещё действует,
        # продлеваем от её текущего окончания.
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


        # ----------------------------------------------------
        # СООБЩЕНИЕ ПОКУПАТЕЛЮ
        # ----------------------------------------------------

        await message.answer(

            "🎉 <b>Оплата прошла успешно!</b>\n\n"

            f"{tariff['name']}\n"
            f"💫 Оплачено: {tariff['price']} ⭐\n\n"

            "🟢 Подписка активирована.\n"

            f"📅 Действует до: "
            f"{expiration.strftime('%d.%m.%Y')}\n\n"

            "🪦 <b>VPN сейчас выдаётся.</b>\n\n"

            "Как только VPN будет готов, "
            "ссылка придёт сюда автоматически.",

            parse_mode="HTML"
        )


        # ----------------------------------------------------
        # ИНФОРМАЦИЯ ДЛЯ АДМИНА
        # ----------------------------------------------------

        username = message.from_user.username

        if username:

            user_display = f"@{username}"

        else:

            first_name = (
                message.from_user.first_name
                or "Без имени"
            )

            user_display = first_name


        admin_keyboard = InlineKeyboardMarkup(

            inline_keyboard=[

                [
                    InlineKeyboardButton(
                        text="🪦 ВЫДАТЬ VPN",
                        callback_data=f"admin_give_{user_id}"
                    )
                ]
            ]
        )


        try:

            await bot.send_message(

                chat_id=ADMIN_ID,

                text=(

                    "💰 <b>НОВАЯ ПОКУПКА</b>\n\n"

                    f"👤 Пользователь: "
                    f"{user_display}\n"

                    f"🆔 Telegram ID: "
                    f"<code>{user_id}</code>\n\n"

                    f"📦 Тариф: "
                    f"{tariff['name']}\n"

                    f"💫 Оплачено: "
                    f"{tariff['price']} ⭐\n\n"

                    f"📅 Действует до: "
                    f"{expiration.strftime('%d.%m.%Y')}\n\n"

                    "⚠️ <b>Нужно выдать VPN.</b>"

                ),

                reply_markup=admin_keyboard,

                parse_mode="HTML"
            )

        except Exception as error:

            print(
                "Ошибка отправки уведомления админу:",
                error
            )


        return


    # ========================================================
    # /START
    # ========================================================

    if text == "/start":

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


    # ========================================================
    # /MYID
    # ========================================================

    if text == "/myid":

        await message.answer(

            "🆔 Твой Telegram ID:\n\n"
            f"<code>{user_id}</code>",

            parse_mode="HTML"
        )

        return


    # ========================================================
    # /GIVEVPN
    # Оставляем старую команду как запасной вариант.
    # ========================================================

    if text == "/givevpn":

        if user_id != ADMIN_ID:

            await message.answer(
                "⛔ У тебя нет доступа к этой команде."
            )

            return


        admin_states[user_id] = {
            "step": "user_id"
        }


        await message.answer(

            "👤 <b>Выдача VPN</b>\n\n"

            "Отправь Telegram ID пользователя.\n\n"

            "Для отмены: /cancel",

            parse_mode="HTML"
        )

        return


    # ========================================================
    # /CANCEL
    # ========================================================

    if text == "/cancel":

        if user_id in admin_states:

            del admin_states[user_id]


        await message.answer(
            "❌ Операция отменена."
        )

        return


    # ========================================================
    # СТАРАЯ РУЧНАЯ ВЫДАЧА
    # ========================================================

    if user_id == ADMIN_ID:

        state = admin_states.get(user_id)


        if state:

            # ------------------------------------------------
            # ВВОД TELEGRAM ID
            # ------------------------------------------------

            if state["step"] == "user_id":

                try:

                    target_user_id = int(
                        text.strip()
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

                    "🔗 <b>Теперь нужна VPN-ссылка.</b>\n\n"

                    "Зайди в 3X-UI, создай клиента "
                    "и скопируй его subscription-ссылку.\n\n"

                    "Отправь ссылку сюда.\n\n"

                    "Для отмены: /cancel",

                    parse_mode="HTML"
                )

                return


            # ------------------------------------------------
            # ВВОД VPN ССЫЛКИ
            # ------------------------------------------------

            if state["step"] == "vpn_link":

                vpn_link = text.strip()


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


                del admin_states[user_id]


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


                await message.answer(

                    "✅ <b>VPN выдан!</b>\n\n"

                    f"👤 ID: "
                    f"<code>{target_user_id}</code>\n"

                    f"📅 До: "
                    f"{expiration_text}",

                    parse_mode="HTML"
                )


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

                except Exception as error:

                    print(
                        "Ошибка отправки VPN:",
                        error
                    )

                    await message.answer(

                        "⚠️ VPN сохранён, "
                        "но сообщение пользователю "
                        "отправить не получилось.\n\n"

                        "Проверь, что пользователь "
                        "уже запускал бота через /start."
                    )

                return


# ============================================================
# CALLBACKS
# ============================================================

@dp.callback_query()
async def callbacks(
    callback: types.CallbackQuery
):

    data = callback.data or ""


    # ========================================================
    # АДМИН — ВЫДАТЬ VPN
    # ========================================================

    if data.startswith("admin_give_"):

        if callback.from_user.id != ADMIN_ID:

            await callback.answer(
                "⛔ Нет доступа.",
                show_alert=True
            )

            return


        target_user_id = int(
            data.replace(
                "admin_give_",
                ""
            )
        )


        admin_states[
            callback.from_user.id
        ] = {

            "step": "vpn_link",

            "target_user_id":
                target_user_id
        }


        await callback.message.answer(

            "🪦 <b>Выдача VPN</b>\n\n"

            f"👤 Пользователь:\n"
            f"<code>{target_user_id}</code>\n\n"

            "Теперь создай клиента в 3X-UI "
            "и отправь сюда его "
            "<b>subscription-ссылку</b>.\n\n"

            "После отправки ссылки бот "
            "автоматически передаст её пользователю.\n\n"

            "Для отмены: /cancel",

            parse_mode="HTML"
        )


        await callback.answer()

        return


    # ========================================================
    # ПОКУПКА
    # ========================================================

    if data.startswith("buy_"):

        tariff_id = data.replace(
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


        await callback.answer()

        return


    # ========================================================
    # МОЯ ПОДПИСКА
    # ========================================================

    if data == "subscription":

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


        await callback.answer()

        return


    # ========================================================
    # УСЛОВИЯ
    # ========================================================

    if data == "terms":

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


        await callback.answer()

        return


    # ========================================================
    # ПОДДЕРЖКА
    # ========================================================

    if data == "support":

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

        return


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


    tariff = TARIFFS.get(
        tariff_id
    )


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
# /TERMS
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


# ============================================================
# /PAYSUPPORT
# ============================================================

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
