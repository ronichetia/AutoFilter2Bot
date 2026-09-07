"""Utility functions for AutoFilterBot."""

import re
import math
import difflib
import logging
import aiohttp

logger = logging.getLogger(__name__)


def parse_file_info(filename: str) -> dict:
    """Extract quality, language, season, episode, year from filename."""
    info = {
        "quality": None,
        "language": None,
        "season": None,
        "episode": None,
        "year": None,
    }

    # Quality patterns
    quality_patterns = [
        r"(2160p|4[Kk]|UHD)",
        r"(1080p|FHD|Full\s*HD)",
        r"(720p|HD)",
        r"(480p|SD)",
        r"(360p)",
        r"(HDRip|WEB-?DL|WEBRip|BluRay|BRRip|DVDRip|HDTV|HDCam|CAMRip|PreDVD)",
    ]
    for pattern in quality_patterns:
        match = re.search(pattern, filename, re.IGNORECASE)
        if match:
            info["quality"] = match.group(1)
            break

    # Language patterns
    lang_patterns = [
        r"\b(Hindi|English|Tamil|Telugu|Malayalam|Kannada|Bengali|Marathi|Gujarati)\b",
        r"\b(Hin|Eng|Tam|Tel|Mal|Kan)\b",
        r"\b(Dual\s*Audio|Multi\s*Audio)\b",
    ]
    for pattern in lang_patterns:
        match = re.search(pattern, filename, re.IGNORECASE)
        if match:
            info["language"] = match.group(1)
            break

    # Season and Episode
    se_match = re.search(r"S(\d{1,3})[\s._-]*E(\d{1,3})", filename, re.IGNORECASE)
    if se_match:
        info["season"] = int(se_match.group(1))
        info["episode"] = int(se_match.group(2))
    else:
        s_match = re.search(r"(?:Season|S)\s*(\d{1,3})", filename, re.IGNORECASE)
        if s_match:
            info["season"] = int(s_match.group(1))
        e_match = re.search(r"(?:Episode|Ep|E)\s*(\d{1,3})", filename, re.IGNORECASE)
        if e_match:
            info["episode"] = int(e_match.group(1))

    # Year
    year_match = re.search(r"[\(\[\s]?((?:19|20)\d{2})[\)\]\s]?", filename)
    if year_match:
        info["year"] = int(year_match.group(1))

    return info


def get_size(size_bytes: int) -> str:
    """Convert bytes to human readable file size."""
    if size_bytes == 0:
        return "0 B"
    size_names = ("B", "KB", "MB", "GB", "TB", "PB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_names[i]}"


# Alias
humanbytes = get_size


async def get_shortlink(url: str, api: str = None, api_key: str = None) -> str:
    """Generate short link using configured shortener API.

    Args:
        url: The URL to shorten.
        api: The shortener API base URL (e.g., 'https://short.example.com/api').
        api_key: API key for the shortener service.

    Returns:
        Shortened URL string, or the original URL on failure.
    """
    if not api or not api_key:
        return url

    try:
        async with aiohttp.ClientSession() as session:
            params = {"api": api_key, "url": url}
            async with session.get(api, params=params, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("status") == "success":
                        return data.get("shortenedUrl", url)
                    # Some APIs return the link differently
                    if "shortenedUrl" in data:
                        return data["shortenedUrl"]
                    if "link" in data:
                        return data["link"]
    except Exception as e:
        logger.warning(f"Shortlink generation failed: {e}")

    return url


def spell_check(query: str, file_names: list[str], n: int = 5, cutoff: float = 0.4) -> list[str]:
    """Fuzzy spell check using difflib. Returns close match suggestions.

    Args:
        query: The search query to match against.
        file_names: List of file names to match from.
        n: Maximum number of suggestions.
        cutoff: Similarity threshold (0.0 to 1.0).

    Returns:
        List of suggested file names sorted by relevance.
    """
    query_lower = query.lower()

    # Clean file names for comparison
    cleaned = {}
    for name in file_names:
        cleaned[clean_file_name(name).lower()] = name

    # Get close matches
    matches = difflib.get_close_matches(
        query_lower, list(cleaned.keys()), n=n, cutoff=cutoff
    )

    # Return original (uncleaned) names
    return [cleaned[m] for m in matches]


def clean_file_name(name: str) -> str:
    """Clean special characters from filename for readability."""
    # Remove file extension
    name = re.sub(r"\.[a-zA-Z0-9]{2,4}$", "", name)
    # Replace common separators with spaces
    name = re.sub(r"[._\-\[\](){}]", " ", name)
    # Remove excess whitespace
    name = re.sub(r"\s+", " ", name).strip()
    return name
