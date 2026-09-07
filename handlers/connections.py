import logging
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from config import Config
from database.connections_db import (
    add_connection,
    delete_connection,
    get_active_connection,
    get_all_connections,
)

logger = logging.getLogger(__name__)


async def connect_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Connect a group to manage from PM: /connect <group_id>"""
    user_id = update.effective_user.id

    if update.effective_chat.type != "private":
        await update.message.reply_text("⚠️ Use this command in PM only.")
        return

    if not context.args:
        await update.message.reply_text(
            "Usage: /connect <group_id>\n"
            "Example: /connect -1001234567890\n\n"
            "Get the group ID by using /id in the group."
        )
        return

    try:
        group_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid group ID.")
        return

    # Verify user is admin in the group
    try:
        member = await context.bot.get_chat_member(group_id, user_id)
        if member.status not in ("administrator", "creator"):
            await update.message.reply_text(
                "⚠️ You must be an admin in that group to connect it."
            )
            return
    except Exception as e:
        await update.message.reply_text(
            f"❌ Cannot access that group. Make sure I'm a member.\nError: {e}"
        )
        return

    # Get group info
    try:
        chat = await context.bot.get_chat(group_id)
        group_name = chat.title or str(group_id)
    except Exception:
        group_name = str(group_id)

    await add_connection(user_id, group_id, group_name)
    await update.message.reply_text(
        f"✅ Connected to <b>{group_name}</b>!\n\n"
        f"You can now search and manage filters for this group from PM.",
        parse_mode="HTML",
    )


async def disconnect_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Disconnect the active group: /disconnect"""
    user_id = update.effective_user.id

    if update.effective_chat.type != "private":
        await update.message.reply_text("⚠️ Use this command in PM only.")
        return

    connection = await get_active_connection(user_id)
    if not connection:
        await update.message.reply_text("ℹ️ No active connection to disconnect.")
        return

    group_name = connection.get("group_name", "Unknown")
    await delete_connection(user_id)
    await update.message.reply_text(
        f"✅ Disconnected from <b>{group_name}</b>.",
        parse_mode="HTML",
    )


async def connections_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all connections: /connections"""
    user_id = update.effective_user.id

    if update.effective_chat.type != "private":
        await update.message.reply_text("⚠️ Use this command in PM only.")
        return

    connections = await get_all_connections(user_id)
    if not connections:
        await update.message.reply_text(
            "ℹ️ No connections found.\nUse /connect <group_id> to connect a group."
        )
        return

    active = await get_active_connection(user_id)
    active_id = active.get("group_id") if active else None

    text = "<b>📋 Your Connections:</b>\n\n"
    for i, conn in enumerate(connections, 1):
        gid = conn.get("group_id")
        gname = conn.get("group_name", "Unknown")
        marker = " ✅" if gid == active_id else ""
        text += f"{i}. <b>{gname}</b> (<code>{gid}</code>){marker}\n"

    text += "\n✅ = Active connection"
    await update.message.reply_text(text=text, parse_mode="HTML")


def register(app):
    """Register connection handlers."""
    app.add_handler(CommandHandler("connect", connect_command))
    app.add_handler(CommandHandler("disconnect", disconnect_command))
    app.add_handler(CommandHandler("connections", connections_command))
