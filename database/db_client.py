from motor.motor_asyncio import AsyncIOMotorClient
from config import Config

motor_client = AsyncIOMotorClient(Config.MONGO_URI)
db = motor_client[Config.DATABASE_NAME]


async def init_db() -> None:
    """Ping the MongoDB server to verify the connection."""
    await motor_client.admin.command("ping")
    print(f"[DATABASE] Connected to MongoDB — database: {Config.DATABASE_NAME}")
