import os
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from aiohttp import web

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo,
    MenuButtonWebApp,
    BotCommand,
)
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode


# =========================
# НАСТРОЙКИ
# =========================

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))

FRIEND_ADMIN_ID = 1404271536

ADMIN_IDS = {
    ADMIN_ID,
    FRIEND_ADMIN_ID,
}

# Реквизиты находятся в Railway Variables
PAYMENT_DETAILS = os.environ.get(
    "PAYMENT_DETAILS",
    "Реквизиты для оплаты пока не настроены."
)

WEBAPP_URL = (
    "https://sweet-rejoicing-production.up.railway.app/app"
)


# =========================
# ТАРИФЫ
# =========================

TARIFFS = {

    7: {
        "days": 7,
        "price": 60,
        "name": "7 дней",
        "emoji": "🪦",
    },

    14: {
        "days": 14,
        "price": 100,
        "name": "14 дней",
        "emoji": "📜",
    },

    30: {
        "days": 30,
        "price": 200,
        "name": "30 дней",
        "emoji": "📜",
    },

    90: {
        "days": 90,
        "price": 399,
        "name": "90 дней",
        "emoji": "🕊️",
    },
}


# =========================
# ДАННЫЕ
# =========================

subscriptions = {}

pending_payments = {}

admin_states = {}

# Пользователи, которые уже получили пробу
trial_users = set()


# =========================
# BOT
# =========================

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(
        parse_mode=ParseMode.HTML
    )
)

dp = Dispatcher()


# =========================
# ГЛАВНОЕ МЕНЮ
# =========================

def main_keyboard():

    return InlineKeyboardMarkup(
        inline_keyboard=[

            [
                InlineKeyboardButton(
                    text="🪡 Открыть ОтвалиVPN",
                    web_app=WebAppInfo(
                        url=WEBAPP_URL
                    )
                )
            ],

            [
                InlineKeyboardButton(
                    text="🎁 3 дня бесплатно",
                    callback_data="trial"
                )
            ],

            [
                InlineKeyboardButton(
                    text="🪦 7 дней — 60 руб",
                    callback_data="buy_7"
                )
            ],

            [
                InlineKeyboardButton(
                    text="📜 14 дней — 100 руб",
                    callback_data="buy_14"
                )
            ],

            [
                InlineKeyboardButton(
                    text="📜 30 дней — 200 руб",
                    callback_data="buy_30"
                )
            ],

            [
                InlineKeyboardButton(
                    text="🕊️ 90 дней — 399 руб",
                    callback_data="buy_90"
                )
            ],

            [
                InlineKeyboardButton(
                    text="💷 Моя подписка",
                    callback_data="my_subscription"
                )
            ],

            [
                InlineKeyboardButton(
                    text="⚔️ Условия",
                    callback_data="terms"
                ),

                InlineKeyboardButton(
                    text="🪡 Поддержка",
                    callback_data="support"
                ),
            ],
        ]
    )


# =========================
# ПОДТВЕРЖДЕНИЕ ПОКУПКИ
# =========================

def payment_confirm_keyboard(days: int):

    return InlineKeyboardMarkup(
        inline_keyboard=[

            [
                InlineKeyboardButton(
                    text="✅ Подтвердить оплату",
                    callback_data=f"confirm_buy_{days}"
                )
            ],

            [
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="cancel_payment"
                )
            ],
        ]
    )


# =========================
# РЕКВИЗИТЫ
# =========================

def payment_details_keyboard(days: int):

    return InlineKeyboardMarkup(
        inline_keyboard=[

            [
                InlineKeyboardButton(
                    text="✅ Я оплатил",
                    callback_data=f"paid_{days}"
                )
            ],

            [
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="cancel_payment"
                )
            ],
        ]
    )


# =========================
# АДМИНСКАЯ КНОПКА ОПЛАТЫ
# =========================

def admin_payment_keyboard(
    user_id: int,
    days: int
):

    return InlineKeyboardMarkup(
        inline_keyboard=[

            [
                InlineKeyboardButton(
                    text="✅ ПОДТВЕРДИТЬ ОПЛАТУ",
                    callback_data=(
                        f"confirm_payment_{user_id}_{days}"
                    )
                )
            ],

            [
                InlineKeyboardButton(
                    text="❌ ОТКЛОНИТЬ",
                    callback_data=(
                        f"reject_payment_{user_id}"
                    )
                )
            ],
        ]
    )


# =========================
# АДМИНСКАЯ КНОПКА ПРОБЫ
# =========================

def admin_trial_keyboard(
    user_id: int
):

    return InlineKeyboardMarkup(
        inline_keyboard=[

            [
                InlineKeyboardButton(
                    text="✅ ВЫДАТЬ 3 ДНЯ",
                    callback_data=f"confirm_trial_{user_id}"
                )
            ],

            [
                InlineKeyboardButton(
                    text="❌ ОТКЛОНИТЬ",
                    callback_data=f"reject_trial_{user_id}"
                )
            ],
        ]
    )


# =========================
# /START
# =========================

@dp.message(Command("start"))
async def start(message: Message):

    text = (
        "🪡 <b>ОтвалиVPN</b>\n\n"
        "Быстрый VPN без лишнего гемора.\n\n"
        "🎁 Попробуй бесплатно 3 дня "
        "или выбери тариф ниже."
    )

    await message.answer(
        text,
        reply_markup=main_keyboard()
    )


# =========================
# WEB APP
# =========================

@dp.message(F.web_app_data)
async def web_app_data(message: Message):

    data = message.web_app_data.data

    if not data.startswith("buy:"):
        return

    try:
        days = int(
            data.split(":")[1]
        )
    except (ValueError, IndexError):
        return

    if days not in TARIFFS:
        return

    tariff = TARIFFS[days]

    await send_buy_confirmation(
        message,
        days,
        tariff["price"]
    )


# =========================
# ПЕРЕД РЕКВИЗИТАМИ
# =========================

async def send_buy_confirmation(
    message: Message,
    days: int,
    price: int
):

    tariff = TARIFFS[days]

    text = (
        "⚠️ <b>Подтверждение покупки</b>\n\n"

        f"📦 Тариф: <b>{tariff['name']}</b>\n"
        f"💰 Стоимость: <b>{price} руб</b>\n\n"

        "После подтверждения тебе будут "
        "показаны реквизиты для перевода.\n\n"

        "<b>Ты действительно хочешь оплатить "
        "этот тариф?</b>"
    )

    await message.answer(
        text,
        reply_markup=payment_confirm_keyboard(days)
    )


# =========================
# КНОПКА ТАРИФА
# =========================

@dp.callback_query(
    F.data.startswith("buy_")
)
async def buy_callback(
    callback: CallbackQuery
):

    try:

        days = int(
            callback.data.split("_")[1]
        )

    except (ValueError, IndexError):

        await callback.answer(
            "Ошибка"
        )

        return

    if days not in TARIFFS:

        await callback.answer(
            "Такого тарифа нет"
        )

        return

    tariff = TARIFFS[days]

    await callback.answer()

    await send_buy_confirmation(
        callback.message,
        days,
        tariff["price"]
    )


# =========================
# ПОДТВЕРДИЛ ПОКУПКУ
# =========================

@dp.callback_query(
    F.data.startswith("confirm_buy_")
)
async def confirm_buy(
    callback: CallbackQuery
):

    try:

        days = int(
            callback.data.split("_")[2]
        )

    except (ValueError, IndexError):

        await callback.answer(
            "Ошибка"
        )

        return

    if days not in TARIFFS:

        await callback.answer(
            "Ошибка тарифа"
        )

        return

    tariff = TARIFFS[days]

    user_id = callback.from_user.id

    pending_payments[user_id] = {
        "days": days,
        "price": tariff["price"],
        "created": datetime.now(timezone.utc),
    }

    await callback.answer(
        "Реквизиты открыты"
    )

    text = (
        "💳 <b>Реквизиты для оплаты</b>\n\n"

        f"📦 Тариф: <b>{tariff['name']}</b>\n"
        f"💰 Сумма: <b>{tariff['price']} руб</b>\n\n"

        f"<code>{PAYMENT_DETAILS}</code>\n\n"

        "Переведи ровно указанную сумму.\n\n"

        "После перевода нажми:\n"
        "✅ <b>Я оплатил</b>\n\n"

        "Оплата проверяется администратором вручную."
    )

    await callback.message.edit_text(
        text,
        reply_markup=payment_details_keyboard(days)
    )


# =========================
# Я ОПЛАТИЛ
# =========================

@dp.callback_query(
    F.data.startswith("paid_")
)
async def paid_callback(
    callback: CallbackQuery
):

    try:

        days = int(
            callback.data.split("_")[1]
        )

    except (ValueError, IndexError):

        await callback.answer(
            "Ошибка"
        )

        return

    if days not in TARIFFS:

        await callback.answer(
            "Ошибка"
        )

        return

    user_id = callback.from_user.id

    tariff = TARIFFS[days]

    pending_payments[user_id] = {
        "days": days,
        "price": tariff["price"],
        "created": datetime.now(timezone.utc),
    }

    await callback.answer(
        "Заявка отправлена!"
    )

    await callback.message.edit_text(

        "🟡 <b>Ожидаем подтверждение оплаты</b>\n\n"

        f"📦 Тариф: {tariff['name']}\n"
        f"💰 Сумма: {tariff['price']} руб\n\n"

        "Администратор проверит перевод "
        "и подтвердит оплату."
    )

    username = (
        f"@{callback.from_user.username}"
        if callback.from_user.username
        else "без username"
    )

    admin_text = (

        "💰 <b>НОВАЯ ОПЛАТА</b>\n\n"

        f"👤 Пользователь: {username}\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"📦 Тариф: <b>{tariff['name']}</b>\n"
        f"💵 Сумма: <b>{tariff['price']} руб</b>\n\n"

        "Проверь поступление денег "
        "в банковском приложении."
    )

    for admin_id in ADMIN_IDS:

        if admin_id == 0:
            continue

        try:

            await bot.send_message(

                admin_id,

                admin_text,

                reply_markup=admin_payment_keyboard(
                    user_id,
                    days
                )
            )

        except Exception as e:

            logging.error(
                f"Ошибка отправки админу "
                f"{admin_id}: {e}"
            )


# =========================
# ПОДТВЕРДИТЬ ОПЛАТУ
# =========================

@dp.callback_query(
    F.data.startswith("confirm_payment_")
)
async def confirm_payment(
    callback: CallbackQuery
):

    if callback.from_user.id not in ADMIN_IDS:

        await callback.answer(
            "Нет доступа"
        )

        return

    parts = callback.data.split("_")

    try:

        user_id = int(parts[2])
        days = int(parts[3])

    except (ValueError, IndexError):

        await callback.answer(
            "Ошибка"
        )

        return

    if days not in TARIFFS:

        await callback.answer(
            "Ошибка тарифа"
        )

        return

    tariff = TARIFFS[days]

    if user_id not in pending_payments:

        await callback.answer(
            "Заявка уже обработана."
        )

        return

    now = datetime.now(timezone.utc)

    old_sub = subscriptions.get(
        user_id
    )

    if (
        old_sub
        and old_sub["expires"] > now
    ):

        expires = (
            old_sub["expires"]
            + timedelta(days=days)
        )

    else:

        expires = (
            now
            + timedelta(days=days)
        )

    subscriptions[user_id] = {

        "days": days,

        "price": tariff["price"],

        "expires": expires,
    }

    del pending_payments[user_id]

    admin_states[
        callback.from_user.id
    ] = {

        "type": "vpn_for_payment",

        "user_id": user_id,

        "days": days,
    }

    await callback.answer(
        "Оплата подтверждена"
    )

    await callback.message.edit_text(

        callback.message.text

        + "\n\n"
        "✅ <b>ОПЛАТА ПОДТВЕРЖДЕНА</b>"
    )

    await bot.send_message(

        callback.from_user.id,

        "🔗 <b>Отправь VPN subscription URL</b>\n\n"
        "Просто вставь ссылку из 3X-UI."
    )

    try:

        await bot.send_message(

            user_id,

            "✅ <b>Оплата подтверждена!</b>\n\n"
            "Администратор сейчас выдаёт тебе VPN."
        )

    except Exception:
        pass


# =========================
# ОТКЛОНИТЬ ОПЛАТУ
# =========================

@dp.callback_query(
    F.data.startswith("reject_payment_")
)
async def reject_payment(
    callback: CallbackQuery
):

    if callback.from_user.id not in ADMIN_IDS:

        await callback.answer(
            "Нет доступа"
        )

        return

    try:

        user_id = int(
            callback.data.split("_")[2]
        )

    except (ValueError, IndexError):

        await callback.answer(
            "Ошибка"
        )

        return

    pending_payments.pop(
        user_id,
        None
    )

    await callback.answer(
        "Оплата отклонена"
    )

    await callback.message.edit_text(

        callback.message.text

        + "\n\n"
        "❌ <b>ОПЛАТА ОТКЛОНЕНА</b>"
    )

    try:

        await bot.send_message(

            user_id,

            "❌ <b>Оплата не подтверждена.</b>\n\n"
            "Если ты уже переводил деньги, "
            "обратись в поддержку."
        )

    except Exception:
        pass


# =========================
# 🎁 БЕСПЛАТНАЯ ПРОБА
# =========================

@dp.callback_query(
    F.data == "trial"
)
async def trial_callback(
    callback: CallbackQuery
):

    user_id = callback.from_user.id

    if user_id in trial_users:

        await callback.answer(
            "Ты уже использовал бесплатную пробу.",
            show_alert=True
        )

        return

    if user_id in subscriptions:

        await callback.answer(
            "У тебя уже есть подписка.",
            show_alert=True
        )

        return

    await callback.answer(
        "Заявка отправлена!"
    )

    username = (
        f"@{callback.from_user.username}"
        if callback.from_user.username
        else "без username"
    )

    admin_text = (

        "🎁 <b>НОВАЯ ЗАЯВКА НА ПРОБУ</b>\n\n"

        f"👤 Пользователь: {username}\n"
        f"🆔 ID: <code>{user_id}</code>\n\n"

        "Пользователь хочет получить "
        "<b>3 дня бесплатно</b>."
    )

    for admin_id in ADMIN_IDS:

        if admin_id == 0:
            continue

        try:

            await bot.send_message(

                admin_id,

                admin_text,

                reply_markup=admin_trial_keyboard(
                    user_id
                )
            )

        except Exception as e:

            logging.error(
                f"Ошибка отправки заявки "
                f"на пробу админу {admin_id}: {e}"
            )

    await callback.message.edit_text(

        "🟡 <b>Заявка на бесплатную пробу отправлена</b>\n\n"

        "Администратор выдаст тебе VPN "
        "на 3 дня после проверки.\n\n"

        "Ожидай сообщение с VPN-ссылкой."
    )


# =========================
# ВЫДАТЬ ПРОБУ
# =========================

@dp.callback_query(
    F.data.startswith("confirm_trial_")
)
async def confirm_trial(
    callback: CallbackQuery
):

    if callback.from_user.id not in ADMIN_IDS:

        await callback.answer(
            "Нет доступа"
        )

        return

    try:

        user_id = int(
            callback.data.split("_")[2]
        )

    except (ValueError, IndexError):

        await callback.answer(
            "Ошибка"
        )

        return

    if user_id in trial_users:

        await callback.answer(
            "Проба уже была выдана."
        )

        return

    trial_users.add(user_id)

    now = datetime.now(timezone.utc)

    subscriptions[user_id] = {

        "days": 3,

        "price": 0,

        "expires": (
            now + timedelta(days=3)
        ),
    }

    admin_states[
        callback.from_user.id
    ] = {

        "type": "vpn_for_trial",

        "user_id": user_id,

        "days": 3,
    }

    await callback.answer(
        "Проба подтверждена"
    )

    await callback.message.edit_text(

        callback.message.text

        + "\n\n"
        "✅ <b>ПРОБА ПОДТВЕРЖДЕНА</b>"
    )

    await bot.send_message(

        callback.from_user.id,

        "🔗 <b>Отправь VPN subscription URL</b>\n\n"
        "Создай пользователю 3 дня в 3X-UI "
        "и вставь сюда его subscription URL."
    )

    try:

        await bot.send_message(

            user_id,

            "🎁 <b>Бесплатная проба одобрена!</b>\n\n"
            "Администратор сейчас выдаёт тебе VPN "
            "на 3 дня."
        )

    except Exception:
        pass


# =========================
# ОТКЛОНИТЬ ПРОБУ
# =========================

@dp.callback_query(
    F.data.startswith("reject_trial_")
)
async def reject_trial(
    callback: CallbackQuery
):

    if callback.from_user.id not in ADMIN_IDS:

        await callback.answer(
            "Нет доступа"
        )

        return

    try:

        user_id = int(
            callback.data.split("_")[2]
        )

    except (ValueError, IndexError):

        await callback.answer(
            "Ошибка"
        )

        return

    await callback.answer(
        "Заявка отклонена"
    )

    await callback.message.edit_text(

        callback.message.text

        + "\n\n"
        "❌ <b>ПРОБА ОТКЛОНЕНА</b>"
    )

    try:

        await bot.send_message(

            user_id,

            "❌ К сожалению, бесплатная проба "
            "сейчас недоступна."
        )

    except Exception:
        pass


# =========================
# ПОЛУЧЕНИЕ VPN ССЫЛКИ
# =========================

@dp.message(F.text)
async def text_handler(
    message: Message
):

    user_id = message.from_user.id

    if (
        user_id in ADMIN_IDS
        and user_id in admin_states
    ):

        state = admin_states[user_id]

        buyer_id = state["user_id"]

        vpn_link = message.text.strip()

        valid = (

            vpn_link.startswith("http://")

            or vpn_link.startswith("https://")

            or vpn_link.startswith("vless://")

            or vpn_link.startswith("vmess://")

            or vpn_link.startswith("trojan://")

            or vpn_link.startswith("ss://")
        )

        if not valid:

            await message.answer(

                "❌ Это не похоже "
                "на VPN subscription URL.\n\n"

                "Просто вставь ссылку из 3X-UI."
            )

            return

        try:

            await bot.send_message(

                buyer_id,

                "🎉 <b>VPN готов!</b>\n\n"

                "Твоя ссылка:\n\n"

                f"<code>{vpn_link}</code>\n\n"

                "Добавь её в HAPP или V2Ray."
            )

            await message.answer(

                "✅ VPN успешно "
                "отправлен пользователю."
            )

        except Exception as e:

            await message.answer(

                f"❌ Не удалось "
                f"отправить VPN:\n{e}"
            )

        del admin_states[user_id]

        return

    await message.answer(

        "Выбери действие в меню 👇",

        reply_markup=main_keyboard()
    )


# =========================
# ОТМЕНА
# =========================

@dp.callback_query(
    F.data == "cancel_payment"
)
async def cancel_payment(
    callback: CallbackQuery
):

    pending_payments.pop(
        callback.from_user.id,
        None
    )

    await callback.answer(
        "Отменено"
    )

    await callback.message.edit_text(

        "❌ <b>Покупка отменена.</b>\n\n"
        "Можешь выбрать другой тариф.",

        reply_markup=main_keyboard()
    )


# =========================
# МОЯ ПОДПИСКА
# =========================

@dp.callback_query(
    F.data == "my_subscription"
)
async def my_subscription(
    callback: CallbackQuery
):

    user_id = callback.from_user.id

    sub = subscriptions.get(
        user_id
    )

    if not sub:

        await callback.answer()

        await callback.message.answer(

            "💷 <b>У тебя пока нет "
            "активной подписки.</b>\n\n"
            "Выбери тариф ниже.",

            reply_markup=main_keyboard()
        )

        return

    expires = sub["expires"]

    if expires <= datetime.now(timezone.utc):

        await callback.answer()

        await callback.message.answer(

            "💷 <b>Твоя подписка закончилась.</b>\n\n"
            "Выбери новый тариф.",

            reply_markup=main_keyboard()
        )

        return

    await callback.answer()

    type_text = (
        "🎁 Бесплатная проба"
        if sub["price"] == 0
        else f"{sub['days']} дней"
    )

    await callback.message.answer(

        "💷 <b>Моя подписка</b>\n\n"

        f"📦 Тариф: <b>{type_text}</b>\n"

        f"📅 Действует до: "
        f"<b>{expires.strftime('%d.%m.%Y %H:%M')}</b> UTC"
    )


# =========================
# УСЛОВИЯ
# =========================

@dp.callback_query(
    F.data == "terms"
)
async def terms_callback(
    callback: CallbackQuery
):

    await callback.answer()

    await callback.message.answer(

        "⚔️ <b>Условия ОтвалиVPN</b>\n\n"

        "• VPN предоставляется "
        "на оплаченный срок.\n"

        "• Бесплатная проба предоставляется "
        "один раз.\n"

        "• После окончания срока "
        "доступ прекращается.\n"

        "• Ссылка предназначена "
        "только для покупателя.\n"

        "• Не передавай VPN-ссылку "
        "другим людям.\n"

        "• При проблемах обращайся "
        "в поддержку."
    )


# =========================
# ПОДДЕРЖКА
# =========================

@dp.callback_query(
    F.data == "support"
)
async def support_callback(
    callback: CallbackQuery
):

    await callback.answer()

    await callback.message.answer(

        "🪡 <b>Поддержка</b>\n\n"

        "Если возникла проблема "
        "с оплатой или VPN — "
        "напиши администратору."
    )


# =========================
# /MYID
# =========================

@dp.message(Command("myid"))
async def myid(
    message: Message
):

    await message.answer(

        "🆔 Твой Telegram ID:\n"

        f"<code>{message.from_user.id}</code>"
    )


# =========================
# /TERMS
# =========================

@dp.message(Command("terms"))
async def terms_command(
    message: Message
):

    await message.answer(

        "⚔️ <b>Условия ОтвалиVPN</b>\n\n"

        "VPN предоставляется "
        "на оплаченный срок.\n"

        "Бесплатная проба — 3 дня.\n"

        "Не передавай VPN-ссылку "
        "другим людям."
    )


# =========================
# /PAY
# =========================

@dp.message(Command("pay"))
async def pay_command(
    message: Message
):

    await message.answer(

        "Выбери тариф:",

        reply_markup=main_keyboard()
    )


# =========================
# /GIVEVPN
# =========================

@dp.message(Command("givevpn"))
async def givevpn(
    message: Message
):

    if message.from_user.id not in ADMIN_IDS:

        await message.answer(
            "Нет доступа."
        )

        return

    args = message.text.split(
        maxsplit=2
    )

    if len(args) < 3:

        await message.answer(

            "Использование:\n"

            "<code>"
            "/givevpn TELEGRAM_ID VPN_LINK"
            "</code>"
        )

        return

    try:

        buyer_id = int(args[1])

    except ValueError:

        await message.answer(
            "❌ Неверный Telegram ID."
        )

        return

    vpn_link = args[2].strip()

    try:

        await bot.send_message(

            buyer_id,

            "🎉 <b>VPN готов!</b>\n\n"

            f"<code>{vpn_link}</code>\n\n"

            "Добавь ссылку в HAPP или V2Ray."
        )

        await message.answer(
            "✅ VPN отправлен."
        )

    except Exception as e:

        await message.answer(
            f"❌ Ошибка:\n{e}"
        )


# =========================
# WEB SERVER
# =========================

async def health(
    request
):

    return web.Response(
        text="ОтвалиVPN работает!"
    )


async def start_web_server():

    app = web.Application()

    app.router.add_get(
        "/",
        health
    )

    async def mini_app(
        request
    ):

        try:

            with open(
                "webapp.html",
                "r",
                encoding="utf-8"
            ) as f:

                html = f.read()

            return web.Response(

                text=html,

                content_type="text/html"
            )

        except FileNotFoundError:

            return web.Response(

                text="webapp.html not found",

                status=404
            )

    app.router.add_get(
        "/app",
        mini_app
    )

    runner = web.AppRunner(app)

    await runner.setup()

    port = int(
        os.environ.get(
            "PORT",
            "8080"
        )
    )

    site = web.TCPSite(

        runner,

        "0.0.0.0",

        port
    )

    await site.start()

    logging.info(
        f"Web server started on port {port}"
    )


# =========================
# TELEGRAM
# =========================

async def setup_bot():

    await bot.set_my_commands([

        BotCommand(
            command="start",
            description="Запустить ОтвалиVPN"
        ),

        BotCommand(
            command="pay",
            description="Купить VPN"
        ),

        BotCommand(
            command="myid",
            description="Мой Telegram ID"
        ),

        BotCommand(
            command="terms",
            description="Условия"
        ),
    ])

    await bot.set_chat_menu_button(

        menu_button=MenuButtonWebApp(

            text="🪡 ОтвалиVPN",

            web_app=WebAppInfo(
                url=WEBAPP_URL
            )
        )
    )


# =========================
# ЗАПУСК
# =========================

async def main():

    logging.basicConfig(
        level=logging.INFO
    )

    if not BOT_TOKEN:

        raise RuntimeError(
            "BOT_TOKEN не найден "
            "в Railway Variables"
        )

    await setup_bot()

    await start_web_server()

    logging.info(
        "ОтвалиVPN запущен!"
    )

    await dp.start_polling(
        bot
    )


if __name__ == "__main__":

    asyncio.run(main())
