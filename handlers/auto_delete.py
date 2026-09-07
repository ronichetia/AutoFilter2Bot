"""Auto-delete handler for AutoFilterBot — deletes files in PM after a delay."""

import asyncio
import logging

from telegram.ext import ContextTypes
from telegram.error import TelegramError

from config import Config

logger = logging.getLogger(__name__)


async def schedule_delete(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    message_id: int,
    delay: int | None = None,
):
    """Schedule a message for deletion after a delay.

    Args:
        context: PTB context (used to access the bot).
        chat_id: Chat where the message lives.
        message_id: ID of the message to delete.
        delay: Seconds to wait before deletion. Defaults to Config.AUTO_DELETE_TIME.
    """
    if delay is None:
        delay = getattr(Config, "AUTO_DELETE_TIME", 600)  # default 10 min

    if delay <= 0:
        return  # auto-delete disabled

    asyncio.create_task(_delete_after(context, chat_id, message_id, delay))


async def _delete_after(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    message_id: int,
    delay: int,
):
    """Internal coroutine: sleep then delete."""
    try:
        await asyncio.sleep(delay)
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
        logger.debug(f"Auto-deleted message {message_id} in chat {chat_id}")
    except TelegramError as e:
        logger.warning(f"Auto-delete failed for msg {message_id} in {chat_id}: {e}")
    except asyncio.CancelledError:
        pass


async def schedule_delete_with_warning(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    message_id: int,
    delay: int | None = None,
):
    """Schedule deletion and send a warning message about upcoming deletion.

    Args:
        context: PTB context.
        chat_id: Chat where the message lives.
        message_id: ID of the message to delete.
        delay: Seconds to wait before deletion.
    """
    if delay is None:
        delay = getattr(Config, "AUTO_DELETE_TIME", 600)

    if delay <= 0:
        return

    minutes = delay // 60
    try:
        warn_msg = await context.bot.send_message(
            chat_id=chat_id,
            text=f"⚠️ This file will be auto-deleted in {minutes} minute(s). "
                 f"Save/forward it before then!",
        )
        # Schedule deletion of both the file and the warning
        asyncio.create_task(_delete_after(context, chat_id, message_id, delay))
        asyncio.create_task(_delete_after(context, chat_id, warn_msg.message_id, delay))
    except TelegramError as e:
        logger.warning(f"Failed to send auto-delete warning: {e}")


def register(app):
    """Register auto-delete handlers (none needed — called programmatically)."""
    pass
