import random
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackQueryHandler, ContextTypes

from config import Config
from database.users_db import add_user, is_user_exist

logger = logging.getLogger(__name__)

HELP_TEXT = """<b>📚 Help & Commands</b>

<b>Search:</b>
• Just type a movie/file name in a connected group
• The bot will automatically search and show results

<b>Commands:</b>
/start - Start the bot
/help - Show this help
/connect - Connect a group to PM
/disconnect - Disconnect group
/connections - List connections
/settings - Bot settings

<b>Admin Commands:</b>
/index - Index files from a channel
/setskip - Set skip count for indexing
/filter - Add a manual filter
/filters - List filters
/del - Delete a filter
/delall - Delete all filters
/gfilter - Add a global filter (bot admin)
/gfilters - List global filters
/gdel - Delete global filter
/gdelall - Delete all global filters

<b>How it works:</b>
Add me to a group, connect a file channel, and I'll auto-filter files when users search!"""

ABOUT_TEXT = """<b>ℹ️ About</b>

<b>Auto Filter Bot</b>
A powerful Telegram bot that automatically filters and serves files from indexed channels.

<b>Features:</b>
• Auto-filter files in groups
• Multi-quality/language filters
• PM & group file delivery
• Manual & global filters
• Group connections
• Referral system

<b>Built with:</b> python-telegram-bot v21
<b>Database:</b> MongoDB"""


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command with deep link support."""
    user = update.effective_user
    chat_id = update.effective_chat.id

    # Check for deep link referral
    if context.args and context.args[0].startswith("ref_"):
        try:
            referrer_id = int(context.args[0].replace("ref_", ""))
            if referrer_id != user.id:
                # Log referral - could store in DB
                logger.info(f"User {user.id} referred by {referrer_id}")
        except (ValueError, IndexError):
            pass

    # Register user in DB
    if not await is_user_exist(user.id):
        await add_user(user.id, user.first_name)
        # Log new user to LOG_CHANNEL
        if Config.LOG_CHANNEL:
            try:
                await context.bot.send_message(
                    chat_id=Config.LOG_CHANNEL,
                    text=(
                        f"#NewUser\n"
                        f"<b>Name:</b> {user.first_name}\n"
                        f"<b>ID:</b> <code>{user.id}</code>\n"
                        f"<b>Username:</b> @{user.username or 'N/A'}"
                    ),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error(f"Failed to log new user: {e}")

    # Welcome message with photo and buttons
    buttons = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🔍 Search", switch_inline_query_current_chat=""),
                InlineKeyboardButton("📚 Help", callback_data="help"),
            ],
            [
                InlineKeyboardButton("⚙️ Settings", callback_data="settings"),
                InlineKeyboardButton("ℹ️ About", callback_data="about"),
            ],
        ]
    )

    welcome_text = (
        f"<b>👋 Hey {user.first_name}!</b>\n\n"
        f"I'm an <b>Auto Filter Bot</b>.\n"
        f"Add me to a group and I'll serve files automatically when users search!\n\n"
        f"Use /help for commands."
    )

    pic = random.choice(Config.PICS) if Config.PICS else None
    try:
        if pic:
            await update.message.reply_photo(
                photo=pic,
                caption=welcome_text,
                reply_markup=buttons,
                parse_mode="HTML",
            )
        else:
            await update.message.reply_text(
                text=welcome_text,
                reply_markup=buttons,
                parse_mode="HTML",
            )
    except Exception as e:
        logger.error(f"Start command error: {e}")
        await update.message.reply_text(
            text=welcome_text,
            reply_markup=buttons,
            parse_mode="HTML",
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    buttons = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🔙 Back", callback_data="start")]]
    )
    await update.message.reply_text(
        text=HELP_TEXT,
        reply_markup=buttons,
        parse_mode="HTML",
    )


async def start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline button callbacks for start menu."""
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "help":
        buttons = InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 Back", callback_data="start")]]
        )
        await query.message.edit_text(
            text=HELP_TEXT,
            reply_markup=buttons,
            parse_mode="HTML",
        )

    elif data == "about":
        buttons = InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 Back", callback_data="start")]]
        )
        await query.message.edit_text(
            text=ABOUT_TEXT,
            reply_markup=buttons,
            parse_mode="HTML",
        )

    elif data == "start":
        user = update.effective_user
        buttons = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🔍 Search", switch_inline_query_current_chat=""
                    ),
                    InlineKeyboardButton("📚 Help", callback_data="help"),
                ],
                [
                    InlineKeyboardButton("⚙️ Settings", callback_data="settings"),
                    InlineKeyboardButton("ℹ️ About", callback_data="about"),
                ],
            ]
        )
        welcome_text = (
            f"<b>👋 Hey {user.first_name}!</b>\n\n"
            f"I'm an <b>Auto Filter Bot</b>.\n"
            f"Add me to a group and I'll serve files automatically when users search!\n\n"
            f"Use /help for commands."
        )
        # Try to edit; if the original was a photo, delete and send text
        try:
            await query.message.edit_text(
                text=welcome_text,
                reply_markup=buttons,
                parse_mode="HTML",
            )
        except Exception:
            await query.message.delete()
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=welcome_text,
                reply_markup=buttons,
                parse_mode="HTML",
            )


def register(app):
    """Register start/help handlers."""
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(
        CallbackQueryHandler(start_callback, pattern=r"^(help|about|start|settings)$")
    )
