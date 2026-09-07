from database.db_client import db

col = db["filters"]


async def add_filter(
    chat_id: int, trigger: str, content: str, reply_markup: dict | None
) -> None:
    """Add or update a custom text filter for a chat."""
    await col.update_one(
        {"chat_id": chat_id, "trigger": trigger},
        {
            "$set": {
                "chat_id": chat_id,
                "trigger": trigger,
                "content": content,
                "reply_markup": reply_markup,
            }
        },
        upsert=True,
    )


async def get_filter(chat_id: int, trigger: str) -> dict | None:
    """Get a specific filter by chat and trigger."""
    return await col.find_one({"chat_id": chat_id, "trigger": trigger})


async def get_all_filters(chat_id: int) -> list[dict]:
    """Get all filters for a chat."""
    cursor = col.find({"chat_id": chat_id})
    return await cursor.to_list(length=None)


async def delete_filter(chat_id: int, trigger: str) -> None:
    """Delete a specific filter."""
    await col.delete_one({"chat_id": chat_id, "trigger": trigger})


async def delete_all_filters(chat_id: int) -> None:
    """Delete all filters for a chat."""
    await col.delete_many({"chat_id": chat_id})


async def count_filters(chat_id: int) -> int:
    """Count filters for a chat."""
    return await col.count_documents({"chat_id": chat_id})
