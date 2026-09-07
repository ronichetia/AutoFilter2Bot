from database.db_client import db

col = db["settings"]

DEFAULT_SETTINGS: dict = {
    "imdb": True,
    "spell_check": True,
    "welcome": True,
    "auto_delete": False,
    "auto_filter": True,
    "button_mode": "single",
    "file_secure": False,
    "pm_search": False,
    "shortlink": False,
    "stream": False,
    "url_shortener": False,
    "max_buttons": 10,
    "max_pages": 5,
    "template": None,
}


async def get_settings(chat_id: int) -> dict:
    """Return the settings for a chat, falling back to defaults."""
    doc = await col.find_one({"chat_id": chat_id})
    if doc:
        settings = {**DEFAULT_SETTINGS, **doc}
        settings.pop("_id", None)
        return settings
    return {"chat_id": chat_id, **DEFAULT_SETTINGS}


async def update_setting(chat_id: int, key: str, value) -> None:
    """Update a single setting key for a chat."""
    await col.update_one(
        {"chat_id": chat_id},
        {"$set": {key: value}},
        upsert=True,
    )


async def reset_settings(chat_id: int) -> None:
    """Reset a chat's settings to defaults."""
    await col.update_one(
        {"chat_id": chat_id},
        {"$set": {**DEFAULT_SETTINGS, "chat_id": chat_id}},
        upsert=True,
    )
