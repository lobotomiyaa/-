import os
import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    DefaultBotProperties,
    BotCommand,
)
from aiogram.enums import ParseMode


# =========================================================
# НАСТРОЙКИ
# =========================================================

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))

# ID второго администратора
FRIEND_ADMIN_ID = 1404271536

ADMIN_IDS = {
    ADMIN_ID,
    FRIEND_ADMIN_ID,
}

# Реквизиты берутся из Railway Variables
PAYMENT_DETAILS = os.environ.get(
    "PAYMENT_DETAILS",
    "Реквизиты для оплаты пока не настроены."
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
# ХРАНИЛИЩЕ
# =========================================================

# user_id -> subscription
subscriptions = {}

# payment_id -> payment
pending_payments = {}

# admin_id -> payment_id
admin_states = {}


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
        parse_mode=ParseMode.HTML
    ),
)

dp = Dispatcher()


# =========================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =========================================================

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def create_payment(
    user_id: int,
    username: str | None,
    days: int,
):

    tariff = TARIFFS.get(days)

    if not tariff:
        return None

    payment_id = uuid.uuid4().hex[:10].upper()

    payment = {
        "id": payment_id,
        "user_id": user_id,
        "username": username or "без username",
        "days": days,
        "price": tariff["price"],
        "status": "waiting_payment",
        "created_at": datetime.now(timezone.utc),
        "vpn_url": None,
    }

    pending_payments[payment_id] = payment

    return payment


def get_active_payment(user_id: int):

    for payment in pending_payments.values():

        if (
            payment["user_id"] == user_id
            and payment["status"] in {
                "waiting_payment",
                "waiting_admin",
                "confirmed",
                "waiting_vpn",
            }
        ):
            return payment

    return None


def main_keyboard():

    return InlineKeyboardMarkup(
        inline_keyboard=[
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
    )


def tariffs_keyboard():

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🪦 7 дней — 60 руб",
                    callback_data="tariff:7",
                )
            ],

            [
                InlineKeyboardButton(
                    text="❄️ 14 дней — 100 руб",
                    callback_data="tariff:14",
                )
            ],

            [
                InlineKeyboardButton(
                    text="📜 30 дней — 200 руб",
                    callback_data="tariff:30",
                )
            ],

            [
                InlineKeyboardButton(
                    text="🕊️ 90 дней — 399 руб",
                    callback_data="tariff:90",
                )
            ],

            [
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data="back_main",
                )
            ],
        ]
    )


def confirm_keyboard(days: int):

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Да, купить",
                    callback_data=f"confirm_buy:{days}",
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


def payment_keyboard(payment_id: str):

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Я оплатил",
                    callback_data=f"user_paid:{payment_id}",
                )
            ],

            [
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data=f"cancel:{payment_id}",
                )
            ],
        ]
    )


def admin_payment_keyboard(payment_id: str):

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ ПОДТВЕРДИТЬ ОПЛАТУ",
                    callback_data=f"admin_confirm:{payment_id}",
                )
            ],

            [
                InlineKeyboardButton(
                    text="❌ ОТКЛОНИТЬ",
                    callback_data=f"admin_reject:{payment_id}",
                )
            ],
        ]
    )


# =========================================================
# START
# =========================================================

@dp.message(Command("start"))
async def start(message: Message):

    await message.answer(
        "🪡 <b>ОТВАЛИVPN</b>\n\n"
        "Быстрый VPN без лишнего.\n\n"
        "Выбирай тариф ниже 👇",
        reply_markup=main_keyboard(),
    )


# =========================================================
# КУПИТЬ VPN
# =========================================================

@dp.callback_query(F.data == "buy_menu")
async def buy_menu(callback: CallbackQuery):

    await callback.message.edit_text(
        "💷 <b>Выбери тариф</b>\n\n"
        "Доступные варианты:",
        reply_markup=tariffs_keyboard(),
    )

    await callback.answer()


# =========================================================
# ВЫБОР ТАРИФА
# =========================================================

@dp.callback_query(F.data.startswith("tariff:"))
async def choose_tariff(callback: CallbackQuery):

    days = int(
        callback.data.split(":")[1]
    )

    tariff = TARIFFS.get(days)

    if not tariff:

        await callback.answer(
            "Тариф не найден.",
            show_alert=True,
        )

        return

    await callback.message.edit_text(
        "⚠️ <b>Подтверждение покупки</b>\n\n"

        "Действительно хочешь купить:\n\n"

        f"{tariff['emoji']} "
        f"<b>{tariff['name']}</b>\n"

        f"💰 Стоимость: "
        f"<b>{tariff['price']} руб</b>\n\n"

        "После подтверждения появятся реквизиты для оплаты.",
        
        reply_markup=confirm_keyboard(days),
    )

    await callback.answer()


# =========================================================
# ПОДТВЕРЖДЕНИЕ ПОКУПКИ
# =========================================================

@dp.callback_query(F.data.startswith("confirm_buy:"))
async def confirm_buy(callback: CallbackQuery):

    days = int(
        callback.data.split(":")[1]
    )

    tariff = TARIFFS.get(days)

    if not tariff:

        await callback.answer(
            "Тариф не найден.",
            show_alert=True,
        )

        return

    existing = get_active_payment(
        callback.from_user.id
    )

    if existing:

        await callback.message.edit_text(
            "⚠️ <b>У тебя уже есть активная заявка.</b>\n\n"

            f"Заявка: "
            f"<code>#{existing['id']}</code>\n"

            f"Тариф: "
            f"<b>{existing['days']} дней</b>\n"

            f"Сумма: "
            f"<b>{existing['price']} руб</b>\n\n"

            "Дождись обработки предыдущей заявки."
        )

        await callback.answer()

        return

    payment = create_payment(
        user_id=callback.from_user.id,
        username=callback.from_user.username,
        days=days,
    )

    if not payment:

        await callback.answer(
            "Не удалось создать заявку.",
            show_alert=True,
        )

        return

    await callback.message.edit_text(
        "💷 <b>ОПЛАТА</b>\n\n"

        f"{tariff['emoji']} Тариф: "
        f"<b>{tariff['name']}</b>\n"

        f"💰 Сумма: "
        f"<b>{tariff['price']} руб</b>\n\n"

        "Переведи точную сумму по реквизитам:\n\n"

        f"<code>{PAYMENT_DETAILS}</code>\n\n"

        "После перевода нажми кнопку "
        "«✅ Я оплатил».\n\n"

        "Оплата будет проверена администратором вручную.",

        reply_markup=payment_keyboard(
            payment["id"]
        ),
    )

    await callback.answer()


# =========================================================
# ПОЛЬЗОВАТЕЛЬ НАЖАЛ "Я ОПЛАТИЛ"
# =========================================================

@dp.callback_query(F.data.startswith("user_paid:"))
async def user_paid(callback: CallbackQuery):

    payment_id = callback.data.split(":")[1]

    payment = pending_payments.get(
        payment_id
    )

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
            "Эта заявка уже отправлена на проверку.",
            show_alert=True,
        )

        return

    payment["status"] = "waiting_admin"

    payment["paid_at"] = datetime.now(
        timezone.utc
    )

    await callback.message.edit_text(
        "⏳ <b>Оплата отправлена на проверку.</b>\n\n"

        f"Заявка: <code>#{payment_id}</code>\n"

        f"Тариф: <b>{payment['days']} дней</b>\n"

        f"Сумма: <b>{payment['price']} руб</b>\n\n"

        "Администратор проверит перевод и "
        "подтвердит оплату."
    )

    admin_text = (
        "💷 <b>НОВАЯ ОПЛАТА</b>\n\n"

        f"🆔 Заявка: "
        f"<code>#{payment_id}</code>\n"

        f"👤 Telegram ID: "
        f"<code>{payment['user_id']}</code>\n"

        f"🔗 Username: "
        f"@{payment['username']}\n"

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
                admin_id,
                admin_text,
                reply_markup=admin_payment_keyboard(
                    payment_id
                ),
            )

        except Exception as e:

            logger.error(
                "Ошибка отправки админу %s: %s",
                admin_id,
                e,
            )

    await callback.answer(
        "Заявка отправлена."
    )


# =========================================================
# ОТМЕНА ПЛАТЕЖА
# =========================================================

@dp.callback_query(F.data.startswith("cancel:"))
async def cancel_payment(callback: CallbackQuery):

    payment_id = callback.data.split(":")[1]

    payment = pending_payments.get(
        payment_id
    )

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
            "Заявка уже находится на проверке.",
            show_alert=True,
        )

        return

    payment["status"] = "cancelled"

    await callback.message.edit_text(
        "❌ <b>Покупка отменена.</b>\n\n"
        "Если захочешь купить VPN — "
        "снова нажми «Купить VPN»."
    )

    await callback.answer()


# =========================================================
# АДМИН ПОДТВЕРЖДАЕТ ОПЛАТУ
# =========================================================

@dp.callback_query(F.data.startswith("admin_confirm:"))
async def admin_confirm(callback: CallbackQuery):

    if not is_admin(
        callback.from_user.id
    ):

        await callback.answer(
            "Нет доступа.",
            show_alert=True,
        )

        return

    payment_id = callback.data.split(":")[1]

    payment = pending_payments.get(
        payment_id
    )

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

    admin_states[
        callback.from_user.id
    ] = payment_id

    await callback.message.edit_text(
        "✅ <b>ОПЛАТА ПОДТВЕРЖДЕНА</b>\n\n"

        f"Заявка: <code>#{payment_id}</code>\n"

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
        payment["user_id"],

        "✅ <b>Оплата подтверждена!</b>\n\n"

        f"Тариф: "
        f"<b>{payment['days']} дней</b>\n\n"

        "Сейчас выдаём VPN.\n"
        "Ожидай ссылку."
    )

    await callback.answer(
        "Оплата подтверждена."
    )


# =========================================================
# АДМИН ОТКЛОНЯЕТ ОПЛАТУ
# =========================================================

@dp.callback_query(F.data.startswith("admin_reject:"))
async def admin_reject(callback: CallbackQuery):

    if not is_admin(
        callback.from_user.id
    ):

        await callback.answer(
            "Нет доступа.",
            show_alert=True,
        )

        return

    payment_id = callback.data.split(":")[1]

    payment = pending_payments.get(
        payment_id
    )

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

        f"Заявка: <code>#{payment_id}</code>\n"

        f"Пользователь: "
        f"<code>{payment['user_id']}</code>"
    )

    await bot.send_message(
        payment["user_id"],

        "❌ <b>Оплата не подтверждена.</b>\n\n"

        "Проверь сумму и реквизиты.\n"
        "Если ты действительно сделал перевод — "
        "обратись в поддержку."
    )

    await callback.answer(
        "Оплата отклонена."
    )


# =========================================================
# АДМИН ОТПРАВЛЯЕТ VPN URL
# =========================================================

@dp.message()
async def all_messages(message: Message):

    user_id = message.from_user.id

    # -----------------------------------------------------
    # ЕСЛИ АДМИН СЕЙЧАС ВЫДАЁТ VPN
    # -----------------------------------------------------

    if is_admin(user_id):

        payment_id = admin_states.get(
            user_id
        )

        if payment_id:

            vpn_url = (
                message.text or ""
            ).strip()

            if not (
                vpn_url.startswith("http://")
                or vpn_url.startswith("https://")
            ):

                await message.answer(
                    "❌ Это не похоже на subscription URL.\n\n"
                    "Отправь полную ссылку из 3X-UI."
                )

                return

            payment = pending_payments.get(
                payment_id
            )

            if not payment:

                admin_states.pop(
                    user_id,
                    None
                )

                await message.answer(
                    "❌ Заявка не найдена."
                )

                return

            if payment["status"] != "confirmed":

                admin_states.pop(
                    user_id,
                    None
                )

                await message.answer(
                    "❌ Эта заявка больше "
                    "не ожидает VPN."
                )

                return

            # ---------------------------------------------
            # СОХРАНЯЕМ ПОДПИСКУ
            # ---------------------------------------------

            now = datetime.now(
                timezone.utc
            )

            expires = now + timedelta(
                days=payment["days"]
            )

            subscriptions[
                payment["user_id"]
            ] = {
                "days": payment["days"],
                "price": payment["price"],
                "url": vpn_url,
                "started_at": now,
                "expires_at": expires,
                "payment_id": payment_id,
            }

            payment["vpn_url"] = vpn_url
            payment["status"] = "completed"
            payment["completed_at"] = now

            admin_states.pop(
                user_id,
                None
            )

            # ---------------------------------------------
            # ОТПРАВЛЯЕМ VPN ПОКУПАТЕЛЮ
            # ---------------------------------------------

            await bot.send_message(
                payment["user_id"],

                "⚔️ <b>VPN ГОТОВ</b>\n\n"

                f"Тариф: "
                f"<b>{payment['days']} дней</b>\n"

                f"Оплата: "
                f"<b>{payment['price']} руб</b>\n\n"

                "Твоя subscription-ссылка:\n\n"

                f"<code>{vpn_url}</code>\n\n"

                "Добавь её в Happ или V2Ray."
            )

            await message.answer(
                "✅ <b>VPN выдан.</b>\n\n"

                f"Заявка: "
                f"<code>#{payment_id}</code>\n"

                f"Пользователь: "
                f"<code>{payment['user_id']}</code>"
            )

            return


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
            "💷 <b>Моя подписка</b>\n\n"
            "Активной подписки нет.",
            reply_markup=main_keyboard(),
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
            "💷 <b>Моя подписка</b>\n\n"
            "Подписка закончилась.",
            reply_markup=main_keyboard(),
        )

        await callback.answer()

        return

    expires_text = expires.strftime(
        "%d.%m.%Y %H:%M"
    )

    await callback.message.edit_text(
        "💷 <b>МОЯ ПОДПИСКА</b>\n\n"

        f"📦 Тариф: "
        f"<b>{subscription['days']} дней</b>\n"

        f"📅 До: "
        f"<b>{expires_text}</b>\n\n"

        "🔗 Subscription URL:\n\n"

        f"<code>{subscription['url']}</code>",

        reply_markup=main_keyboard(),
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

        "После окончания срока подписка "
        "перестаёт действовать.",

        reply_markup=main_keyboard(),
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

        reply_markup=main_keyboard(),
    )

    await callback.answer()


# =========================================================
# НАЗАД
# =========================================================

@dp.callback_query(F.data == "back_main")
async def back_main(
    callback: CallbackQuery
):

    await callback.message.edit_text(
        "🪡 <b>ОТВАЛИVPN</b>\n\n"
        "Выбирай нужное действие 👇",

        reply_markup=main_keyboard(),
    )

    await callback.answer()


# =========================================================
# COMMAND /pay
# =========================================================

@dp.message(Command("pay"))
async def pay(message: Message):

    await message.answer(
        "💷 <b>Выбери тариф:</b>",
        reply_markup=tariffs_keyboard(),
    )


# =========================================================
# COMMAND /myid
# =========================================================

@dp.message(Command("myid"))
async def myid(message: Message):

    await message.answer(
        "🆔 Твой Telegram ID:\n\n"
        f"<code>{message.from_user.id}</code>"
    )


# =========================================================
# COMMAND /terms
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
# COMMAND /paysupport
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
# НАСТРОЙКА BOTFATHER-КОМАНД
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
        "Bot setup complete"
    )


# =========================================================
# MAIN
# =========================================================

async def main():

    if not BOT_TOKEN:

        raise RuntimeError(
            "BOT_TOKEN не задан в Railway Variables"
        )

    if ADMIN_ID <= 0:

        raise RuntimeError(
            "ADMIN_ID не задан в Railway Variables"
        )

    await setup_bot()

    logger.info(
        "Starting Telegram polling..."
    )

    try:

        await dp.start_polling(bot)

    finally:

        await bot.session.close()


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    asyncio.run(main())
