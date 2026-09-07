from database.db_client import db

col = db["users"]


async def add_user(user_id: int, name: str) -> None:
    """Add or update a user."""
    await col.update_one(
        {"user_id": user_id},
        {"$set": {"user_id": user_id, "name": name}},
        upsert=True,
    )


async def is_user_exist(user_id: int) -> bool:
    """Check if a user exists in the database."""
    doc = await col.find_one({"user_id": user_id})
    return doc is not None


async def get_user(user_id: int) -> dict | None:
    """Get a user document."""
    return await col.find_one({"user_id": user_id})


async def get_all_users():
    """Return a cursor over all users."""
    return col.find({})


async def count_users() -> int:
    """Count total users."""
    return await col.count_documents({})


async def delete_user(user_id: int) -> None:
    """Delete a user."""
    await col.delete_one({"user_id": user_id})


async def is_user_banned(user_id: int) -> bool:
    """Check if a user is banned."""
    user = await col.find_one({"user_id": user_id})
    if user:
        return user.get("banned", False)
    return False


async def ban_user(user_id: int) -> None:
    """Ban a user."""
    await col.update_one(
        {"user_id": user_id},
        {"$set": {"banned": True}},
        upsert=True,
    )


async def unban_user(user_id: int) -> None:
    """Unban a user."""
    await col.update_one(
        {"user_id": user_id},
        {"$set": {"banned": False}},
        upsert=True,
    )


async def get_banned_users() -> list[dict]:
    """Return all banned users."""
    cursor = col.find({"banned": True})
    return await cursor.to_list(length=None)


async def update_user_setting(user_id: int, key: str, value) -> None:
    """Update a single user-level setting (e.g. caption, thumbnail)."""
    await col.update_one(
        {"user_id": user_id},
        {"$set": {key: value}},
        upsert=True,
    )


async def get_referral_count(user_id: int) -> int:
    """Proxy to referral_db.get_referral_count (convenience import)."""
    from database.referral_db import get_referral_count as _get
    return await _get(user_id)
