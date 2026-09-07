import re
import difflib
from database.db_client import db

col = db["files"]


async def save_file(
    file_id: str,
    file_name: str,
    file_size: int,
    file_type: str,
    caption: str | None,
    chat_id: int,
) -> None:
    """Insert or update a file document keyed by file_id."""
    await col.update_one(
        {"file_id": file_id},
        {
            "$set": {
                "file_id": file_id,
                "file_name": file_name,
                "file_size": file_size,
                "file_type": file_type,
                "caption": caption,
                "chat_id": chat_id,
            }
        },
        upsert=True,
    )


async def search_files(query: str, max_results: int = 10) -> list[dict]:
    """Regex search on file_name (case-insensitive). Returns up to max_results."""
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    cursor = col.find({"file_name": {"$regex": pattern}}).limit(max_results)
    return await cursor.to_list(length=max_results)


async def fuzzy_search(query: str, max_results: int = 10) -> list[dict]:
    """Fetch all file names and rank them by SequenceMatcher ratio (≥0.4)."""
    cursor = col.find({}, {"file_id": 1, "file_name": 1, "file_size": 1, "file_type": 1, "caption": 1, "chat_id": 1})
    results: list[tuple[float, dict]] = []
    async for doc in cursor:
        name = doc.get("file_name", "")
        ratio = difflib.SequenceMatcher(None, query.lower(), name.lower()).ratio()
        if ratio >= 0.4:
            results.append((ratio, doc))
    results.sort(key=lambda x: x[0], reverse=True)
    return [doc for _, doc in results[:max_results]]


async def get_file(file_id: str) -> dict | None:
    """Get a single file document by file_id."""
    return await col.find_one({"file_id": file_id})


async def delete_file(file_id: str) -> None:
    """Delete a single file by file_id."""
    await col.delete_one({"file_id": file_id})


async def delete_files_by_chat(chat_id: int) -> int:
    """Delete all files belonging to a chat. Returns deleted count."""
    result = await col.delete_many({"chat_id": chat_id})
    return result.deleted_count


async def count_files() -> int:
    """Return total number of indexed files."""
    return await col.count_documents({})


async def get_file_details(file_id: str) -> dict | None:
    """Return the full document for a file_id."""
    return await col.find_one({"file_id": file_id})
