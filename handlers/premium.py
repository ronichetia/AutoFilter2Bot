"""Premium features handler for AutoFilterBot."""

import logging
import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from config import Config

logger = logging.getLogger(__name__)

# Available plans (display only — actual purchase handled externally or by admin)
PREMIUM_PLANS = [
    {"name": "Weekly", "duration": "7 days", "price": "₹29 / $0.49"},
    {"name": "Monthly", "duration": "30 days", "price": "₹99 / $1.49"},
    {"name": "Yearly", "duration": "365 days", "price": "₹499 / $6.99"},
    {"name": "Lifetime", "duration": "Forever", "price": "₹999 / $12.99"},
]


async def myplan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's premium status."""
    user_id = update.effective_user.id

    from database.premium_db import get_premium

    info = await get_premium(user_id)

    if not info:
        await update.message.reply_text(
            "⭐ <b>Premium Status</b>\n\n"
            "📌 Plan: <b>Free</b>\n\n"
            "Upgrade to Premium for:\n"
            "• No token verification\n"
            "• No shortlinks\n"
            "• Priority file access\n"
            "• Custom captions & thumbnails\n\n"
            "Use /plans to see available plans.",
            parse_mode="HTML",
        )
        return

    expiry = info.get("expiry_date")
    if expiry:
        if isinstance(expiry, datetime.datetime):
            remaining = expiry - datetime.datetime.now(datetime.timezone.utc)
            days_left = max(0, remaining.days)
            expiry_str = expiry.strftime("%Y-%m-%d %H:%M UTC")
            remaining_str = f"{days_left} day(s)"
        else:
            expiry_str = str(expiry)
            remaining_str = "Unknown"
    else:
        expiry_str = "Never (Lifetime)"
        remaining_str = "∞"

    await update.message.reply_text(
        "⭐ <b>Premium Status</b>\n\n"
        f"📌 Plan: <b>Premium</b>\n"
        f"📅 Expires: <code>{expiry_str}</code>\n"
        f"⏳ Remaining: <b>{remaining_str}</b>\n\n"
        "✅ Benefits active:\n"
        "• No token verification\n"
        "• No shortlinks\n"
        "• Priority file access",
        parse_mode="HTML",
    )


async def plans_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show available premium plans."""
    text = "⭐ <b>Premium Plans</b>\n\n"

    for plan in PREMIUM_PLANS:
        text += (
            f"📌 <b>{plan['name']}</b>\n"
            f"   ⏱️ Duration: {plan['duration']}\n"
            f"   💰 Price: {plan['price']}\n\n"
        )

    text += (
        "💎 <b>Premium Benefits:</b>\n"
        "• Skip token verification\n"
        "• No shortlinks on files\n"
        "• Priority file access\n"
        "• Custom captions & thumbnails\n\n"
        "📩 Contact admin to purchase."
    )

    admin_buttons = []
    admin_ids = getattr(Config, "ADMIN_IDS", [])
    if admin_ids:
        admin_buttons.append(
            InlineKeyboardButton(
                "📩 Contact Admin",
                url=f"tg://user?id={admin_ids[0]}",
            )
        )

    markup = InlineKeyboardMarkup([admin_buttons]) if admin_buttons else None

    await update.message.reply_text(text, parse_mode="HTML", reply_markup=markup)


async def refer_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's referral link and referral count."""
    user_id = update.effective_user.id
    bot_username = (await context.bot.get_me()).username

    refer_link = f"https://t.me/{bot_username}?start=ref_{user_id}"

    from database.users_db import get_referral_count
    ref_count = await get_referral_count(user_id)

    await update.message.reply_text(
        "🔗 <b>Referral Program</b>\n\n"
        f"Your referral link:\n<code>{refer_link}</code>\n\n"
        f"👥 Total referrals: <b>{ref_count}</b>\n\n"
        "Share your link and earn rewards!",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📤 Share Link", url=f"https://t.me/share/url?url={refer_link}&text=Check%20out%20this%20bot!")]
        ]),
    )


def register(app):
    """Register premium handlers."""
    app.add_handler(CommandHandler("myplan", myplan_cmd))
    app.add_handler(CommandHandler("plans", plans_cmd))
    app.add_handler(CommandHandler("refer", refer_cmd))
