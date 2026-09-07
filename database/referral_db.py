from datetime import datetime
from database.db_client import db

col = db["referrals"]


async def add_referral(user_id: int, referred_by: int) -> None:
    """Record that user_id was referred by referred_by."""
    await col.insert_one(
        {
            "user_id": user_id,
            "referred_by": referred_by,
            "date": datetime.utcnow(),
        }
    )


async def get_referral_count(user_id: int) -> int:
    """Count how many users were referred by user_id."""
    return await col.count_documents({"referred_by": user_id})


async def get_referrals(user_id: int) -> list[dict]:
    """Get all referral records where user_id is the referrer."""
    cursor = col.find({"referred_by": user_id})
    return await cursor.to_list(length=None)
