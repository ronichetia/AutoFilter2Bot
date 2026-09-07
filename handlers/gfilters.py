import logging
from telegram import Update
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters as ptb_filters,
)

from config import Config
from database.gfilters_db import (
    add_gfilter,
    get_gfilter,
    get_all_gfilters,
    delete_gfilter,
    delete_all_gfilters,
    count_gfilters,
)

logger = logging.getLogger(__name__)


async def add_gfilter_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add a global filter (admin only): /gfilter <trigger> <reply>"""
    user_id = update.effective_user.id

    if user_id not in Config.ADMINS:
        await update.message.reply_text("⛔ This command is for bot admins only.")
        return

    if not context.args:
        await update.message.reply_text(
            "Usage: /gfilter <trigger> <reply text>\n"
            "Or: /gfilter <trigger> (reply to a message)"
        )
        return

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
        reply_message_id = reply_msg.message_id
    else:
        await update.message.reply_text(
            "❌ Please provide reply text or reply to a message.\n"
            "Usage: /gfilter <trigger> <reply text>"
        )
        return

    await add_gfilter(
        trigger=trigger,
        reply_text=reply_text,
        reply_message_id=reply_message_id,
    )

    await update.message.reply_text(
        f"✅ Global filter added!\n"
        f"<b>Trigger:</b> <code>{trigger}</code>\n"
        f"<b>Reply:</b> {reply_text[:100] if reply_text else '(message)'}",
        parse_mode="HTML",
    )


async def list_gfilters_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List global filters: /gfilters"""
    user_id = update.effective_user.id

    if user_id not in Config.ADMINS:
        await update.message.reply_text("⛔ This command is for bot admins only.")
        return

    all_gfilters = await get_all_gfilters()
    if not all_gfilters:
        await update.message.reply_text("ℹ️ No global filters set.")
        return

    text = f"<b>🌐 Global Filters ({len(all_gfilters)}):</b>\n\n"
    for i, f in enumerate(all_gfilters, 1):
        trigger = f.get("trigger", "?")
        text += f"{i}. <code>{trigger}</code>\n"

    text += "\nUse /gdel <trigger> to remove."
    await update.message.reply_text(text=text, parse_mode="HTML")


async def delete_gfilter_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete a global filter: /gdel <trigger>"""
    user_id = update.effective_user.id

    if user_id not in Config.ADMINS:
        await update.message.reply_text("⛔ This command is for bot admins only.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /gdel <trigger>")
        return

    trigger = context.args[0].lower()
    result = await delete_gfilter(trigger)

    if result:
        await update.message.reply_text(
            f"✅ Global filter <code>{trigger}</code> deleted.",
            parse_mode="HTML",
        )
    else:
        await update.message.reply_text(
            f"❌ Global filter <code>{trigger}</code> not found.",
            parse_mode="HTML",
        )


async def delete_all_gfilters_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete all global filters: /gdelall"""
    user_id = update.effective_user.id

    if user_id not in Config.ADMINS:
        await update.message.reply_text("⛔ This command is for bot admins only.")
        return

    count = await count_gfilters()
    if count == 0:
        await update.message.reply_text("ℹ️ No global filters to delete.")
        return

    await delete_all_gfilters()
    await update.message.reply_text(f"✅ All {count} global filters deleted.")


async def check_gfilters_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check incoming messages against global filters (all chats)."""
    message = update.effective_message
    if not message or not message.text:
        return

    text_lower = message.text.lower()

    all_gfilters = await get_all_gfilters()
    if not all_gfilters:
        return

    for f in all_gfilters:
        trigger = f.get("trigger", "")
        if trigger in text_lower:
            reply_text = f.get("reply_text")
            if reply_text:
                await message.reply_text(reply_text)
            return  # Match first only


def register(app):
    """Register global filter handlers."""
    app.add_handler(CommandHandler("gfilter", add_gfilter_command))
    app.add_handler(CommandHandler("gfilters", list_gfilters_command))
    app.add_handler(CommandHandler("gdel", delete_gfilter_command))
    app.add_handler(CommandHandler("gdelall", delete_all_gfilters_command))

    # Global filter checker — lowest priority group
    app.add_handler(
        MessageHandler(
            (ptb_filters.ChatType.GROUPS | ptb_filters.ChatType.PRIVATE)
            & ptb_filters.TEXT
            & ~ptb_filters.COMMAND,
            check_gfilters_handler,
        ),
        group=6,
    )
