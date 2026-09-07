"""Token verification handler for AutoFilterBot."""

import time
import uuid
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackQueryHandler, ContextTypes

from config import Config

logger = logging.getLogger(__name__)

# In-memory token store: {user_id: {"token": str, "expires": float}}
_verified_users: dict[int, dict] = {}

# Default verification duration in hours
VERIFY_DURATION_HOURS = getattr(Config, "TOKEN_VERIFY_HOURS", 12)


async def is_verified(user_id: int) -> bool:
    """Check if user has a valid (non-expired) token.

    Args:
        user_id: Telegram user ID.

    Returns:
        True if verified and not expired, False otherwise.
    """
    entry = _verified_users.get(user_id)
    if not entry:
        return False

    if time.time() > entry["expires"]:
        # Token expired, clean up
        _verified_users.pop(user_id, None)
        return False

    return True


async def generate_token(user_id: int) -> str:
    """Generate a verification token and link for the user.

    Args:
        user_id: Telegram user ID.

    Returns:
        Verification URL string.
    """
    token = uuid.uuid4().hex[:16]
    bot_username = getattr(Config, "BOT_USERNAME", "AutoFilterBot")

    # Store token with expiry
    _verified_users[user_id] = {
        "token": token,
        "expires": time.time() + (VERIFY_DURATION_HOURS * 3600),
    }

    # Deep link: user clicks this, bot receives /start verify_{token}_{user_id}
    verify_url = f"https://t.me/{bot_username}?start=verify_{token}_{user_id}"
    return verify_url


async def verify_token(user_id: int, token: str) -> bool:
    """Verify a token string for a user.

    Args:
        user_id: Telegram user ID.
        token: Token string to verify.

    Returns:
        True if token matches and is not expired.
    """
    entry = _verified_users.get(user_id)
    if not entry:
        return False

    if entry["token"] != token:
        return False

    if time.time() > entry["expires"]:
        _verified_users.pop(user_id, None)
        return False

    return True


def get_verify_keyboard(verify_url: str) -> InlineKeyboardMarkup:
    """Build an inline keyboard with the verification link."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔐 Verify", url=verify_url)],
    ])


async def token_status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /verify command — show token status."""
    user_id = update.effective_user.id

    if await is_verified(user_id):
        entry = _verified_users[user_id]
        remaining = int(entry["expires"] - time.time())
        hours, remainder = divmod(remaining, 3600)
        minutes, _ = divmod(remainder, 60)
        await update.message.reply_text(
            f"✅ You are verified.\n"
            f"⏳ Expires in: {hours}h {minutes}m"
        )
    else:
        verify_url = await generate_token(user_id)
        await update.message.reply_text(
            "❌ You are not verified or your token has expired.\n"
            "Click the button below to verify:",
            reply_markup=get_verify_keyboard(verify_url),
        )


def register(app):
    """Register token verification handlers."""
    app.add_handler(CommandHandler("verify", token_status_cmd))
