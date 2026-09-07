"""Force subscribe check handler for AutoFilterBot."""

import logging
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ChatMemberUpdated,
)
from telegram.ext import (
    ChatJoinRequestHandler,
    ContextTypes,
)
from telegram.error import TelegramError

from config import Config

logger = logging.getLogger(__name__)


async def check_force_sub(bot, user_id: int) -> bool | InlineKeyboardMarkup:
    """Check if user is a member of AUTH_CHANNEL.

    Args:
        bot: The Bot instance.
        user_id: User ID to check.

    Returns:
        True if subscribed or no AUTH_CHANNEL configured.
        InlineKeyboardMarkup with join button if not subscribed.
    """
    if not Config.AUTH_CHANNEL:
        return True

    try:
        member = await bot.get_chat_member(
            chat_id=Config.AUTH_CHANNEL, user_id=user_id
        )
        status = member.status
        if status in ("member", "administrator", "creator"):
            return True
        elif status == "restricted" and member.is_member:
            return True
    except TelegramError as e:
        logger.warning(f"Force sub check failed for user {user_id}: {e}")
        # If the check fails (bot not admin in channel, etc.), allow the user
        return True

    # User is not subscribed — build join button
    try:
        chat = await bot.get_chat(Config.AUTH_CHANNEL)
        invite_link = chat.invite_link
        if not invite_link:
            invite_link = (await bot.export_chat_invite_link(Config.AUTH_CHANNEL))
    except TelegramError:
        invite_link = f"https://t.me/{Config.AUTH_CHANNEL}" if isinstance(
            Config.AUTH_CHANNEL, str
        ) else None

    buttons = []
    if invite_link:
        buttons.append([
            InlineKeyboardButton("📢 Join Channel", url=invite_link)
        ])
    buttons.append([
        InlineKeyboardButton("🔄 Check Again", callback_data="fsub_check")
    ])

    return InlineKeyboardMarkup(buttons)


async def fsub_check_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle 'Check Again' button press for force sub."""
    query = update.callback_query
    user_id = query.from_user.id

    result = await check_force_sub(context.bot, user_id)
    if result is True:
        await query.answer("✅ You have joined! Try again now.", show_alert=True)
        await query.message.delete()
    else:
        await query.answer(
            "❌ You haven't joined yet. Please join the channel first.",
            show_alert=True,
        )


async def join_request_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Auto-approve join requests for AUTH_CHANNEL (request-to-join mode)."""
    join_request = update.chat_join_request
    if not join_request:
        return

    chat_id = join_request.chat.id
    user_id = join_request.from_user.id

    if Config.AUTH_CHANNEL and chat_id == Config.AUTH_CHANNEL:
        try:
            await join_request.approve()
            logger.info(f"Approved join request from user {user_id} for channel {chat_id}")
        except TelegramError as e:
            logger.error(f"Failed to approve join request: {e}")


def register(app):
    """Register force sub handlers."""
    from telegram.ext import CallbackQueryHandler

    app.add_handler(CallbackQueryHandler(fsub_check_callback, pattern=r"^fsub_check$"))
    app.add_handler(ChatJoinRequestHandler(join_request_handler))
