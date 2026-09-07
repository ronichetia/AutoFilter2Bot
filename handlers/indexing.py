import logging
import asyncio
from telegram import Update
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from config import Config
from database.files_db import save_file

logger = logging.getLogger(__name__)

# Per-user skip count for bulk indexing
_skip_counts = {}


def _extract_file_info(message):
    """Extract file metadata from a channel post message."""
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
    """Auto-index files posted to configured file channels."""
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


async def index_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command: /index channel_id — bulk index a channel's file history."""
    user_id = update.effective_user.id
    if user_id not in Config.ADMINS:
        await update.message.reply_text("⛔ This command is for admins only.")
        return

    if not context.args:
        await update.message.reply_text(
            "Usage: /index <channel_id>\n"
            "Example: /index -1001234567890\n\n"
            "Use /setskip <number> to skip messages before indexing."
        )
        return

    try:
        channel_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid channel ID. Must be a number.")
        return

    skip = _skip_counts.get(user_id, 0)
    status_msg = await update.message.reply_text(
        f"📂 Starting indexing from channel <code>{channel_id}</code>...\n"
        f"Skip: {skip} messages",
        parse_mode="HTML",
    )

    total = 0
    saved = 0
    errors = 0
    skipped = 0

    try:
        # Iterate through channel message history
        # We'll fetch messages using get_chat and iterating by message ID
        # PTB doesn't have iter_history, so we use a workaround via forwarding
        # Actually, we need to use context.bot methods
        msg_id = 1  # Start from first message
        skip_remaining = skip

        # Try to get the latest message to know the range
        # We'll use a batch approach
        progress_interval = 50

        # Forward-based indexing: try fetching messages by forwarding from channel
        # Alternative: use copy_message or forward_message to probe
        # Best approach: iterate using getUpdates is not viable, use a different strategy
        # We'll use the Telegram Bot API's forwardMessage to probe messages

        await status_msg.edit_text(
            f"📂 Indexing channel <code>{channel_id}</code>...\n"
            f"Skipping first {skip} messages.\n"
            f"This may take a while...",
            parse_mode="HTML",
        )

        # Use copy_message approach to find and index files
        # We probe message IDs sequentially
        consecutive_failures = 0
        max_consecutive_failures = 50
        msg_id = skip + 1

        while consecutive_failures < max_consecutive_failures:
            try:
                # Try to forward the message to ourselves temporarily
                forwarded = await context.bot.forward_message(
                    chat_id=user_id,
                    from_chat_id=channel_id,
                    message_id=msg_id,
                )

                total += 1
                consecutive_failures = 0

                # Check if it has a file
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

                # Delete the forwarded message
                try:
                    await forwarded.delete()
                except Exception:
                    pass

                # Update progress
                if total % progress_interval == 0:
                    try:
                        await status_msg.edit_text(
                            f"📂 Indexing in progress...\n\n"
                            f"📊 <b>Progress:</b>\n"
                            f"├ Scanned: {total}\n"
                            f"├ Saved: {saved}\n"
                            f"├ Errors: {errors}\n"
                            f"└ Current MSG ID: {msg_id}",
                            parse_mode="HTML",
                        )
                    except Exception:
                        pass

                # Rate limiting
                if total % 10 == 0:
                    await asyncio.sleep(0.5)

            except Exception:
                consecutive_failures += 1

            msg_id += 1

    except Exception as e:
        logger.error(f"Indexing error: {e}")
        errors += 1

    # Final report
    await status_msg.edit_text(
        f"✅ <b>Indexing Complete!</b>\n\n"
        f"📊 <b>Results:</b>\n"
        f"├ Total scanned: {total}\n"
        f"├ Files saved: {saved}\n"
        f"├ Errors: {errors}\n"
        f"└ Channel: <code>{channel_id}</code>",
        parse_mode="HTML",
    )


async def setskip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set skip count for next /index operation."""
    user_id = update.effective_user.id
    if user_id not in Config.ADMINS:
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
    # Channel post auto-indexing
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
