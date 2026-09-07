"""File interaction handlers for AutoFilterBot."""

import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from telegram.error import TelegramError

from config import Config
from handlers.force_sub import check_force_sub
from handlers.token_verify import is_verified, generate_token, get_verify_keyboard
from handlers.auto_delete import schedule_delete_with_warning

logger = logging.getLogger(__name__)

# State constants for multi-step interactions
WAITING_RENAME = "waiting_rename"
WAITING_CAPTION = "waiting_caption"
WAITING_THUMBNAIL = "waiting_thumbnail"


# ---------------------------------------------------------------------------
#  File send callback (from search result buttons)
# ---------------------------------------------------------------------------
async def file_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle file button press from search results.

    Callback data format: file_{file_id_hash}
    """
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data

    if not data.startswith("file_"):
        return

    file_key = data[5:]  # strip "file_"
    await query.answer()

    # --- Force subscribe check ---
    fsub_result = await check_force_sub(context.bot, user_id)
    if fsub_result is not True:
        await query.message.reply_text(
            "📢 <b>Please join our channel to use this bot.</b>",
            parse_mode="HTML",
            reply_markup=fsub_result,
        )
        return

    # --- Token verification check ---
    from database.premium_db import is_premium
    is_premium_flag = await is_premium(user_id)

    if not is_premium_flag:
        verified = await is_verified(user_id)
        if not verified:
            verify_url = await generate_token(user_id)
            await query.message.reply_text(
                "🔐 <b>Verify to access files.</b>\n"
                "Click the button below, then come back and try again.",
                parse_mode="HTML",
                reply_markup=get_verify_keyboard(verify_url),
            )
            return

    # --- Fetch file from DB and send ---
    from database.files_db import get_file

    file_doc = await get_file(file_key)
    if not file_doc:
        await query.message.reply_text("❌ File not found in database.")
        return

    try:
        file_id = file_doc.get("file_id")
        file_name = file_doc.get("file_name", "file")
        file_type = file_doc.get("file_type", "document")
        caption = file_doc.get("caption", f"📁 {file_name}")

        # Get user's custom caption/thumbnail if set
        from database.users_db import get_user
        user_doc = await get_user(user_id)
        custom_caption = user_doc.get("caption") if user_doc else None
        custom_thumb = user_doc.get("thumbnail") if user_doc else None

        if custom_caption:
            caption = custom_caption.format(
                file_name=file_name,
                file_size=file_doc.get("file_size", ""),
            )

        # Check file_secure setting
        from database.settings_db import get_settings
        chat_settings = await get_settings(query.message.chat_id)
        protect = chat_settings.get("file_secure", False)

        # Build action buttons
        action_buttons = []
        stream_enabled = chat_settings.get("stream", False)
        if stream_enabled:
            action_buttons.append(
                InlineKeyboardButton("🖥️ Stream", callback_data=f"strm_{file_key}")
            )
        action_buttons.append(
            InlineKeyboardButton("📥 Download", callback_data=f"dl_{file_key}")
        )

        markup = InlineKeyboardMarkup([action_buttons]) if action_buttons else None

        send_kwargs = {
            "chat_id": user_id,
            "caption": caption,
            "parse_mode": "HTML",
            "protect_content": protect,
            "reply_markup": markup,
        }

        if file_type == "video":
            sent = await context.bot.send_video(video=file_id, thumbnail=custom_thumb, **send_kwargs)
        elif file_type == "audio":
            sent = await context.bot.send_audio(audio=file_id, thumbnail=custom_thumb, **send_kwargs)
        else:
            sent = await context.bot.send_document(
                document=file_id, thumbnail=custom_thumb, **send_kwargs
            )

        # Schedule auto-delete if enabled and in PM
        auto_del = chat_settings.get("auto_delete", True)
        if auto_del and query.message.chat.type == "private":
            await schedule_delete_with_warning(
                context, user_id, sent.message_id
            )

    except TelegramError as e:
        logger.error(f"Error sending file {file_key} to {user_id}: {e}")
        await query.message.reply_text(f"❌ Failed to send file: {e}")


# ---------------------------------------------------------------------------
#  Stream link callback
# ---------------------------------------------------------------------------
async def stream_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate a stream URL for the file."""
    query = update.callback_query
    data = query.data

    if not data.startswith("strm_"):
        return

    file_key = data[5:]
    await query.answer()

    from database.files_db import get_file
    file_doc = await get_file(file_key)

    if not file_doc:
        await query.message.reply_text("❌ File not found.")
        return

    stream_base = getattr(Config, "STREAM_URL", "https://stream.example.com")
    file_name = file_doc.get("file_name", "file")
    stream_url = f"{stream_base}/watch/{file_key}/{file_name}"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🖥️ Watch Online", url=stream_url)],
    ])

    await query.message.reply_text(
        f"🖥️ <b>Stream Link</b>\n\n"
        f"📁 {file_name}\n"
        f"🔗 <a href='{stream_url}'>Click to stream</a>",
        parse_mode="HTML",
        reply_markup=keyboard,
        disable_web_page_preview=True,
    )


# ---------------------------------------------------------------------------
#  Download callback (direct send)
# ---------------------------------------------------------------------------
async def download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Direct file send (download button)."""
    query = update.callback_query
    data = query.data

    if not data.startswith("dl_"):
        return

    file_key = data[3:]
    user_id = query.from_user.id
    await query.answer("📥 Sending file...")

    from database.files_db import get_file
    file_doc = await get_file(file_key)

    if not file_doc:
        await query.message.reply_text("❌ File not found.")
        return

    try:
        file_id = file_doc.get("file_id")
        file_name = file_doc.get("file_name", "file")

        sent = await context.bot.send_document(
            chat_id=user_id,
            document=file_id,
            caption=f"📁 {file_name}",
            parse_mode="HTML",
        )

        # Auto-delete in PM
        from database.settings_db import get_settings
        chat_settings = await get_settings(query.message.chat_id)
        if chat_settings.get("auto_delete", True) and query.message.chat.type == "private":
            await schedule_delete_with_warning(context, user_id, sent.message_id)

    except TelegramError as e:
        logger.error(f"Download send error: {e}")
        await query.message.reply_text(f"❌ Failed: {e}")


# ---------------------------------------------------------------------------
#  /rename — rename file
# ---------------------------------------------------------------------------
async def rename_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start file rename flow. Usage: reply to a file with /rename or /rename <new_name>."""
    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ Reply to a file message with /rename <new_name>")
        return

    reply = update.message.reply_to_message
    file_obj = reply.document or reply.video or reply.audio
    if not file_obj:
        await update.message.reply_text("❌ No file found in the replied message.")
        return

    if context.args:
        # Immediate rename
        new_name = " ".join(context.args)
        await _do_rename(update, context, reply, file_obj, new_name)
    else:
        # Ask for new name
        context.user_data["rename_state"] = WAITING_RENAME
        context.user_data["rename_msg_id"] = reply.message_id
        context.user_data["rename_file_id"] = file_obj.file_id
        context.user_data["rename_file_type"] = (
            "video" if reply.video else "audio" if reply.audio else "document"
        )
        await update.message.reply_text(
            "📝 Send the new file name (with extension):"
        )


async def _do_rename(update, context, reply_msg, file_obj, new_name):
    """Perform the rename: download and re-upload with new name."""
    status = await update.message.reply_text("⏳ Renaming file...")

    try:
        tg_file = await context.bot.get_file(file_obj.file_id)
        file_bytes = await tg_file.download_as_bytearray()

        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=bytes(file_bytes),
            filename=new_name,
            caption=f"📁 Renamed: {new_name}",
        )
        await status.edit_text(f"✅ File renamed to: {new_name}")
    except TelegramError as e:
        await status.edit_text(f"❌ Rename failed: {e}")


# ---------------------------------------------------------------------------
#  /setcaption — set custom caption
# ---------------------------------------------------------------------------
async def setcaption_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set custom caption for files. Usage: /setcaption <caption_template>"""
    user_id = update.effective_user.id

    if context.args:
        caption = " ".join(context.args)
        from database.users_db import update_user_setting
        await update_user_setting(user_id, "caption", caption)
        await update.message.reply_text(
            f"✅ Caption set:\n<code>{caption}</code>\n\n"
            f"Available variables: {{file_name}}, {{file_size}}",
            parse_mode="HTML",
        )
    else:
        context.user_data["rename_state"] = WAITING_CAPTION
        await update.message.reply_text(
            "📝 Send your custom caption template.\n\n"
            "Available variables:\n"
            "<code>{file_name}</code> — File name\n"
            "<code>{file_size}</code> — File size\n\n"
            "Send /removecaption to remove custom caption.",
            parse_mode="HTML",
        )


async def removecaption_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove custom caption."""
    user_id = update.effective_user.id
    from database.users_db import update_user_setting
    await update_user_setting(user_id, "caption", None)
    await update.message.reply_text("✅ Custom caption removed.")


# ---------------------------------------------------------------------------
#  /setthumb — set custom thumbnail
# ---------------------------------------------------------------------------
async def setthumb_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set custom thumbnail. Reply to a photo or send /setthumb then upload."""
    user_id = update.effective_user.id

    if update.message.reply_to_message and update.message.reply_to_message.photo:
        photo = update.message.reply_to_message.photo[-1]  # highest res
        from database.users_db import update_user_setting
        await update_user_setting(user_id, "thumbnail", photo.file_id)
        await update.message.reply_text("✅ Custom thumbnail set!")
    else:
        context.user_data["rename_state"] = WAITING_THUMBNAIL
        await update.message.reply_text(
            "🖼️ Send a photo to use as thumbnail.\n"
            "Send /removethumb to remove custom thumbnail."
        )


async def removethumb_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove custom thumbnail."""
    user_id = update.effective_user.id
    from database.users_db import update_user_setting
    await update_user_setting(user_id, "thumbnail", None)
    await update.message.reply_text("✅ Custom thumbnail removed.")


# ---------------------------------------------------------------------------
#  Multi-step input handler
# ---------------------------------------------------------------------------
async def user_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user text/photo input during multi-step flows (rename, caption, thumb)."""
    state = context.user_data.get("rename_state")

    if not state:
        return  # Not in any flow

    user_id = update.effective_user.id

    if state == WAITING_RENAME:
        new_name = update.message.text
        if not new_name:
            await update.message.reply_text("❌ Please send a valid file name.")
            return

        file_id = context.user_data.get("rename_file_id")
        if not file_id:
            await update.message.reply_text("❌ Session expired. Please try /rename again.")
            context.user_data.pop("rename_state", None)
            return

        status = await update.message.reply_text("⏳ Renaming file...")
        try:
            tg_file = await context.bot.get_file(file_id)
            file_bytes = await tg_file.download_as_bytearray()

            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=bytes(file_bytes),
                filename=new_name,
                caption=f"📁 Renamed: {new_name}",
            )
            await status.edit_text(f"✅ File renamed to: {new_name}")
        except TelegramError as e:
            await status.edit_text(f"❌ Rename failed: {e}")

        context.user_data.pop("rename_state", None)
        context.user_data.pop("rename_file_id", None)
        context.user_data.pop("rename_msg_id", None)
        context.user_data.pop("rename_file_type", None)

    elif state == WAITING_CAPTION:
        caption = update.message.text
        if not caption:
            await update.message.reply_text("❌ Please send a valid caption.")
            return

        from database.users_db import update_user_setting
        await update_user_setting(user_id, "caption", caption)
        await update.message.reply_text(
            f"✅ Caption set:\n<code>{caption}</code>", parse_mode="HTML"
        )
        context.user_data.pop("rename_state", None)

    elif state == WAITING_THUMBNAIL:
        if not update.message.photo:
            await update.message.reply_text("❌ Please send a photo.")
            return

        photo = update.message.photo[-1]
        from database.users_db import update_user_setting
        await update_user_setting(user_id, "thumbnail", photo.file_id)
        await update.message.reply_text("✅ Custom thumbnail set!")
        context.user_data.pop("rename_state", None)


# ---------------------------------------------------------------------------
#  register
# ---------------------------------------------------------------------------
def register(app):
    """Register file action handlers."""
    # File button callback from search results
    app.add_handler(CallbackQueryHandler(file_callback, pattern=r"^file_"))
    # Stream and download
    app.add_handler(CallbackQueryHandler(stream_callback, pattern=r"^strm_"))
    app.add_handler(CallbackQueryHandler(download_callback, pattern=r"^dl_"))

    # Rename, caption, thumbnail commands
    app.add_handler(CommandHandler("rename", rename_cmd))
    app.add_handler(CommandHandler("setcaption", setcaption_cmd))
    app.add_handler(CommandHandler("removecaption", removecaption_cmd))
    app.add_handler(CommandHandler("setthumb", setthumb_cmd))
    app.add_handler(CommandHandler("removethumb", removethumb_cmd))

    # Multi-step input handler — text for rename/caption
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
            user_input_handler,
        ),
        group=5,  # Lower priority so it doesn't intercept search queries
    )

    # Photo handler for thumbnail
    app.add_handler(
        MessageHandler(
            filters.PHOTO & filters.ChatType.PRIVATE,
            user_input_handler,
        ),
        group=5,
    )
