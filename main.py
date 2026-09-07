"""
AutoFilterBot – Main Entry Point
Telegram auto-filter bot built with python-telegram-bot v21.
"""

import asyncio
import logging
import sys
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

from telegram import Update
from telegram.ext import ApplicationBuilder

from config import Config
from database.db_client import init_db

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler(sys.stderr),
    ],
)
logger = logging.getLogger(__name__)

# Silence noisy third-party loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)


# ── Health-check server (keeps free-tier hosts alive) ────────────────────────
class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, fmt, *args):
        pass  # suppress request logs


def _start_health_server():
    server = HTTPServer(("0.0.0.0", Config.PORT), _HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("Health server listening on port %s", Config.PORT)


# ── Post-init hook ───────────────────────────────────────────────────────────
async def post_init(app):
    """Called after the Application is fully initialised."""
    await init_db()
    logger.info("Database initialised")
    if Config.LOG_CHANNEL:
        try:
            await app.bot.send_message(
                chat_id=Config.LOG_CHANNEL,
                text="<b>Bot restarted successfully ✅</b>",
                parse_mode="HTML",
            )
        except Exception as exc:
            logger.warning("Failed to send restart message: %s", exc)


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    _start_health_server()

    app = (
        ApplicationBuilder()
        .token(Config.BOT_TOKEN)
        .concurrent_updates(True)
        .post_init(post_init)
        .build()
    )

    # Register handler modules — order matters.
    # file_actions MUST be registered before search so its
    # CallbackQueryHandlers take priority over search result callbacks.
    from handlers import (
        start,
        indexing,
        file_actions,
        search,
        pm_search,
        connections,
        filters,
        gfilters,
        admin,
        settings,
        force_sub,
        token_verify,
        premium,
        auto_delete,
    )

    for module in (
        start,
        indexing,
        file_actions,      # before search!
        search,
        pm_search,
        connections,
        filters,
        gfilters,
        admin,
        settings,
        force_sub,
        token_verify,
        premium,
        auto_delete,
    ):
        module.register(app)
        logger.info("Registered handlers from %s", module.__name__)

    logger.info("Starting polling…")
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )


# ── Python 3.14 event-loop fix ───────────────────────────────────────────────
# Python 3.14 removed the implicit creation of an event loop in the main
# thread.  We create one explicitly so PTB's run_polling() works correctly.
if __name__ == "__main__":
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    main()
