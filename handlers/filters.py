import logging
from telegram import Update
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters as ptb_filters,
)

from config import Config
from database.filters_db import (
    add_filter,
    get_filter,
    get_all_filters,
    delete_filter,
    delete_all_filters,
    count_filters,
)

logger = logging.getLogger(__name__)


async def add_filter_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add a manual filter: /filter <trigger> <reply> or reply to a message."""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    # Check if user is admin in group
    if update.effective_chat.type in ("group", "supergroup"):
        try:
            member = await context.bot.get_chat_member(chat_id, user_id)
            if member.status not in ("administrator", "creator"):
                await update.message.reply_text("⚠️ Only admins can add filters.")
                return
        except Exception:
            pass

    if not context.args:
        await update.message.reply_text(
            "Usage: /filter <trigger> <reply text>\n"
            "Or: /filter <trigger> (reply to a message)"
        )
        return

    # Parse trigger and reply content
    trigger = context.args[0].lower()
    reply_text = None
    reply_message_id = None

    if len(context.args) > 1:
        reply_text = " ".join(context.args[1:])
    elif update.message.reply_to_message:
        reply_msg = update.message.reply_to_message
        if reply_msg.text:
            reply_text = reply_msg.text
        elif reply_msg.caption:
            reply_text = reply_msg.caption
        # Could also store file_id for media filters
        reply_message_id = reply_msg.message_id
    else:
        await update.message.reply_text(
            "❌ Please provide reply text or reply to a message.\n"
            "Usage: /filter <trigger> <reply text>"
        )
        return

    await add_filter(
        chat_id=chat_id,
        trigger=trigger,
        reply_text=reply_text,
        reply_message_id=reply_message_id,
    )

    await update.message.reply_text(
        f"✅ Filter added!\n"
        f"<b>Trigger:</b> <code>{trigger}</code>\n"
        f"<b>Reply:</b> {reply_text[:100] if reply_text else '(message)'}",
        parse_mode="HTML",
    )


async def list_filters_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all filters: /filters"""
    chat_id = update.effective_chat.id

    all_filters = await get_all_filters(chat_id)
    if not all_filters:
        await update.message.reply_text("ℹ️ No filters set for this chat.")
        return

    text = f"<b>📋 Filters for this chat ({len(all_filters)}):</b>\n\n"
    for i, f in enumerate(all_filters, 1):
        trigger = f.get("trigger", "?")
        text += f"{i}. <code>{trigger}</code>\n"

    text += "\nUse /del <trigger> to remove a filter."
    await update.message.reply_text(text=text, parse_mode="HTML")


async def delete_filter_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete a filter: /del <trigger>"""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if update.effective_chat.type in ("group", "supergroup"):
        try:
            member = await context.bot.get_chat_member(chat_id, user_id)
            if member.status not in ("administrator", "creator"):
                await update.message.reply_text("⚠️ Only admins can delete filters.")
                return
        except Exception:
            pass

    if not context.args:
        await update.message.reply_text("Usage: /del <trigger>")
        return

    trigger = context.args[0].lower()
    result = await delete_filter(chat_id, trigger)

    if result:
        await update.message.reply_text(
            f"✅ Filter <code>{trigger}</code> deleted.",
            parse_mode="HTML",
        )
    else:
        await update.message.reply_text(
            f"❌ Filter <code>{trigger}</code> not found.",
            parse_mode="HTML",
        )


async def delete_all_filters_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete all filters: /delall"""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if update.effective_chat.type in ("group", "supergroup"):
        try:
            member = await context.bot.get_chat_member(chat_id, user_id)
            if member.status not in ("administrator", "creator"):
                await update.message.reply_text("⚠️ Only admins can delete filters.")
                return
        except Exception:
            pass

    count = await count_filters(chat_id)
    if count == 0:
        await update.message.reply_text("ℹ️ No filters to delete.")
        return

    await delete_all_filters(chat_id)
    await update.message.reply_text(f"✅ All {count} filters deleted.")


async def check_filters_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check incoming group messages against manual filters."""
    message = update.effective_message
    if not message or not message.text:
        return

    chat_id = update.effective_chat.id
    text_lower = message.text.lower()

    # Check each word and multi-word triggers
    all_filters = await get_all_filters(chat_id)
    if not all_filters:
        return

    for f in all_filters:
        trigger = f.get("trigger", "")
        if trigger in text_lower:
            reply_text = f.get("reply_text")
            if reply_text:
                await message.reply_text(reply_text)
            return  # Only match first filter


def register(app):
    """Register filter handlers."""
    app.add_handler(CommandHandler("filter", add_filter_command))
    app.add_handler(CommandHandler("filters", list_filters_command))
    app.add_handler(CommandHandler("del", delete_filter_command))
    app.add_handler(CommandHandler("delall", delete_all_filters_command))

    # Filter checker runs at a lower priority group so search runs first
    app.add_handler(
        MessageHandler(
            ptb_filters.ChatType.GROUPS & ptb_filters.TEXT & ~ptb_filters.COMMAND,
            check_filters_handler,
        ),
        group=5,
    )
