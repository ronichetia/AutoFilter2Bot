from motor.motor_asyncio import AsyncIOMotorClient
from config import Config

motor_client = AsyncIOMotorClient(Config.MONGO_URI)
db = motor_client[Config.DATABASE_NAME]


async def init_db() -> None:
    """Ping MongoDB and create indexes for performance."""
    await motor_client.admin.command("ping")
    print(f"[DATABASE] Connected to MongoDB — database: {Config.DATABASE_NAME}")

    # Ensure indexes on the files collection
    files_col = db["files"]
    await files_col.create_index("file_id", unique=True)
    await files_col.create_index("file_ref")
    await files_col.create_index([("file_name", "text")])  # text search index
    await files_col.create_index("chat_id")
    print("[DATABASE] Indexes ensured on 'files' collection")

    # Backfill file_ref for any docs that lack it
    import hashlib
    missing = files_col.find({"file_ref": {"$exists": False}}, {"file_id": 1})
    backfill_count = 0
    async for doc in missing:
        fid = doc.get("file_id", "")
        ref = hashlib.md5(fid.encode()).hexdigest()[:12]
        await files_col.update_one({"_id": doc["_id"]}, {"$set": {"file_ref": ref}})
        backfill_count += 1
    if backfill_count:
        print(f"[DATABASE] Backfilled file_ref on {backfill_count} docs")
