# 🤖 AutoFilterBot

A powerful Telegram auto-filter bot that automatically indexes and serves files from connected channels and groups. Built with **python-telegram-bot v21** and **MongoDB**.

---

## Features

- [x] Auto-filter — indexes files from groups/channels and serves them via inline search
- [x] Manual filters — custom keyword-based replies
- [x] Global filters — filters that work across all connected groups
- [x] Group connections — manage filters via PM by connecting to groups
- [x] Force subscribe — require users to join a channel before using the bot
- [x] Token verification — short-link token gating to prevent spam
- [x] Premium system — per-user premium access with extended limits
- [x] Auto-delete — automatically delete bot responses after a timeout
- [x] Admin panel — broadcast, stats, ban/unban users
- [x] PM search — search files directly in bot DMs
- [x] File actions — rename, caption edit, and share indexed files
- [x] Multi-platform deploy — Heroku, Render, Koyeb, Docker, VPS

---

## Deployment

### Prerequisites

| Requirement | Where to get it |
|---|---|
| Bot Token | [@BotFather](https://t.me/BotFather) |
| API ID & Hash | [my.telegram.org](https://my.telegram.org) |
| MongoDB URI | [MongoDB Atlas](https://www.mongodb.com/cloud/atlas) (free tier works) |

### Heroku

1. Fork this repository.
2. Create a new app on [Heroku](https://heroku.com).
3. Connect your fork under the **Deploy** tab.
4. Set the config vars listed below under **Settings > Config Vars**.
5. Deploy the `main` branch.
6. Scale the **worker** dyno to 1 under **Resources**.

### Render

1. Fork this repo and push to your GitHub.
2. Create a **New Web Service** on [Render](https://render.com).
3. Connect the repository — Render detects `render.yaml` automatically.
4. Add the required environment variables as secrets.
5. Deploy.

### Koyeb

1. Fork this repository.
2. Create a new app on [Koyeb](https://www.koyeb.com).
3. Select **Docker** builder, point to your fork.
4. Set the environment variables and deploy.

### Docker

```bash
git clone https://github.com/yourname/AutoFilterBot.git
cd AutoFilterBot
cp .env.example .env
# Edit .env with your values
docker compose up -d
```

### VPS (Manual)

```bash
git clone https://github.com/yourname/AutoFilterBot.git
cd AutoFilterBot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your values
python main.py
```

> **Tip:** Use `screen`, `tmux`, or a systemd service to keep the bot running after you disconnect.

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `BOT_TOKEN` | Yes | — | Telegram bot token from BotFather |
| `API_ID` | Yes | — | Telegram API ID |
| `API_HASH` | Yes | — | Telegram API hash |
| `MONGO_URI` | Yes | — | MongoDB connection string |
| `ADMINS` | Yes | — | Space-separated admin user IDs |
| `LOG_CHANNEL` | Yes | — | Channel ID for bot logs |
| `FORCE_SUB_CHANNEL` | No | — | Channel users must join |
| `PORT` | No | `8080` | Health-check server port |
| `BOT_NAME` | No | `AutoFilterBot` | Display name in messages |
| `MAX_RESULTS` | No | `10` | Results per search page |
| `MAX_PAGES` | No | `5` | Max pages of results |
| `START_PIC` | No | — | Photo/animation URL for /start |
| `PREMIUM_ENABLED` | No | `false` | Enable premium features |
| `AUTO_DELETE_SECONDS` | No | `300` | Auto-delete timeout (0 = off) |
| `TOKEN_EXPIRY` | No | `600` | Token link expiry in seconds |
| `SHORTLINK_API` | No | — | Short-link API key |
| `SHORTLINK_URL` | No | — | Short-link service base URL |
| `DB_NAME` | No | `autofilter` | MongoDB database name |
| `SHOW_FILE_SIZE` | No | `true` | Show file sizes in results |

---

## Commands

### User Commands

| Command | Description |
|---|---|
| `/start` | Start the bot / show welcome message |
| `/help` | Show help and usage info |
| `/connect <group_id>` | Connect a group to manage via PM |
| `/disconnect` | Disconnect the current group |

### Admin Commands (Groups)

| Command | Description |
|---|---|
| `/index` | Start indexing files from the group |
| `/filter <keyword> <reply>` | Add a manual filter |
| `/filters` | List all filters in the group |
| `/del <keyword>` | Delete a filter |
| `/delall` | Delete all filters |
| `/gfilter <keyword> <reply>` | Add a global filter |
| `/gfilters` | List global filters |
| `/settings` | Manage group settings |

### Owner Commands

| Command | Description |
|---|---|
| `/broadcast <message>` | Broadcast a message to all users |
| `/stats` | Show bot statistics |
| `/ban <user_id>` | Ban a user from the bot |
| `/unban <user_id>` | Unban a user |
| `/premium <user_id> <days>` | Grant premium access |

---

## Project Structure

```
AutoFilterBot/
├── main.py              # Entry point
├── config.py            # Configuration from environment
├── database/
│   ├── db_client.py     # MongoDB client & init
│   ├── users_db.py      # User operations
│   ├── filters_db.py    # Filter CRUD
│   ├── files_db.py      # Indexed file operations
│   └── connections_db.py # Group connection ops
├── handlers/
│   ├── start.py         # /start, /help
│   ├── indexing.py      # File indexing
│   ├── search.py        # Inline/group search
│   ├── pm_search.py     # PM search
│   ├── file_actions.py  # File operations
│   ├── connections.py   # Group connections
│   ├── filters.py       # Manual filters
│   ├── gfilters.py      # Global filters
│   ├── admin.py         # Admin panel
│   ├── settings.py      # Group settings
│   ├── force_sub.py     # Force subscribe
│   ├── token_verify.py  # Token verification
│   ├── premium.py       # Premium system
│   └── auto_delete.py   # Auto-delete
├── utils/
│   └── helpers.py       # Shared utilities
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── render.yaml
├── heroku.yml
├── Procfile
├── koyeb.yaml
├── .env.example
└── .gitignore
```

---

## Credits

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) — Telegram Bot API wrapper
- [Motor](https://motor.readthedocs.io/) — Async MongoDB driver
- [MongoDB Atlas](https://www.mongodb.com/cloud/atlas) — Cloud database

---

## License

This project is licensed under the **GNU General Public License v2.0** — see the [LICENSE](LICENSE) file for details.
