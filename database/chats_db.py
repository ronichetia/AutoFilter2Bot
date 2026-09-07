from database.db_client import db

col = db["chats"]


async def add_chat(chat_id: int, title: str) -> None:
    """Add or update a chat/group."""
    await col.update_one(
        {"chat_id": chat_id},
        {"$set": {"chat_id": chat_id, "title": title}},
        upsert=True,
    )


async def get_chat(chat_id: int) -> dict | None:
    """Get a chat document."""
    return await col.find_one({"chat_id": chat_id})


async def get_all_chats():
    """Return a cursor over all chats."""
    return col.find({})


async def count_chats() -> int:
    """Count total chats."""
    return await col.count_documents({})


async def delete_chat(chat_id: int) -> None:
    """Delete a chat."""
    await col.delete_one({"chat_id": chat_id})


async def is_chat_disabled(chat_id: int) -> bool:
    """Check if a chat is disabled."""
    chat = await col.find_one({"chat_id": chat_id})
    if chat:
        return chat.get("disabled", False)
    return False


async def disable_chat(chat_id: int) -> None:
    """Disable a chat."""
    await col.update_one(
        {"chat_id": chat_id},
        {"$set": {"disabled": True}},
        upsert=True,
    )


async def enable_chat(chat_id: int) -> None:
    """Enable a chat."""
    await col.update_one(
        {"chat_id": chat_id},
        {"$set": {"disabled": False}},
        upsert=True,
    )
