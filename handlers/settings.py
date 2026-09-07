"""Settings menu handler for AutoFilterBot."""

import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from config import Config

logger = logging.getLogger(__name__)

# Setting keys — stored in DB per chat/user
SETTINGS_DEFS = [
    ("auto_filter",   "Auto Filter",    True),
    ("imdb_info",     "IMDB Info",       True),
    ("spell_check",   "Spell Check",    True),
    ("welcome_msg",   "Welcome Message", True),
    ("auto_delete",   "Auto Delete",     True),
    ("file_secure",   "File Secure",     False),
    ("pm_search",     "PM Search",       True),
    ("shortlink",     "Shortlink",       False),
    ("stream",        "Stream",          False),
    ("button_mode",   "Button Mode",     False),  # False = list, True = grid
    ("max_buttons",   "Max Buttons",     False),  # toggle capped results
]

ON = "✅"
OFF = "❌"


def _build_settings_keyboard(settings: dict) -> InlineKeyboardMarkup:
    """Build the settings inline keyboard from current settings dict."""
    buttons = []
    row = []
    for key, label, default in SETTINGS_DEFS:
        value = settings.get(key, default)
        icon = ON if value else OFF
        row.append(
            InlineKeyboardButton(f"{icon} {label}", callback_data=f"set_{key}")
        )
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    buttons.append([InlineKeyboardButton("❌ Close", callback_data="set_close")])
    return InlineKeyboardMarkup(buttons)


async def settings_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /settings — show settings menu.

    Works in groups (chat settings) and PM (user settings).
    In groups, only admins can change settings.
    """
    chat_id = update.effective_chat.id
    chat_type = update.effective_chat.type

    # In groups, restrict to chat admins or bot admins
    if chat_type in ("group", "supergroup"):
        user = update.effective_user
        if not Config.is_admin(user.id):
            member = await context.bot.get_chat_member(chat_id, user.id)
            if member.status not in ("administrator", "creator"):
                await update.message.reply_text("⚠️ Only admins can change settings.")
                return

    from database.settings_db import get_settings

    settings = await get_settings(chat_id)
    keyboard = _build_settings_keyboard(settings)

    await update.message.reply_text(
        "⚙️ <b>Settings</b>\n\n"
        "Toggle settings on/off by pressing the buttons below.\n"
        f"Chat ID: <code>{chat_id}</code>",
        parse_mode="HTML",
        reply_markup=keyboard,
    )


async def settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle setting toggle callbacks."""
    query = update.callback_query
    data = query.data
    chat_id = query.message.chat_id

    # Close button
    if data == "set_close":
        await query.answer()
        await query.message.delete()
        return

    # Extract setting key from callback data
    if not data.startswith("set_"):
        return
    key = data[4:]  # strip "set_"

    # Permission check in groups
    chat_type = query.message.chat.type
    if chat_type in ("group", "supergroup"):
        user = query.from_user
        if not Config.is_admin(user.id):
            member = await context.bot.get_chat_member(chat_id, user.id)
            if member.status not in ("administrator", "creator"):
                await query.answer("⚠️ Only admins can change settings.", show_alert=True)
                return

    # Validate key
    valid_keys = {s[0] for s in SETTINGS_DEFS}
    if key not in valid_keys:
        await query.answer("Unknown setting.", show_alert=True)
        return

    from database.settings_db import get_settings, update_setting

    settings = await get_settings(chat_id)

    # Find default for this key
    default = next((s[2] for s in SETTINGS_DEFS if s[0] == key), False)
    current = settings.get(key, default)
    new_value = not current

    await update_setting(chat_id, key, new_value)

    # Refresh the settings dict and keyboard
    settings[key] = new_value
    keyboard = _build_settings_keyboard(settings)

    label = next((s[1] for s in SETTINGS_DEFS if s[0] == key), key)
    status = "ON" if new_value else "OFF"
    await query.answer(f"{label}: {status}")

    await query.edit_message_reply_markup(reply_markup=keyboard)


def register(app):
    """Register settings handlers."""
    app.add_handler(CommandHandler("settings", settings_cmd))
    app.add_handler(CallbackQueryHandler(settings_callback, pattern=r"^set_"))
