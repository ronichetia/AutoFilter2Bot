import logging
import asyncio
from telegram import Update
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from telegram.error import TelegramError

from config import Config
from database.files_db import save_file, count_files

logger = logging.getLogger(__name__)

# Per-user skip count for bulk indexing
_skip_counts: dict[int, int] = {}
# Track running index jobs so admins can /cancelindex
_active_jobs: dict[int, bool] = {}  # user_id -> running


def _extract_file_info(message):
    """Extract file metadata from a message object."""
    file_id = None
    file_name = None
    file_size = 0
    file_type = None

    if message.document:
        file_id = message.document.file_id
        file_name = message.document.file_name or "Unknown"
        file_size = message.document.file_size or 0
        file_type = "document"
    elif message.video:
        file_id = message.video.file_id
        file_name = message.video.file_name or "Video"
        file_size = message.video.file_size or 0
        file_type = "video"
    elif message.audio:
        file_id = message.audio.file_id
        file_name = message.audio.file_name or "Audio"
        file_size = message.audio.file_size or 0
        file_type = "audio"

    caption = message.caption or ""
    return file_id, file_name, file_size, file_type, caption


async def channel_post_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Auto-index files posted to configured file channels (real-time)."""
    message = update.channel_post
    if not message:
        return

    chat_id = message.chat_id

    # Only index from configured file channels
    if Config.FILE_CHANNELS and chat_id not in Config.FILE_CHANNELS:
        return

    file_id, file_name, file_size, file_type, caption = _extract_file_info(message)
    if not file_id:
        return

    try:
        await save_file(
            file_id=file_id,
            file_name=file_name,
            file_size=file_size,
            file_type=file_type,
            caption=caption,
            chat_id=chat_id,
            message_id=message.message_id,
        )
        logger.info(f"Indexed: {file_name} from channel {chat_id}")
    except Exception as e:
        logger.error(f"Failed to index file: {e}")


async def _do_index(context, user_id, channel_id, skip, status_msg):
    """Background indexer — forwards to LOG_CHANNEL (or bot's saved messages)
    instead of flooding the admin's PM. Deletes forwarded copies immediately."""

    # Determine a silent destination for probing messages.
    # Prefer LOG_CHANNEL; fall back to the admin's own chat (deleted instantly).
    probe_chat = Config.LOG_CHANNEL or user_id

    total = 0
    saved = 0
    errors = 0
    msg_id = skip + 1
    consecutive_failures = 0
    max_consecutive_failures = 100
    progress_interval = 100
    batch_pause = 20  # pause every N messages to avoid flood limits

    _active_jobs[user_id] = True

    try:
        while consecutive_failures < max_consecutive_failures:
            # Check for cancellation
            if not _active_jobs.get(user_id, False):
                await status_msg.edit_text(
                    f"🛑 <b>Indexing cancelled.</b>\n\n"
                    f"📊 <b>Progress so far:</b>\n"
                    f"├ Scanned: {total}\n"
                    f"├ Saved: {saved}\n"
                    f"├ Errors: {errors}\n"
                    f"└ Last MSG ID: {msg_id - 1}",
                    parse_mode="HTML",
                )
                return

            try:
                # Forward to probe destination (silent, no notification)
                forwarded = await context.bot.forward_message(
                    chat_id=probe_chat,
                    from_chat_id=channel_id,
                    message_id=msg_id,
                    disable_notification=True,
                )

                total += 1
                consecutive_failures = 0

                # Extract file info
                file_id, file_name, file_size, file_type, caption = _extract_file_info(
                    forwarded
                )

                if file_id:
                    try:
                        await save_file(
                            file_id=file_id,
                            file_name=file_name,
                            file_size=file_size,
                            file_type=file_type,
                            caption=caption,
                            chat_id=channel_id,
                            message_id=msg_id,
                        )
                        saved += 1
                    except Exception:
                        errors += 1

                # Delete the forwarded probe message immediately
                try:
                    await forwarded.delete()
                except Exception:
                    pass

                # Progress update
                if total % progress_interval == 0:
                    try:
                        await status_msg.edit_text(
                            f"📂 <b>Indexing in progress...</b>\n\n"
                            f"📊 <b>Progress:</b>\n"
                            f"├ Scanned: {total}\n"
                            f"├ Files saved: {saved}\n"
                            f"├ Errors: {errors}\n"
                            f"└ Current MSG ID: {msg_id}\n\n"
                            f"💡 Use /cancelindex to stop.",
                            parse_mode="HTML",
                        )
                    except Exception:
                        pass

                # Rate limiting — batch pause to avoid Telegram flood
                if total % batch_pause == 0:
                    await asyncio.sleep(1.5)
                else:
                    await asyncio.sleep(0.05)  # tiny delay between each

            except TelegramError:
                consecutive_failures += 1
                # Don't sleep long on missing messages, they're gaps
                await asyncio.sleep(0.02)

            msg_id += 1

    except Exception as e:
        logger.error(f"Indexing error: {e}")

    finally:
        _active_jobs.pop(user_id, None)

    # Final report
    try:
        total_db = await count_files()
        await status_msg.edit_text(
            f"✅ <b>Indexing Complete!</b>\n\n"
            f"📊 <b>Results:</b>\n"
            f"├ Messages scanned: {total}\n"
            f"├ Files saved: {saved}\n"
            f"├ Errors: {errors}\n"
            f"├ Last MSG ID: {msg_id - 1}\n"
            f"└ Total files in DB: {total_db}\n\n"
            f"📂 Channel: <code>{channel_id}</code>",
            parse_mode="HTML",
        )
    except Exception:
        pass


async def index_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command: /index channel_id — bulk index a channel's file history.

    Runs in the background — no PM flood!
    """
    user_id = update.effective_user.id
    if user_id not in Config.ADMIN_IDS:
        await update.message.reply_text("⛔ This command is for admins only.")
        return

    if not context.args:
        await update.message.reply_text(
            "📂 <b>Bulk Indexing</b>\n\n"
            "Usage: <code>/index channel_id</code>\n"
            "Example: <code>/index -1001234567890</code>\n\n"
            "📌 <b>Commands:</b>\n"
            "├ /setskip <number> — skip first N messages\n"
            "├ /cancelindex — stop running index job\n"
            "└ /totalfiles — show total indexed files",
            parse_mode="HTML",
        )
        return

    if _active_jobs.get(user_id):
        await update.message.reply_text(
            "⚠️ An indexing job is already running.\n"
            "Use /cancelindex to stop it first."
        )
        return

    try:
        channel_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid channel ID. Must be a number.")
        return

    skip = _skip_counts.get(user_id, 0)
    status_msg = await update.message.reply_text(
        f"📂 <b>Starting background indexing...</b>\n"
        f"Channel: <code>{channel_id}</code>\n"
        f"Skip: {skip} messages\n\n"
        f"💡 This runs in the background — no PM flood!\n"
        f"Use /cancelindex to stop.",
        parse_mode="HTML",
    )

    # Fire-and-forget — run indexing as a background task
    asyncio.create_task(
        _do_index(context, user_id, channel_id, skip, status_msg)
    )


async def cancelindex_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel a running index job."""
    user_id = update.effective_user.id
    if user_id not in Config.ADMIN_IDS:
        await update.message.reply_text("⛔ This command is for admins only.")
        return

    if _active_jobs.get(user_id):
        _active_jobs[user_id] = False
        await update.message.reply_text("🛑 Cancelling index job...")
    else:
        await update.message.reply_text("ℹ️ No indexing job is running.")


async def totalfiles_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show total indexed files count."""
    user_id = update.effective_user.id
    if user_id not in Config.ADMIN_IDS:
        await update.message.reply_text("⛔ This command is for admins only.")
        return

    total = await count_files()
    await update.message.reply_text(
        f"📊 <b>Total indexed files:</b> {total}",
        parse_mode="HTML",
    )


async def setskip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set skip count for next /index operation."""
    user_id = update.effective_user.id
    if user_id not in Config.ADMIN_IDS:
        await update.message.reply_text("⛔ This command is for admins only.")
        return

    if not context.args:
        current = _skip_counts.get(user_id, 0)
        await update.message.reply_text(
            f"Current skip count: {current}\n"
            f"Usage: /setskip <number>"
        )
        return

    try:
        skip = int(context.args[0])
        if skip < 0:
            raise ValueError
        _skip_counts[user_id] = skip
        await update.message.reply_text(f"✅ Skip count set to {skip}")
    except ValueError:
        await update.message.reply_text("❌ Please provide a valid positive number.")


def register(app):
    """Register indexing handlers."""
    # Channel post auto-indexing (real-time)
    app.add_handler(
        MessageHandler(
            filters.UpdateType.CHANNEL_POST
            & (filters.Document.ALL | filters.VIDEO | filters.AUDIO),
            channel_post_handler,
        ),
        group=1,
    )

    # Admin commands
    app.add_handler(CommandHandler("index", index_command))
    app.add_handler(CommandHandler("setskip", setskip_command))
    app.add_handler(CommandHandler("cancelindex", cancelindex_command))
    app.add_handler(CommandHandler("totalfiles", totalfiles_command))
