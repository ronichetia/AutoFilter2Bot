from database.db_client import db

col = db["global_filters"]


async def add_gfilter(trigger: str, content: str, reply_markup: dict | None) -> None:
    """Add or update a global filter."""
    await col.update_one(
        {"trigger": trigger},
        {
            "$set": {
                "trigger": trigger,
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


async def delete_gfilter(trigger: str) -> None:
    """Delete a global filter."""
    await col.delete_one({"trigger": trigger})


async def delete_all_gfilters() -> None:
    """Delete all global filters."""
    await col.delete_many({})


async def count_gfilters() -> int:
    """Count total global filters."""
    return await col.count_documents({})
