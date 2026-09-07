from database.db_client import db

col = db["global_filters"]


async def add_gfilter(
    trigger: str, reply_text: str = "", reply_message_id: int | None = None,
    content: str | None = None, reply_markup: dict | None = None,
) -> None:
    """Add or update a global filter."""
    await col.update_one(
        {"trigger": trigger},
        {
            "$set": {
                "trigger": trigger,
                "reply_text": reply_text,
                "reply_message_id": reply_message_id,
                "content": content,
                "reply_markup": reply_markup,
            }
        },
        upsert=True,
    )


async def get_gfilter(trigger: str) -> dict | None:
    """Get a global filter by trigger."""
    return await col.find_one({"trigger": trigger})


async def get_all_gfilters() -> list[dict]:
    """Get all global filters."""
    cursor = col.find({})
    return await cursor.to_list(length=None)


async def delete_gfilter(trigger: str) -> bool:
    """Delete a global filter. Returns True if something was deleted."""
    result = await col.delete_one({"trigger": trigger})
    return result.deleted_count > 0


async def delete_all_gfilters() -> None:
    """Delete all global filters."""
    await col.delete_many({})


async def count_gfilters() -> int:
    """Count total global filters."""
    return await col.count_documents({})
