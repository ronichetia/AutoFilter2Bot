from database.db_client import db

col = db["connections"]


async def add_connection(user_id: int, chat_id: int, group_name: str = "") -> None:
    """Add or update a connection, setting it as active."""
    # Deactivate all existing connections for this user
    await col.update_many(
        {"user_id": user_id},
        {"$set": {"active": False}},
    )
    # Upsert the new connection as active
    await col.update_one(
        {"user_id": user_id, "group_id": chat_id},
        {"$set": {
            "user_id": user_id,
            "group_id": chat_id,
            "group_name": group_name,
            "active": True,
        }},
        upsert=True,
    )


async def get_active_connection(user_id: int) -> dict | None:
    """Get the currently active connection for a user."""
    return await col.find_one({"user_id": user_id, "active": True})


async def get_all_connections(user_id: int) -> list[dict]:
    """Get all connections for a user."""
    cursor = col.find({"user_id": user_id})
    return await cursor.to_list(length=None)


async def get_connections(user_id: int) -> list[dict]:
    """Alias for get_all_connections."""
    return await get_all_connections(user_id)


async def delete_connection(user_id: int, chat_id: int = None) -> None:
    """Remove a connection. If chat_id is None, remove the active one."""
    if chat_id is not None:
        await col.delete_one({"user_id": user_id, "group_id": chat_id})
    else:
        await col.delete_one({"user_id": user_id, "active": True})


async def is_connected(user_id: int, chat_id: int = None) -> bool:
    """Check if a user has an active connection (optionally to a specific chat)."""
    query = {"user_id": user_id, "active": True}
    if chat_id is not None:
        query["group_id"] = chat_id
    doc = await col.find_one(query)
    return doc is not None
