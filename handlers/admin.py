"""Admin command handlers for AutoFilterBot."""

import os
import sys
import asyncio
import logging
import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
from telegram.error import TelegramError

from config import Config

logger = logging.getLogger(__name__)

USERS_PER_PAGE = 10
CHATS_PER_PAGE = 10


def _admin_only(func):
    """Decorator to restrict handler to admins."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not Config.is_admin(update.effective_user.id):
            return
        return await func(update, context)
    wrapper.__name__ = func.__name__
    return wrapper


# ---------------------------------------------------------------------------
#  /stats
# ---------------------------------------------------------------------------
@_admin_only
async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show bot statistics."""
    from database.users_db import count_users
    from database.chats_db import count_chats
    from database.files_db import count_files
    from database.premium_db import count_premium

    users = await count_users()
    chats = await count_chats()
    files = await count_files()
    premium = await count_premium()

    text = (
        "📊 <b>Bot Statistics</b>\n\n"
        f"👤 Users: <code>{users}</code>\n"
        f"💬 Chats: <code>{chats}</code>\n"
        f"📁 Files: <code>{files}</code>\n"
        f"⭐ Premium Users: <code>{premium}</code>\n\n"
        f"🕐 <i>{datetime.datetime.now(datetime.timezone.utc):%Y-%m-%d %H:%M:%S} UTC</i>"
    )
    await update.message.reply_text(text, parse_mode="HTML")


# ---------------------------------------------------------------------------
#  /logs
# ---------------------------------------------------------------------------
@_admin_only
async def logs_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send last 50 lines of log file."""
    log_file = getattr(Config, "LOG_FILE", "bot.log")

    if not os.path.exists(log_file):
        await update.message.reply_text("📜 No log file found.")
        return

    try:
        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        last_lines = lines[-50:]
        text = "".join(last_lines)

        if len(text) > 4000:
            # Send as file instead
            await update.message.reply_document(
                document=open(log_file, "rb"),
                filename="logs.txt",
                caption="📜 Full log (last 50 lines too large for message)",
            )
        else:
            await update.message.reply_text(
                f"📜 <b>Last 50 log lines:</b>\n\n<pre>{text}</pre>",
                parse_mode="HTML",
            )
    except Exception as e:
        await update.message.reply_text(f"❌ Error reading logs: {e}")


# ---------------------------------------------------------------------------
#  /broadcast
# ---------------------------------------------------------------------------
@_admin_only
async def broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Broadcast replied-to message to all users."""
    if not update.message.reply_to_message:
        await update.message.reply_text(
            "⚠️ Reply to a message with /broadcast to send it to all users."
        )
        return

    from database.users_db import get_all_users

    cursor = await get_all_users()
    user_ids_docs = await cursor.to_list(length=None)
    user_ids = [u["user_id"] for u in user_ids_docs]
    msg = update.message.reply_to_message

    sent = 0
    failed = 0
    status = await update.message.reply_text("📡 Broadcasting...")

    for uid in user_ids:
        try:
            await msg.copy(chat_id=uid)
            sent += 1
        except TelegramError:
            failed += 1

        # Throttle to avoid flood limits
        if (sent + failed) % 25 == 0:
            await asyncio.sleep(1)

        # Update status every 100 messages
        if (sent + failed) % 100 == 0:
            try:
                await status.edit_text(
                    f"📡 Broadcasting...\n✅ Sent: {sent}\n❌ Failed: {failed}"
                )
            except TelegramError:
                pass

    await status.edit_text(
        f"📡 <b>Broadcast Complete</b>\n\n"
        f"✅ Sent: <code>{sent}</code>\n"
        f"❌ Failed: <code>{failed}</code>\n"
        f"📊 Total: <code>{sent + failed}</code>",
        parse_mode="HTML",
    )


# ---------------------------------------------------------------------------
#  /users (paginated)
# ---------------------------------------------------------------------------
@_admin_only
async def users_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show paginated list of users."""
    await _send_users_page(update.message, context, page=0)


async def _send_users_page(message_or_query, context, page: int):
    from database.users_db import count_users, get_all_users

    total = await count_users()
    cursor = await get_all_users()
    all_users = await cursor.to_list(length=None)
    users = all_users[page * USERS_PER_PAGE : (page + 1) * USERS_PER_PAGE]

    if not users:
        text = "👤 No users found."
    else:
        text = f"👤 <b>Users (Page {page + 1})</b>\n\n"
        for i, u in enumerate(users, start=page * USERS_PER_PAGE + 1):
            uid = u.get("user_id", "?")
            name = u.get("name", "Unknown")
            text += f"{i}. <code>{uid}</code> — {name}\n"

    total_pages = max(1, (total + USERS_PER_PAGE - 1) // USERS_PER_PAGE)
    buttons = []
    if page > 0:
        buttons.append(InlineKeyboardButton("◀️ Prev", callback_data=f"adm_usr_{page - 1}"))
    if page < total_pages - 1:
        buttons.append(InlineKeyboardButton("Next ▶️", callback_data=f"adm_usr_{page + 1}"))

    markup = InlineKeyboardMarkup([buttons]) if buttons else None

    if hasattr(message_or_query, "edit_text"):
        await message_or_query.edit_text(text, parse_mode="HTML", reply_markup=markup)
    else:
        await message_or_query.reply_text(text, parse_mode="HTML", reply_markup=markup)


async def users_page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not Config.is_admin(update.effective_user.id):
        return
    query = update.callback_query
    await query.answer()
    page = int(query.data.split("_")[-1])
    await _send_users_page(query.message, context, page)


# ---------------------------------------------------------------------------
#  /chats (paginated)
# ---------------------------------------------------------------------------
@_admin_only
async def chats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show paginated list of chats."""
    await _send_chats_page(update.message, context, page=0)


async def _send_chats_page(message_or_query, context, page: int):
    from database.chats_db import count_chats, get_all_chats

    total = await count_chats()
    cursor = await get_all_chats()
    all_chats = await cursor.to_list(length=None)
    chats = all_chats[page * CHATS_PER_PAGE : (page + 1) * CHATS_PER_PAGE]

    if not chats:
        text = "💬 No chats found."
    else:
        text = f"💬 <b>Chats (Page {page + 1})</b>\n\n"
        for i, c in enumerate(chats, start=page * CHATS_PER_PAGE + 1):
            cid = c.get("chat_id", "?")
            title = c.get("title", "Unknown")
            disabled = " 🔴" if c.get("disabled") else ""
            text += f"{i}. <code>{cid}</code> — {title}{disabled}\n"

    total_pages = max(1, (total + CHATS_PER_PAGE - 1) // CHATS_PER_PAGE)
    buttons = []
    if page > 0:
        buttons.append(InlineKeyboardButton("◀️ Prev", callback_data=f"adm_cht_{page - 1}"))
    if page < total_pages - 1:
        buttons.append(InlineKeyboardButton("Next ▶️", callback_data=f"adm_cht_{page + 1}"))

    markup = InlineKeyboardMarkup([buttons]) if buttons else None

    if hasattr(message_or_query, "edit_text"):
        await message_or_query.edit_text(text, parse_mode="HTML", reply_markup=markup)
    else:
        await message_or_query.reply_text(text, parse_mode="HTML", reply_markup=markup)


async def chats_page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not Config.is_admin(update.effective_user.id):
        return
    query = update.callback_query
    await query.answer()
    page = int(query.data.split("_")[-1])
    await _send_chats_page(query.message, context, page)


# ---------------------------------------------------------------------------
#  /ban, /unban
# ---------------------------------------------------------------------------
@_admin_only
async def ban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ban a user by ID."""
    if not context.args:
        await update.message.reply_text("Usage: /ban <user_id>")
        return

    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID.")
        return

    from database.users_db import ban_user
    await ban_user(user_id)
    await update.message.reply_text(f"🚫 User <code>{user_id}</code> has been banned.", parse_mode="HTML")


@_admin_only
async def unban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unban a user by ID."""
    if not context.args:
        await update.message.reply_text("Usage: /unban <user_id>")
        return

    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID.")
        return

    from database.users_db import unban_user
    await unban_user(user_id)
    await update.message.reply_text(f"✅ User <code>{user_id}</code> has been unbanned.", parse_mode="HTML")


# ---------------------------------------------------------------------------
#  /leave
# ---------------------------------------------------------------------------
@_admin_only
async def leave_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Leave a chat by ID."""
    if not context.args:
        await update.message.reply_text("Usage: /leave <chat_id>")
        return

    try:
        chat_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid chat ID.")
        return

    try:
        await context.bot.leave_chat(chat_id)
        await update.message.reply_text(f"👋 Left chat <code>{chat_id}</code>.", parse_mode="HTML")
    except TelegramError as e:
        await update.message.reply_text(f"❌ Failed to leave chat: {e}")


# ---------------------------------------------------------------------------
#  /disable, /enable
# ---------------------------------------------------------------------------
@_admin_only
async def disable_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Disable a chat (stop auto-filtering there)."""
    if not context.args:
        await update.message.reply_text("Usage: /disable <chat_id>")
        return

    try:
        chat_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid chat ID.")
        return

    from database.chats_db import disable_chat
    await disable_chat(chat_id)
    await update.message.reply_text(f"🔴 Chat <code>{chat_id}</code> disabled.", parse_mode="HTML")


@_admin_only
async def enable_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enable a chat."""
    if not context.args:
        await update.message.reply_text("Usage: /enable <chat_id>")
        return

    try:
        chat_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid chat ID.")
        return

    from database.chats_db import enable_chat
    await enable_chat(chat_id)
    await update.message.reply_text(f"🟢 Chat <code>{chat_id}</code> enabled.", parse_mode="HTML")


# ---------------------------------------------------------------------------
#  /deleteall, /delete
# ---------------------------------------------------------------------------
@_admin_only
async def deleteall_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete all indexed files."""
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚠️ Yes, Delete All", callback_data="adm_delall_y"),
            InlineKeyboardButton("❌ Cancel", callback_data="adm_delall_n"),
        ]
    ])
    await update.message.reply_text(
        "🗑️ <b>Are you sure you want to delete ALL indexed files?</b>\n"
        "This action cannot be undone!",
        parse_mode="HTML",
        reply_markup=keyboard,
    )


async def deleteall_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not Config.is_admin(update.effective_user.id):
        return
    query = update.callback_query
    await query.answer()

    if query.data == "adm_delall_y":
        from database.files_db import col as files_col
        result = await files_col.delete_many({})
        count = result.deleted_count
        await query.edit_message_text(
            f"🗑️ Deleted <code>{count}</code> files from index.", parse_mode="HTML"
        )
    else:
        await query.edit_message_text("❌ Cancelled.")


@_admin_only
async def delete_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete specific file(s) by replying to a file message."""
    if not update.message.reply_to_message:
        await update.message.reply_text(
            "⚠️ Reply to a file message with /delete to remove it from the index."
        )
        return

    reply = update.message.reply_to_message
    # Try to extract file_id from the replied message
    file_id = None
    for attr in ("document", "video", "audio"):
        media = getattr(reply, attr, None)
        if media:
            file_id = media.file_unique_id
            break

    if not file_id:
        await update.message.reply_text("❌ No file found in the replied message.")
        return

    from database.files_db import delete_file
    deleted = await delete_file(file_id)

    await update.message.reply_text(f"🗑️ File deleted from index. (unique_id: <code>{file_id}</code>)", parse_mode="HTML")


# ---------------------------------------------------------------------------
#  /addpremium, /removepremium, /premiumlist
# ---------------------------------------------------------------------------
@_admin_only
async def addpremium_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add premium to a user for N days."""
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /addpremium <user_id> <days>")
        return

    try:
        user_id = int(context.args[0])
        days = int(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ Invalid arguments. Use: /addpremium <user_id> <days>")
        return

    from database.premium_db import add_premium
    expiry = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=days)
    await add_premium(user_id, expiry, f"{days}-day admin grant")
    await update.message.reply_text(
        f"⭐ Premium added for user <code>{user_id}</code> for {days} day(s).",
        parse_mode="HTML",
    )


@_admin_only
async def removepremium_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove premium from a user."""
    if not context.args:
        await update.message.reply_text("Usage: /removepremium <user_id>")
        return

    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID.")
        return

    from database.premium_db import remove_premium
    await remove_premium(user_id)
    await update.message.reply_text(
        f"⭐ Premium removed for user <code>{user_id}</code>.", parse_mode="HTML"
    )


@_admin_only
async def premiumlist_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all premium users."""
    from database.premium_db import get_all_premium

    cursor = await get_all_premium()
    premiums = await cursor.to_list(length=None)

    if not premiums:
        await update.message.reply_text("⭐ No premium users.")
        return

    text = "⭐ <b>Premium Users</b>\n\n"
    for i, p in enumerate(premiums, 1):
        uid = p.get("user_id", "?")
        expiry = p.get("expiry_date")
        if expiry:
            exp_str = expiry.strftime("%Y-%m-%d %H:%M")
        else:
            exp_str = "Lifetime"
        text += f"{i}. <code>{uid}</code> — Expires: {exp_str}\n"

    await update.message.reply_text(text, parse_mode="HTML")


# ---------------------------------------------------------------------------
#  /restart
# ---------------------------------------------------------------------------
@_admin_only
async def restart_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Restart the bot process."""
    await update.message.reply_text("🔄 Restarting bot...")
    logger.info(f"Bot restart requested by admin {update.effective_user.id}")

    # Give time for the message to send
    await asyncio.sleep(1)

    os.execl(sys.executable, sys.executable, *sys.argv)


# ---------------------------------------------------------------------------
#  register
# ---------------------------------------------------------------------------
def register(app):
    """Register all admin command handlers."""
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("logs", logs_cmd))
    app.add_handler(CommandHandler("broadcast", broadcast_cmd))
    app.add_handler(CommandHandler("users", users_cmd))
    app.add_handler(CommandHandler("chats", chats_cmd))
    app.add_handler(CommandHandler("ban", ban_cmd))
    app.add_handler(CommandHandler("unban", unban_cmd))
    app.add_handler(CommandHandler("leave", leave_cmd))
    app.add_handler(CommandHandler("disable", disable_cmd))
    app.add_handler(CommandHandler("enable", enable_cmd))
    app.add_handler(CommandHandler("deleteall", deleteall_cmd))
    app.add_handler(CommandHandler("delete", delete_cmd))
    app.add_handler(CommandHandler("addpremium", addpremium_cmd))
    app.add_handler(CommandHandler("removepremium", removepremium_cmd))
    app.add_handler(CommandHandler("premiumlist", premiumlist_cmd))
    app.add_handler(CommandHandler("restart", restart_cmd))

    # Pagination callbacks
    app.add_handler(CallbackQueryHandler(users_page_callback, pattern=r"^adm_usr_\d+$"))
    app.add_handler(CallbackQueryHandler(chats_page_callback, pattern=r"^adm_cht_\d+$"))
    app.add_handler(CallbackQueryHandler(deleteall_confirm_callback, pattern=r"^adm_delall_"))
