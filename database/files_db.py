import re
import hashlib
import difflib
from database.db_client import db

col = db["files"]


def _make_ref(file_id: str) -> str:
    """Create a short (12-char) unique reference from a file_id for callback data."""
    return hashlib.md5(file_id.encode()).hexdigest()[:12]


async def save_file(
    file_id: str,
    file_name: str,
    file_size: int,
    file_type: str,
    caption: str | None,
    chat_id: int,
    message_id: int | None = None,
) -> None:
    """Insert or update a file document keyed by file_id."""
    doc = {
        "file_id": file_id,
        "file_ref": _make_ref(file_id),
        "file_name": file_name,
        "file_size": file_size,
        "file_type": file_type,
        "caption": caption,
        "chat_id": chat_id,
    }
    if message_id is not None:
        doc["message_id"] = message_id
    await col.update_one(
        {"file_id": file_id},
        {"$set": doc},
        upsert=True,
    )


async def search_files(
    query: str,
    max_results: int = 10,
    page: int = 0,
    per_page: int | None = None,
    fuzzy: bool = False,
) -> tuple[list[dict], int]:
    """Search files by name, returning ``(results_page, total_count)``.

    Exact regex search first; set *fuzzy=True* for SequenceMatcher fallback.
    """
    if per_page is not None:
        limit = per_page
    else:
        limit = max_results

    if fuzzy:
        all_results = await fuzzy_search(query, max_results=0)  # 0 = no cap
        total = len(all_results)
        start = page * limit
        return all_results[start : start + limit], total

    pattern = re.compile(re.escape(query), re.IGNORECASE)
    total = await col.count_documents({"file_name": {"$regex": pattern}})
    cursor = (
        col.find({"file_name": {"$regex": pattern}})
        .skip(page * limit)
        .limit(limit)
    )
    results = await cursor.to_list(length=limit)
    return results, total


async def fuzzy_search(query: str, max_results: int = 10) -> list[dict]:
    """Fetch all file names and rank by SequenceMatcher ratio (≥0.4)."""
    cursor = col.find(
        {},
        {
            "file_id": 1, "file_ref": 1, "file_name": 1,
            "file_size": 1, "file_type": 1, "caption": 1, "chat_id": 1,
        },
    )
    results: list[tuple[float, dict]] = []
    async for doc in cursor:
        name = doc.get("file_name", "")
        ratio = difflib.SequenceMatcher(None, query.lower(), name.lower()).ratio()
        if ratio >= 0.4:
            results.append((ratio, doc))
    results.sort(key=lambda x: x[0], reverse=True)
    if max_results:
        return [doc for _, doc in results[:max_results]]
    return [doc for _, doc in results]


async def get_file(file_ref: str) -> dict | None:
    """Get a file document by file_ref (short hash) or file_id."""
    # Try file_ref first (short callback key), then file_id (full key)
    doc = await col.find_one({"file_ref": file_ref})
    if doc:
        return doc
    return await col.find_one({"file_id": file_ref})


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
