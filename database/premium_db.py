from datetime import datetime
from database.db_client import db

col = db["premium"]


async def add_premium(user_id: int, expiry_date: datetime, plan_name: str) -> None:
    """Add or update a premium user."""
    await col.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "user_id": user_id,
                "expiry_date": expiry_date,
                "plan_name": plan_name,
            }
        },
        upsert=True,
    )


async def get_premium(user_id: int) -> dict | None:
    """Get premium info for a user."""
    return await col.find_one({"user_id": user_id})


async def is_premium(user_id: int) -> bool:
    """Check if a user's premium is currently active (expiry in the future)."""
    doc = await col.find_one({"user_id": user_id})
    if doc and doc.get("expiry_date"):
        return doc["expiry_date"] > datetime.utcnow()
    return False


async def remove_premium(user_id: int) -> None:
    """Remove premium status from a user."""
    await col.delete_one({"user_id": user_id})


async def get_all_premium():
    """Return a cursor over all premium users."""
    return col.find({})


async def count_premium() -> int:
    """Count total premium users."""
    return await col.count_documents({})
