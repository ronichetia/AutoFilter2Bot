import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from config import Config
from database.files_db import search_files, get_file
from database.connections_db import get_active_connection
from handlers.search import (
    RESULTS_PER_PAGE,
    _format_size,
    _build_results_keyboard,
    _collect_filter_values,
    _build_filter_buttons,
)

logger = logging.getLogger(__name__)


async def pm_search_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages in PM — search if PM_SEARCH is enabled or connection exists."""
    message = update.effective_message
    user_id = update.effective_user.id
    query = message.text.strip()

    if not query or len(query) < 2:
        return

    # Check if PM search is enabled globally
    pm_enabled = getattr(Config, "PM_SEARCH", True)
    if not pm_enabled:
        # Check if user has a connected group
        connection = await get_active_connection(user_id)
        if not connection:
            await message.reply_text(
                "🔒 PM search is disabled.\n"
                "Use /connect <group_id> to connect a group first."
            )
            return

    # Search files DB
    results, total = await search_files(query=query, page=0, per_page=RESULTS_PER_PAGE)

    if not results:
        # Try fuzzy
        results, total = await search_files(
            query=query, page=0, per_page=RESULTS_PER_PAGE, fuzzy=True
        )

    if not results:
        await message.reply_text(
            f"❌ No results found for: <i>{query}</i>",
            parse_mode="HTML",
        )
        return

    # Collect filter values from broader result set
    all_results, _ = await search_files(query=query, page=0, per_page=100)
    filter_values = _collect_filter_values(all_results)

    text = (
        f"<b>🔍 Results for:</b> <i>{query}</i>\n"
        f"<b>📁 Found:</b> {total} files\n"
    )

    kb = _build_results_keyboard(results, page=0, total=total, query=query)

    if filter_values:
        filter_rows = _build_filter_buttons(filter_values, query)
        all_buttons = filter_rows + list(kb.inline_keyboard)
        kb = InlineKeyboardMarkup(all_buttons)

    await message.reply_text(
        text=text,
        reply_markup=kb,
        parse_mode="HTML",
    )


async def pm_file_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle file selection in PM — send file directly."""
    query = update.callback_query
    data = query.data

    if not data.startswith("pmf#"):
        return

    await query.answer()
    file_id_key = data[4:]
    user_id = update.effective_user.id

    file_doc = await get_file(file_id_key)
    if not file_doc:
        await query.answer("❌ File not found!", show_alert=True)
        return

    actual_file_id = file_doc.get("file_id")
    file_type = file_doc.get("file_type", "document")

    try:
        send_method = {
            "video": context.bot.send_video,
            "audio": context.bot.send_audio,
        }.get(file_type, context.bot.send_document)

        await send_method(
            chat_id=user_id,
            **{file_type if file_type in ("video", "audio") else "document": actual_file_id},
            caption=f"📁 {file_doc.get('file_name', 'File')}",
        )
    except Exception as e:
        logger.error(f"PM file send error: {e}")
        await query.answer("❌ Failed to send file.", show_alert=True)


def register(app):
    """Register PM search handlers."""
    app.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND,
            pm_search_handler,
        ),
        group=3,
    )
    app.add_handler(
        CallbackQueryHandler(pm_file_callback, pattern=r"^pmf#")
    )
