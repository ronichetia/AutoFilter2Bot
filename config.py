import os
from dotenv import load_dotenv

load_dotenv()


def _bool(val: str | None) -> bool:
    """Parse a boolean from env var string."""
    if val is None:
        return False
    return val.strip().lower() in ("true", "1", "yes")


def _int_list(val: str | None) -> list[int]:
    """Parse a space-separated list of ints from env var."""
    if not val:
        return []
    return [int(x) for x in val.strip().split() if x]


def _str_list(val: str | None) -> list[str]:
    """Parse a space-separated list of strings from env var."""
    if not val:
        return []
    return [x for x in val.strip().split() if x]


class Config:
    # Telegram
    BOT_TOKEN: str = os.environ.get("BOT_TOKEN", "")
    API_ID: int = int(os.environ.get("API_ID", "0"))
    API_HASH: str = os.environ.get("API_HASH", "")

    # MongoDB
    MONGO_URI: str = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
    DATABASE_NAME: str = os.environ.get("DATABASE_NAME", "autofilterbot")

    # Admin / channels
    ADMIN_IDS: list[int] = _int_list(os.environ.get("ADMIN_IDS"))
    LOG_CHANNEL: int = int(os.environ.get("LOG_CHANNEL", "0"))
    FILE_CHANNELS: list[int] = _int_list(os.environ.get("FILE_CHANNELS"))
    AUTH_CHANNEL: int | None = (
        int(os.environ["AUTH_CHANNEL"]) if os.environ.get("AUTH_CHANNEL") else None
    )

    # Links
    SUPPORT_CHAT: str = os.environ.get("SUPPORT_CHAT", "")
    OWNER_LINK: str = os.environ.get("OWNER_LINK", "")
    PICS: list[str] = _str_list(os.environ.get("PICS"))

    # Feature toggles (bool)
    CLONE_MODE: bool = _bool(os.environ.get("CLONE_MODE"))
    MULTIPLE_DB: bool = _bool(os.environ.get("MULTIPLE_DB"))
    PREMIUM_MODE: bool = _bool(os.environ.get("PREMIUM_MODE"))
    REFERRAL_MODE: bool = _bool(os.environ.get("REFERRAL_MODE"))
    PM_SEARCH: bool = _bool(os.environ.get("PM_SEARCH"))
    SPELL_CHECK: bool = _bool(os.environ.get("SPELL_CHECK"))
    AUTO_DELETE: bool = _bool(os.environ.get("AUTO_DELETE"))
    FORCE_SUB: bool = _bool(os.environ.get("FORCE_SUB"))
    STREAM_MODE: bool = _bool(os.environ.get("STREAM_MODE"))
    URL_SHORTENER_MODE: bool = _bool(os.environ.get("URL_SHORTENER_MODE"))
    TOKEN_VERIFY: bool = _bool(os.environ.get("TOKEN_VERIFY"))

    # Shortlink
    SHORTLINK_URL: str = os.environ.get("SHORTLINK_URL", "")
    SHORTLINK_API: str = os.environ.get("SHORTLINK_API", "")

    # Referral
    REFERRAL_COUNT: int = int(os.environ.get("REFERRAL_COUNT", "20"))
    REFERRAL_PREMIUM_TIME: str = os.environ.get("REFERRAL_PREMIUM_TIME", "1month")

    # Auto-delete time in seconds
    AUTO_DELETE_TIME: int = int(os.environ.get("AUTO_DELETE_TIME", "300"))

    # Health server port
    PORT: int = int(os.environ.get("PORT", "8080"))

    @staticmethod
    def is_admin(user_id: int) -> bool:
        """Check if a user ID is in the admin list."""
        return user_id in Config.ADMIN_IDS
