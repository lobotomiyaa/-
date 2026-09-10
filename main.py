import os
import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone

from aiogram import Bot, Dispatcher, F, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    BotCommand,
)


# =========================================================
# НАСТРОЙКИ
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# Второй администратор
FRIEND_ADMIN_ID = 1404271536

ADMIN_IDS = {
    ADMIN_ID,
    FRIEND_ADMIN_ID,
}

# Реквизиты оплаты
PAYMENT_DETAILS = os.getenv(
    "PAYMENT_DETAILS",
    "Реквизиты оплаты не настроены."
)


# =========================================================
# ТАРИФЫ
# =========================================================

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
        "emoji": "❄️",
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


# =========================================================
# ВРЕМЕННОЕ ХРАНИЛИЩЕ
# =========================================================

# user_id -> подписка
subscriptions = {}

# payment_id -> оплата
payments = {}

# admin_id -> payment_id
admin_waiting_vpn = {}

# admin_id -> данные выдачи подарка
admin_gift_state = {}


# =========================================================
# ЛОГИ
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


# =========================================================
# BOT
# =========================================================

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(
        parse_mode=ParseMode.HTML,
    ),
)

dp = Dispatcher()


# =========================================================
# ПРОВЕРКА АДМИНА
# =========================================================

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# =========================================================
# ГЛАВНОЕ МЕНЮ
# =========================================================

def main_keyboard(user_id: int | None = None):

    buttons = [
        [
            InlineKeyboardButton(
                text="🪡 Купить VPN",
                callback_data="buy_menu",
            )
        ],

        [
            InlineKeyboardButton(
                text="💷 Моя подписка",
                callback_data="my_subscription",
            )
        ],

        [
            InlineKeyboardButton(
                text="⚔️ Условия",
                callback_data="terms",
            ),

            InlineKeyboardButton(
                text="🪡 Поддержка",
                callback_data="support",
            ),
        ],
    ]

    # Кнопка подарка только для админов
    if user_id is not None and is_admin(user_id):

        buttons.append(
            [
                InlineKeyboardButton(
                    text="🎁 Выдать подарок",
                    callback_data="gift_menu",
                )
            ]
        )

    return InlineKeyboardMarkup(
        inline_keyboard=buttons
    )


# =========================================================
# МЕНЮ ТАРИФОВ
# =========================================================

def tariffs_keyboard():

    return InlineKeyboardMarkup(
        inline_keyboard=[

            [
                InlineKeyboardButton(
                    text="🪦 7 дней — 60 руб",
                    callback_data="tariff_7",
                )
            ],

            [
                InlineKeyboardButton(
                    text="❄️ 14 дней — 100 руб",
                    callback_data="tariff_14",
                )
            ],

            [
                InlineKeyboardButton(
                    text="📜 30 дней — 200 руб",
                    callback_data="tariff_30",
                )
            ],

            [
                InlineKeyboardButton(
                    text="🕊️ 90 дней — 399 руб",
                    callback_data="tariff_90",
                )
            ],

            [
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data="main_menu",
                )
            ],
        ]
    )


# =========================================================
# МЕНЮ ПОДАРКА
# =========================================================

def gift_tariffs_keyboard():

    return InlineKeyboardMarkup(
        inline_keyboard=[

            [
                InlineKeyboardButton(
                    text="🎁 7 дней",
                    callback_data="gift_tariff_7",
                )
            ],

            [
                InlineKeyboardButton(
                    text="🎁 14 дней",
                    callback_data="gift_tariff_14",
                )
            ],

            [
                InlineKeyboardButton(
                    text="🎁 30 дней",
                    callback_data="gift_tariff_30",
                )
            ],

            [
                InlineKeyboardButton(
                    text="🎁 90 дней",
                    callback_data="gift_tariff_90",
                )
            ],

            [
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data="main_menu",
                )
            ],
        ]
    )


# =========================================================
# ПОДТВЕРЖДЕНИЕ ПОКУПКИ
# =========================================================

def confirm_keyboard(days: int):

    return InlineKeyboardMarkup(
        inline_keyboard=[

            [
                InlineKeyboardButton(
                    text="✅ Да, купить",
                    callback_data=f"confirm_{days}",
                )
            ],

            [
                InlineKeyboardButton(
                    text="❌ Нет, назад",
                    callback_data="buy_menu",
                )
            ],
        ]
    )


# =========================================================
# КНОПКА ОПЛАТЫ
# =========================================================

def payment_keyboard(payment_id: str):

    return InlineKeyboardMarkup(
        inline_keyboard=[

            [
                InlineKeyboardButton(
                    text="✅ Я оплатил",
                    callback_data=f"user_paid_{payment_id}",
                )
            ],

            [
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data=f"cancel_{payment_id}",
                )
            ],
        ]
    )


# =========================================================
# КНОПКИ АДМИНА
# =========================================================

def admin_payment_keyboard(payment_id: str):

    return InlineKeyboardMarkup(
        inline_keyboard=[

            [
                InlineKeyboardButton(
                    text="✅ ПОДТВЕРДИТЬ ОПЛАТУ",
                    callback_data=f"admin_yes_{payment_id}",
                )
            ],

            [
                InlineKeyboardButton(
                    text="❌ ОТКЛОНИТЬ",
                    callback_data=f"admin_no_{payment_id}",
                )
            ],
        ]
    )


# =========================================================
# START
# =========================================================

@dp.message(CommandStart())
async def start(message: Message):

    await message.answer(
        "🪡 <b>ОТВАЛИVPN</b>\n\n"
        "Быстрый VPN без лишнего.\n\n"
        "Выбирай тариф ниже 👇",
        reply_markup=main_keyboard(
            message.from_user.id
        ),
    )


# =========================================================
# /PAY
# =========================================================

@dp.message(Command("pay"))
async def pay_command(message: Message):

    await message.answer(
        "💷 <b>Выбери тариф:</b>",
        reply_markup=tariffs_keyboard(),
    )


# =========================================================
# КНОПКА "КУПИТЬ VPN"
# =========================================================

@dp.callback_query(F.data == "buy_menu")
async def buy_menu(callback: CallbackQuery):

    await callback.message.edit_text(
        "💷 <b>ВЫБЕРИ ТАРИФ</b>\n\n"
        "Доступные варианты:",
        reply_markup=tariffs_keyboard(),
    )

    await callback.answer()


# =========================================================
# ВЫБОР ТАРИФА
# =========================================================

@dp.callback_query(F.data.startswith("tariff_"))
async def tariff_selected(callback: CallbackQuery):

    try:
        days = int(
            callback.data.replace(
                "tariff_",
                "",
            )
        )
    except ValueError:

        await callback.answer(
            "Ошибка тарифа.",
            show_alert=True,
        )

        return

    tariff = TARIFFS.get(days)

    if not tariff:

        await callback.answer(
            "Тариф не найден.",
            show_alert=True,
        )

        return

    await callback.message.edit_text(

        "⚠️ <b>ПОДТВЕРЖДЕНИЕ ПОКУПКИ</b>\n\n"

        "Действительно хочешь купить:\n\n"

        f"{tariff['emoji']} "
        f"<b>{tariff['name']}</b>\n"

        f"💰 Цена: "
        f"<b>{tariff['price']} руб</b>\n\n"

        "После подтверждения появятся "
        "реквизиты для оплаты.",

        reply_markup=confirm_keyboard(days),
    )

    await callback.answer()


# =========================================================
# ПОДТВЕРЖДЕНИЕ ПОКУПКИ
# =========================================================

@dp.callback_query(F.data.startswith("confirm_"))
async def confirm_purchase(callback: CallbackQuery):

    try:
        days = int(
            callback.data.replace(
                "confirm_",
                "",
            )
        )
    except ValueError:

        await callback.answer(
            "Ошибка.",
            show_alert=True,
        )

        return

    tariff = TARIFFS.get(days)

    if not tariff:

        await callback.answer(
            "Тариф не найден.",
            show_alert=True,
        )

        return

    existing = None

    for payment in payments.values():

        if (
            payment["user_id"]
            == callback.from_user.id
            and payment["status"]
            in (
                "waiting_payment",
                "waiting_admin",
                "confirmed",
            )
        ):

            existing = payment
            break

    if existing:

        await callback.message.edit_text(

            "⚠️ <b>У ТЕБЯ УЖЕ ЕСТЬ ЗАЯВКА</b>\n\n"

            f"Заявка: "
            f"<code>#{existing['id']}</code>\n"

            f"Тариф: "
            f"<b>{existing['days']} дней</b>\n"

            f"Сумма: "
            f"<b>{existing['price']} руб</b>\n\n"

            "Дождись обработки предыдущей заявки.",

            reply_markup=main_keyboard(
                callback.from_user.id
            ),
        )

        await callback.answer()

        return

    payment_id = uuid.uuid4().hex[:10].upper()

    payments[payment_id] = {

        "id": payment_id,

        "user_id":
            callback.from_user.id,

        "username":
            callback.from_user.username
            or "без username",

        "days":
            days,

        "price":
            tariff["price"],

        "status":
            "waiting_payment",

        "created_at":
            datetime.now(timezone.utc),

        "vpn_url":
            None,
    }

    await callback.message.edit_text(

        "💷 <b>ОПЛАТА</b>\n\n"

        f"{tariff['emoji']} Тариф: "
        f"<b>{tariff['name']}</b>\n"

        f"💰 Сумма: "
        f"<b>{tariff['price']} руб</b>\n\n"

        "Переведи точную сумму по реквизитам:\n\n"

        f"<code>{html.quote(PAYMENT_DETAILS)}</code>\n\n"

        "После перевода нажми:\n"
        "«✅ Я оплатил»\n\n"

        "Оплата будет проверена "
        "администратором вручную.",

        reply_markup=payment_keyboard(
            payment_id
        ),
    )

    await callback.answer()


# =========================================================
# ПОЛЬЗОВАТЕЛЬ НАЖАЛ "Я ОПЛАТИЛ"
# =========================================================

@dp.callback_query(F.data.startswith("user_paid_"))
async def user_paid(callback: CallbackQuery):

    payment_id = callback.data.replace(
        "user_paid_",
        "",
    )

    payment = payments.get(payment_id)

    if not payment:

        await callback.answer(
            "Заявка не найдена.",
            show_alert=True,
        )

        return

    if payment["user_id"] != callback.from_user.id:

        await callback.answer(
            "Это не твоя заявка.",
            show_alert=True,
        )

        return

    if payment["status"] != "waiting_payment":

        await callback.answer(
            "Заявка уже отправлена на проверку.",
            show_alert=True,
        )

        return

    payment["status"] = "waiting_admin"

    payment["paid_at"] = datetime.now(
        timezone.utc
    )

    await callback.message.edit_text(

        "⏳ <b>ОПЛАТА ОТПРАВЛЕНА НА ПРОВЕРКУ</b>\n\n"

        f"Заявка: "
        f"<code>#{payment_id}</code>\n"

        f"Тариф: "
        f"<b>{payment['days']} дней</b>\n"

        f"Сумма: "
        f"<b>{payment['price']} руб</b>\n\n"

        "Ожидай подтверждения администратора.",

        reply_markup=main_keyboard(
            callback.from_user.id
        ),
    )

    username = html.quote(
        payment["username"]
    )

    admin_text = (

        "💷 <b>НОВАЯ ОПЛАТА</b>\n\n"

        f"🆔 Заявка: "
        f"<code>#{payment_id}</code>\n"

        f"👤 Telegram ID: "
        f"<code>{payment['user_id']}</code>\n"

        f"🔗 Username: "
        f"@{username}\n"

        f"📦 Тариф: "
        f"<b>{payment['days']} дней</b>\n"

        f"💰 Сумма: "
        f"<b>{payment['price']} руб</b>\n\n"

        "Проверь перевод в банковском приложении."
    )

    for admin_id in ADMIN_IDS:

        if admin_id <= 0:
            continue

        try:

            await bot.send_message(

                chat_id=admin_id,

                text=admin_text,

                reply_markup=
                    admin_payment_keyboard(
                        payment_id
                    ),
            )

        except Exception as error:

            logger.error(
                "Ошибка отправки админу %s: %s",
                admin_id,
                error,
            )

    await callback.answer(
        "Заявка отправлена администратору."
    )


# =========================================================
# ОТМЕНА ОПЛАТЫ
# =========================================================

@dp.callback_query(F.data.startswith("cancel_"))
async def cancel_payment(callback: CallbackQuery):

    payment_id = callback.data.replace(
        "cancel_",
        "",
    )

    payment = payments.get(payment_id)

    if not payment:

        await callback.answer(
            "Заявка не найдена."
        )

        return

    if payment["user_id"] != callback.from_user.id:

        await callback.answer(
            "Это не твоя заявка.",
            show_alert=True,
        )

        return

    if payment["status"] != "waiting_payment":

        await callback.answer(
            "Заявка уже обрабатывается.",
            show_alert=True,
        )

        return

    payment["status"] = "cancelled"

    await callback.message.edit_text(

        "❌ <b>ПОКУПКА ОТМЕНЕНА</b>\n\n"
        "Если захочешь купить VPN — "
        "нажми «🪡 Купить VPN».",

        reply_markup=main_keyboard(
            callback.from_user.id
        ),
    )

    await callback.answer()


# =========================================================
# АДМИН ПОДТВЕРЖДАЕТ ОПЛАТУ
# =========================================================

@dp.callback_query(F.data.startswith("admin_yes_"))
async def admin_confirm(callback: CallbackQuery):

    if not is_admin(
        callback.from_user.id
    ):

        await callback.answer(
            "Нет доступа.",
            show_alert=True,
        )

        return

    payment_id = callback.data.replace(
        "admin_yes_",
        "",
    )

    payment = payments.get(payment_id)

    if not payment:

        await callback.answer(
            "Заявка не найдена.",
            show_alert=True,
        )

        return

    if payment["status"] != "waiting_admin":

        await callback.answer(
            "Эта заявка уже обработана.",
            show_alert=True,
        )

        return

    payment["status"] = "confirmed"

    payment["confirmed_by"] = (
        callback.from_user.id
    )

    payment["confirmed_at"] = (
        datetime.now(timezone.utc)
    )

    admin_waiting_vpn[
        callback.from_user.id
    ] = payment_id

    await callback.message.edit_text(

        "✅ <b>ОПЛАТА ПОДТВЕРЖДЕНА</b>\n\n"

        f"Заявка: "
        f"<code>#{payment_id}</code>\n"

        f"Пользователь: "
        f"<code>{payment['user_id']}</code>\n"

        f"Тариф: "
        f"<b>{payment['days']} дней</b>\n"

        f"Сумма: "
        f"<b>{payment['price']} руб</b>\n\n"

        "Теперь отправь сюда "
        "<b>subscription URL из 3X-UI</b>."
    )

    await bot.send_message(

        chat_id=payment["user_id"],

        text=(

            "✅ <b>ОПЛАТА ПОДТВЕРЖДЕНА!</b>\n\n"

            f"Тариф: "
            f"<b>{payment['days']} дней</b>\n\n"

            "Администратор сейчас выдаёт VPN.\n"
            "Ожидай ссылку."
        ),
    )

    await callback.answer(
        "Оплата подтверждена."
    )


# =========================================================
# АДМИН ОТКЛОНЯЕТ ОПЛАТУ
# =========================================================

@dp.callback_query(F.data.startswith("admin_no_"))
async def admin_reject(callback: CallbackQuery):

    if not is_admin(
        callback.from_user.id
    ):

        await callback.answer(
            "Нет доступа.",
            show_alert=True,
        )

        return

    payment_id = callback.data.replace(
        "admin_no_",
        "",
    )

    payment = payments.get(payment_id)

    if not payment:

        await callback.answer(
            "Заявка не найдена.",
            show_alert=True,
        )

        return

    if payment["status"] != "waiting_admin":

        await callback.answer(
            "Эта заявка уже обработана.",
            show_alert=True,
        )

        return

    payment["status"] = "rejected"

    payment["rejected_by"] = (
        callback.from_user.id
    )

    payment["rejected_at"] = (
        datetime.now(timezone.utc)
    )

    await callback.message.edit_text(

        "❌ <b>ОПЛАТА ОТКЛОНЕНА</b>\n\n"

        f"Заявка: "
        f"<code>#{payment_id}</code>\n"

        f"Пользователь: "
        f"<code>{payment['user_id']}</code>"
    )

    await bot.send_message(

        chat_id=payment["user_id"],

        text=(

            "❌ <b>ОПЛАТА НЕ ПОДТВЕРЖДЕНА</b>\n\n"

            "Проверь сумму и реквизиты.\n\n"

            "Если перевод действительно был сделан, "
            "обратись в поддержку."
        ),
    )

    await callback.answer(
        "Оплата отклонена."
    )


# =========================================================
# 🎁 МЕНЮ ПОДАРКА
# =========================================================

@dp.callback_query(F.data == "gift_menu")
async def gift_menu(callback: CallbackQuery):

    if not is_admin(
        callback.from_user.id
    ):

        await callback.answer(
            "Нет доступа.",
            show_alert=True,
        )

        return

    await callback.message.edit_text(

        "🎁 <b>ВЫДАТЬ ПОДАРОК</b>\n\n"

        "Выбери срок VPN:",

        reply_markup=gift_tariffs_keyboard(),
    )

    await callback.answer()


# =========================================================
# 🎁 ВЫБОР СРОКА ПОДАРКА
# =========================================================

@dp.callback_query(F.data.startswith("gift_tariff_"))
async def gift_tariff_selected(
    callback: CallbackQuery
):

    if not is_admin(
        callback.from_user.id
    ):

        await callback.answer(
            "Нет доступа.",
            show_alert=True,
        )

        return

    try:

        days = int(
            callback.data.replace(
                "gift_tariff_",
                "",
            )
        )

    except ValueError:

        await callback.answer(
            "Ошибка срока.",
            show_alert=True,
        )

        return

    tariff = TARIFFS.get(days)

    if not tariff:

        await callback.answer(
            "Срок не найден.",
            show_alert=True,
        )

        return

    # Сохраняем состояние админа
    admin_gift_state[
        callback.from_user.id
    ] = {

        "days": days,

        "stage": "waiting_user_id",
    }

    await callback.message.edit_text(

        "🎁 <b>ПОДАРОК</b>\n\n"

        f"Срок: <b>{days} дней</b>\n\n"

        "Теперь отправь сюда "
        "<b>Telegram ID получателя</b>.\n\n"

        "Например:\n"
        "<code>123456789</code>"
    )

    await callback.answer()


# =========================================================
# ОБРАБОТКА СООБЩЕНИЙ АДМИНА
# =========================================================

@dp.message()
async def admin_messages(message: Message):

    user_id = message.from_user.id

    # =====================================================
    # НЕ АДМИН
    # =====================================================

    if not is_admin(user_id):
        return

    # =====================================================
    # СНАЧАЛА ПРОВЕРЯЕМ ПОДАРОК
    # =====================================================

    gift = admin_gift_state.get(user_id)

    if gift:

        # -------------------------------------------------
        # ЖДЁМ TELEGRAM ID
        # -------------------------------------------------

        if gift["stage"] == "waiting_user_id":

            text = (
                message.text or ""
            ).strip()

            try:

                target_user_id = int(text)

                if target_user_id <= 0:
                    raise ValueError

            except ValueError:

                await message.answer(

                    "❌ <b>Неверный Telegram ID.</b>\n\n"

                    "Отправь только число.\n\n"

                    "Например:\n"
                    "<code>123456789</code>"
                )

                return

            gift["target_user_id"] = (
                target_user_id
            )

            gift["stage"] = "waiting_vpn_url"

            await message.answer(

                "✅ Получатель установлен.\n\n"

                f"🆔 ID: "
                f"<code>{target_user_id}</code>\n"

                f"🎁 Срок: "
                f"<b>{gift['days']} дней</b>\n\n"

                "Теперь отправь "
                "<b>subscription URL из 3X-UI</b>."
            )

            return

        # -------------------------------------------------
        # ЖДЁМ VPN URL
        # -------------------------------------------------

        if gift["stage"] == "waiting_vpn_url":

            vpn_url = (
                message.text or ""
            ).strip()

            if not (
                vpn_url.startswith("http://")
                or vpn_url.startswith("https://")
            ):

                await message.answer(

                    "❌ <b>Неверная ссылка.</b>\n\n"

                    "Отправь полную "
                    "subscription-ссылку из 3X-UI."
                )

                return

            target_user_id = (
                gift["target_user_id"]
            )

            days = gift["days"]

            now = datetime.now(
                timezone.utc
            )

            expires = now + timedelta(
                days=days
            )

            gift_id = (
                "GIFT-"
                + uuid.uuid4().hex[:8].upper()
            )

            # Сохраняем подписку
            subscriptions[
                target_user_id
            ] = {

                "days":
                    days,

                "price":
                    0,

                "url":
                    vpn_url,

                "started_at":
                    now,

                "expires_at":
                    expires,

                "payment_id":
                    gift_id,

                "gift":
                    True,
            }

            # Удаляем состояние
            admin_gift_state.pop(
                user_id,
                None,
            )

            # -------------------------------------------------
            # ОТПРАВЛЯЕМ ПОДАРОК ПОЛУЧАТЕЛЮ
            # -------------------------------------------------

            try:

                await bot.send_message(

                    chat_id=target_user_id,

                    text=(

                        "🎁 <b>ТЕБЕ ПОДАРИЛИ VPN!</b>\n\n"

                        f"📦 Срок: "
                        f"<b>{days} дней</b>\n\n"

                        "⚔️ <b>Твоя subscription-ссылка:</b>\n\n"

                        f"<code>{html.quote(vpn_url)}</code>\n\n"

                        "Добавь эту ссылку в "
                        "Happ или V2Ray.\n\n"

                        "Приятного пользования ❤️"
                    ),
                )

            except Exception as error:

                logger.error(
                    "Не удалось отправить подарок пользователю %s: %s",
                    target_user_id,
                    error,
                )

                # Удаляем подписку, если доставить её невозможно
                subscriptions.pop(
                    target_user_id,
                    None,
                )

                await message.answer(

                    "❌ <b>Не удалось отправить подарок.</b>\n\n"

                    f"Telegram ID: "
                    f"<code>{target_user_id}</code>\n\n"

                    "Возможно, пользователь ещё "
                    "не запускал бота через /start.\n\n"

                    "Пусть он зайдёт в бота и нажмёт "
                    "«/start», после чего попробуй снова."
                )

                return

            await message.answer(

                "🎁 <b>ПОДАРОК ВЫДАН!</b>\n\n"

                f"👤 Получатель: "
                f"<code>{target_user_id}</code>\n"

                f"📦 Срок: "
                f"<b>{days} дней</b>\n\n"

                "VPN-ссылка отправлена получателю."
            )

            return

    # =====================================================
    # ОПЛАЧЕННАЯ ЗАЯВКА — ЖДЁМ VPN URL
    # =====================================================

    payment_id = admin_waiting_vpn.get(
        user_id
    )

    if not payment_id:
        return

    payment = payments.get(
        payment_id
    )

    if not payment:

        admin_waiting_vpn.pop(
            user_id,
            None,
        )

        await message.answer(
            "❌ Заявка не найдена."
        )

        return

    if payment["status"] != "confirmed":

        admin_waiting_vpn.pop(
            user_id,
            None,
        )

        await message.answer(

            "❌ Эта заявка больше "
            "не ожидает VPN."
        )

        return

    vpn_url = (
        message.text or ""
    ).strip()

    if not (
        vpn_url.startswith("http://")
        or vpn_url.startswith("https://")
    ):

        await message.answer(

            "❌ <b>Неверная ссылка.</b>\n\n"

            "Отправь полную "
            "subscription-ссылку из 3X-UI."
        )

        return

    now = datetime.now(
        timezone.utc
    )

    expires = now + timedelta(
        days=payment["days"]
    )

    subscriptions[
        payment["user_id"]
    ] = {

        "days":
            payment["days"],

        "price":
            payment["price"],

        "url":
            vpn_url,

        "started_at":
            now,

        "expires_at":
            expires,

        "payment_id":
            payment_id,
    }

    payment["vpn_url"] = vpn_url
    payment["status"] = "completed"
    payment["completed_at"] = now

    admin_waiting_vpn.pop(
        user_id,
        None,
    )

    await bot.send_message(

        chat_id=payment["user_id"],

        text=(

            "⚔️ <b>VPN ГОТОВ!</b>\n\n"

            f"📦 Тариф: "
            f"<b>{payment['days']} дней</b>\n"

            f"💰 Оплата: "
            f"<b>{payment['price']} руб</b>\n\n"

            "🔗 <b>Твоя subscription-ссылка:</b>\n\n"

            f"<code>{html.quote(vpn_url)}</code>\n\n"

            "Добавь эту ссылку в Happ или V2Ray."
        ),
    )

    await message.answer(

        "✅ <b>VPN ВЫДАН</b>\n\n"

        f"Заявка: "
        f"<code>#{payment_id}</code>\n"

        f"Пользователь: "
        f"<code>{payment['user_id']}</code>"
    )


# =========================================================
# МОЯ ПОДПИСКА
# =========================================================

@dp.callback_query(F.data == "my_subscription")
async def my_subscription(
    callback: CallbackQuery
):

    subscription = subscriptions.get(
        callback.from_user.id
    )

    if not subscription:

        await callback.message.edit_text(

            "💷 <b>МОЯ ПОДПИСКА</b>\n\n"

            "Активной подписки нет.",

            reply_markup=main_keyboard(
                callback.from_user.id
            ),
        )

        await callback.answer()

        return

    expires = subscription[
        "expires_at"
    ]

    now = datetime.now(
        timezone.utc
    )

    if expires <= now:

        await callback.message.edit_text(

            "💷 <b>МОЯ ПОДПИСКА</b>\n\n"

            "Подписка закончилась.",

            reply_markup=main_keyboard(
                callback.from_user.id
            ),
        )

        await callback.answer()

        return

    expires_text = expires.strftime(
        "%d.%m.%Y %H:%M"
    )

    gift_text = ""

    if subscription.get("gift"):
        gift_text = "🎁 <b>Это подарок</b>\n\n"

    await callback.message.edit_text(

        "💷 <b>МОЯ ПОДПИСКА</b>\n\n"

        f"{gift_text}"

        f"📦 Тариф: "
        f"<b>{subscription['days']} дней</b>\n"

        f"📅 Действует до: "
        f"<b>{expires_text}</b>\n\n"

        "🔗 Subscription URL:\n\n"

        f"<code>{html.quote(subscription['url'])}</code>",

        reply_markup=main_keyboard(
            callback.from_user.id
        ),
    )

    await callback.answer()


# =========================================================
# УСЛОВИЯ
# =========================================================

@dp.callback_query(F.data == "terms")
async def terms(callback: CallbackQuery):

    await callback.message.edit_text(

        "⚔️ <b>УСЛОВИЯ</b>\n\n"

        "VPN предоставляется на выбранный срок.\n\n"

        "Оплата проверяется вручную.\n"

        "После подтверждения оплаты "
        "администратор выдаёт VPN.\n\n"

        "Подарочный VPN также выдаётся "
        "администратором вручную.\n\n"

        "После окончания срока "
        "подписка перестаёт действовать.",

        reply_markup=main_keyboard(
            callback.from_user.id
        ),
    )

    await callback.answer()


# =========================================================
# ПОДДЕРЖКА
# =========================================================

@dp.callback_query(F.data == "support")
async def support(callback: CallbackQuery):

    await callback.message.edit_text(

        "🪡 <b>ПОДДЕРЖКА</b>\n\n"

        "Если возникла проблема с оплатой "
        "или VPN — напиши администратору.",

        reply_markup=main_keyboard(
            callback.from_user.id
        ),
    )

    await callback.answer()


# =========================================================
# ГЛАВНОЕ МЕНЮ
# =========================================================

@dp.callback_query(F.data == "main_menu")
async def main_menu(callback: CallbackQuery):

    await callback.message.edit_text(

        "🪡 <b>ОТВАЛИVPN</b>\n\n"

        "Выбирай нужное действие 👇",

        reply_markup=main_keyboard(
            callback.from_user.id
        ),
    )

    await callback.answer()


# =========================================================
# /MYID
# =========================================================

@dp.message(Command("myid"))
async def myid(message: Message):

    await message.answer(

        "🆔 <b>Твой Telegram ID:</b>\n\n"

        f"<code>{message.from_user.id}</code>"
    )


# =========================================================
# /TERMS
# =========================================================

@dp.message(Command("terms"))
async def terms_command(
    message: Message
):

    await message.answer(

        "⚔️ <b>УСЛОВИЯ</b>\n\n"

        "VPN предоставляется на выбранный срок.\n"

        "Оплата проверяется вручную.\n"

        "После подтверждения оплаты "
        "администратор выдаёт VPN."
    )


# =========================================================
# /PAYSUPPORT
# =========================================================

@dp.message(Command("paysupport"))
async def paysupport(
    message: Message
):

    await message.answer(

        "🪡 <b>ПОДДЕРЖКА</b>\n\n"

        "Если возникла проблема с оплатой "
        "или VPN — напиши администратору."
    )


# =========================================================
# КОМАНДЫ TELEGRAM
# =========================================================

async def setup_bot():

    await bot.set_my_commands(

        [
            BotCommand(
                command="start",
                description="Запустить ОтвалиVPN",
            ),

            BotCommand(
                command="pay",
                description="Купить VPN",
            ),

            BotCommand(
                command="myid",
                description="Мой Telegram ID",
            ),

            BotCommand(
                command="terms",
                description="Условия",
            ),

            BotCommand(
                command="paysupport",
                description="Поддержка",
            ),
        ]
    )

    logger.info(
        "Команды Telegram установлены"
    )


# =========================================================
# MAIN
# =========================================================

async def main():

    if not BOT_TOKEN:

        raise RuntimeError(
            "❌ BOT_TOKEN не найден в Railway Variables"
        )

    if ADMIN_ID <= 0:

        raise RuntimeError(
            "❌ ADMIN_ID не найден в Railway Variables"
        )

    logger.info(
        "Запуск ОтвалиVPN..."
    )

    await setup_bot()

    await dp.start_polling(
        bot
    )


# =========================================================
# ЗАПУСК
# =========================================================

if __name__ == "__main__":

    asyncio.run(main())
