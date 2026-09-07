import re
import logging
import math
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from config import Config
from database.files_db import search_files, _make_ref
from database.connections_db import get_active_connection

logger = logging.getLogger(__name__)

RESULTS_PER_PAGE = 10

# --- Filename parsing regex patterns ---

QUALITY_PATTERNS = re.compile(
    r"(2160p|4K|1080p|720p|480p|360p|240p|"
    r"HDRip|WEBRip|WEB-DL|WEBDL|BluRay|BRRip|BDRip|"
    r"DVDRip|DVDScr|HDTV|HDCam|HDTS|CAMRip|PreDVD|"
    r"HQ|HD|SD|UHD)",
    re.IGNORECASE,
)

LANGUAGE_PATTERNS = re.compile(
    r"\b(Hindi|English|Tamil|Telugu|Malayalam|Kannada|Bengali|"
    r"Marathi|Gujarati|Punjabi|Urdu|Korean|Japanese|Chinese|"
    r"French|German|Spanish|Italian|Portuguese|Russian|Arabic|"
    r"Dual[ .]?Audio|Multi[ .]?Audio|Hin|Eng|Tam|Tel|Mal)\b",
    re.IGNORECASE,
)

SEASON_PATTERN = re.compile(
    r"(?:S|Season\s?)(\d{1,3})", re.IGNORECASE
)

EPISODE_PATTERN = re.compile(
    r"(?:E|Ep(?:isode)?\s?)(\d{1,4})", re.IGNORECASE
)

YEAR_PATTERN = re.compile(
    r"[\(\[\s]((?:19|20)\d{2})[\)\]\s]"
)


def _parse_file_attributes(file_name: str) -> dict:
    """Extract quality, language, season, episode, year from filename."""
    attrs = {}
    q = QUALITY_PATTERNS.findall(file_name)
    if q:
        attrs["quality"] = list({x.upper() for x in q})
    l_ = LANGUAGE_PATTERNS.findall(file_name)
    if l_:
        attrs["language"] = list({x.capitalize() for x in l_})
    s = SEASON_PATTERN.findall(file_name)
    if s:
        attrs["season"] = list({f"S{x.zfill(2)}" for x in s})
    e = EPISODE_PATTERN.findall(file_name)
    if e:
        attrs["episode"] = list({f"E{x.zfill(2)}" for x in e})
    y = YEAR_PATTERN.findall(file_name)
    if y:
        attrs["year"] = list(set(y))
    return attrs


def _format_size(size_bytes: int) -> str:
    """Format file size to human readable."""
    if size_bytes <= 0:
        return "N/A"
    units = ["B", "KB", "MB", "GB"]
    i = 0
    size = float(size_bytes)
    while size >= 1024 and i < len(units) - 1:
        size /= 1024
        i += 1
    return f"{size:.1f} {units[i]}"


def _collect_filter_values(results: list) -> dict:
    """Collect unique quality/language/season/episode/year across all results."""
    combined = {
        "quality": set(),
        "language": set(),
        "season": set(),
        "episode": set(),
        "year": set(),
    }
    for f in results:
        attrs = _parse_file_attributes(f.get("file_name", ""))
        for key in combined:
            combined[key].update(attrs.get(key, []))
    # Only keep categories with multiple distinct values
    return {k: sorted(v) for k, v in combined.items() if len(v) > 1}


def _build_results_keyboard(
    results: list,
    page: int,
    total: int,
    query: str,
    active_filters: dict = None,
) -> InlineKeyboardMarkup:
    """Build inline keyboard with file results and pagination."""
    buttons = []

    for f in results:
        name = f.get("file_name", "Unknown")
        size = _format_size(f.get("file_size", 0))
        # Truncate name for button text (max ~50 chars)
        display = name[:45] + "…" if len(name) > 45 else name
        btn_text = f"📄 {display} [{size}]"
        # Use file_ref (short hash) for callback data — fits in 64 bytes
        fref = f.get("file_ref") or _make_ref(f.get("file_id", ""))
        cb_data = f"file_{fref}"
        buttons.append([InlineKeyboardButton(btn_text, callback_data=cb_data)])

    # Pagination row
    total_pages = max(1, math.ceil(total / RESULTS_PER_PAGE))
    nav_row = []

    # Encode query for callback (truncate to fit 64 byte limit)
    q_short = query[:20]
    if page > 0:
        nav_row.append(
            InlineKeyboardButton("⬅️ Prev", callback_data=f"pg#{page - 1}#{q_short}")
        )
    nav_row.append(
        InlineKeyboardButton(f"📃 {page + 1}/{total_pages}", callback_data="noop")
    )
    if (page + 1) * RESULTS_PER_PAGE < total:
        nav_row.append(
            InlineKeyboardButton("Next ➡️", callback_data=f"pg#{page + 1}#{q_short}")
        )

    if nav_row:
        buttons.append(nav_row)

    # Close button
    buttons.append([InlineKeyboardButton("❌ Close", callback_data="close")])

    return InlineKeyboardMarkup(buttons)


def _build_filter_buttons(
    filter_values: dict, query: str
) -> list:
    """Build filter category buttons (quality, language, etc.)."""
    rows = []
    q_short = query[:15]

    for category, values in filter_values.items():
        cat_buttons = []
        emoji_map = {
            "quality": "🎬",
            "language": "🌐",
            "season": "📺",
            "episode": "🎞",
            "year": "📅",
        }
        emoji = emoji_map.get(category, "🔹")
        for val in values[:6]:  # Max 6 per category
            cb_data = f"fl#{category[:3]}#{val[:10]}#{q_short}"
            cat_buttons.append(InlineKeyboardButton(f"{emoji} {val}", callback_data=cb_data))
        # Arrange 3 per row
        for i in range(0, len(cat_buttons), 3):
            rows.append(cat_buttons[i : i + 3])

    return rows


async def group_search_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages in groups — auto-filter search."""
    message = update.effective_message
    query = message.text.strip()

    if not query or len(query) < 2:
        return

    chat_id = update.effective_chat.id

    # Search files DB — exact regex first
    results, total = await search_files(query=query, page=0, per_page=RESULTS_PER_PAGE)

    spell_suggestion = None
    if not results:
        # Try fuzzy search
        results, total = await search_files(
            query=query, page=0, per_page=RESULTS_PER_PAGE, fuzzy=True
        )
        if results:
            spell_suggestion = query

    if not results:
        return  # Silently ignore if no results

    # Collect filter values
    # For filters, we need a bigger sample
    all_results_for_filters, _ = await search_files(
        query=query, page=0, per_page=100
    )
    filter_values = _collect_filter_values(all_results_for_filters)

    # Build response
    text = f"<b>🔍 Results for:</b> <i>{query}</i>\n"
    text += f"<b>📁 Found:</b> {total} files\n"

    if spell_suggestion:
        text += f"\n💡 <i>Showing fuzzy results. Did you mean something else?</i>\n"

    kb = _build_results_keyboard(results, page=0, total=total, query=query)

    # Prepend filter buttons if available
    if filter_values:
        filter_rows = _build_filter_buttons(filter_values, query)
        all_buttons = filter_rows + list(kb.inline_keyboard)
        kb = InlineKeyboardMarkup(all_buttons)

    await message.reply_text(
        text=text,
        reply_markup=kb,
        parse_mode="HTML",
    )


async def search_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle callbacks for pagination, file selection, and filters."""
    query = update.callback_query
    await query.answer()
    data = query.data

    # --- Close button ---
    if data == "close":
        try:
            await query.message.delete()
        except Exception:
            pass
        return

    # --- Noop (page indicator) ---
    if data == "noop":
        return

    # --- File selection is handled by file_actions.py ---

    # --- Pagination: pg#<page>#<query> ---
    if data.startswith("pg#"):
        parts = data.split("#", 2)
        if len(parts) < 3:
            return
        page = int(parts[1])
        search_query = parts[2]

        results, total = await search_files(
            query=search_query, page=page, per_page=RESULTS_PER_PAGE
        )
        if not results:
            await query.answer("No more results.", show_alert=True)
            return

        text = (
            f"<b>🔍 Results for:</b> <i>{search_query}</i>\n"
            f"<b>📁 Found:</b> {total} files\n"
        )

        kb = _build_results_keyboard(results, page=page, total=total, query=search_query)

        try:
            await query.message.edit_text(
                text=text,
                reply_markup=kb,
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f"Pagination edit error: {e}")
        return

    # --- Filter: fl#<cat>#<val>#<query> ---
    if data.startswith("fl#"):
        parts = data.split("#", 3)
        if len(parts) < 4:
            return
        category_prefix = parts[1]
        filter_val = parts[2]
        search_query = parts[3]

        # Map category prefix back
        cat_map = {
            "qua": "quality",
            "lan": "language",
            "sea": "season",
            "epi": "episode",
            "yea": "year",
        }
        category = cat_map.get(category_prefix, category_prefix)

        # Search with filter applied — append filter value to query
        refined_query = f"{search_query} {filter_val}"
        results, total = await search_files(
            query=refined_query, page=0, per_page=RESULTS_PER_PAGE
        )

        if not results:
            await query.answer("No results with this filter.", show_alert=True)
            return

        text = (
            f"<b>🔍 Results for:</b> <i>{search_query}</i>\n"
            f"<b>🏷 Filter:</b> {category.title()} = {filter_val}\n"
            f"<b>📁 Found:</b> {total} files\n"
        )

        kb = _build_results_keyboard(
            results, page=0, total=total, query=refined_query
        )

        try:
            await query.message.edit_text(
                text=text,
                reply_markup=kb,
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f"Filter edit error: {e}")
        return


def register(app):
    """Register search handlers."""
    # Group auto-filter search
    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS & filters.TEXT & ~filters.COMMAND,
            group_search_handler,
        ),
        group=2,
    )

    # Search callbacks (pagination, filters, close)
    app.add_handler(
        CallbackQueryHandler(
            search_callback, pattern=r"^(pg#|fl#|close|noop)"
        )
    )
