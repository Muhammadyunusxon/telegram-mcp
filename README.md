# Telegram MCP Server

An [MCP](https://modelcontextprotocol.io) server that lets Claude (or any MCP
client) control **your personal Telegram account** via the MTProto API
([Telethon](https://github.com/LonamiWebs/Telethon)) — not a bot.

Send/read messages, media, search, reactions, scheduled messages, and full
group/channel administration — all from your AI assistant, with built-in
safety guards.

> 🇺🇿 O'zbekcha qo'llanma: [README.uz.md](README.uz.md)

---

## ⚠️ Security & responsible use

- This server has **full access** to your account. Your `.session` file and
  `api_hash` act like a login — never share them or commit them to git
  (`.gitignore` already excludes them).
- Telegram limits automation. Bulk/spam messages can get your account limited
  or banned. Use responsibly, on your own account.
- Each user runs this with **their own** API credentials. There is no shared
  hosted service.

### Built-in safety guards

| Env var | Effect |
|---------|--------|
| `TELEGRAM_READONLY=1` | Disables every write/modify tool — read-only mode |
| `TELEGRAM_ALLOWED_PEERS=@chan,123,me` | Messages can only be sent to these peers |
| `TELEGRAM_MAX_FLOODWAIT=60` | Auto-wait up to N seconds on Telegram FloodWait, then retry |

Destructive tools (`delete_message`, `remove_participant`, `leave_chat`)
require an explicit `confirm=true` argument. FloodWait errors are caught and
retried automatically.

## Features (26 tools)

**Messaging:** `send_message`, `read_messages`, `search_messages`,
`reply_message`, `edit_message`, `forward_message`, `delete_message`,
`pin_message`, `unpin_message`, `react`, `schedule_message`, `mark_read`

**Media:** `send_file` (photo/document/video/voice), `download_media`

**Discovery:** `get_me`, `list_dialogs`, `list_contacts`, `resolve_entity`

**Groups & channels:** `send_to_channel`, `create_group`, `get_participants`,
`add_participants`, `remove_participant`, `promote_admin`, `join_chat`,
`leave_chat`

`peer` accepts an `@username`, phone number, chat ID, or `"me"` (Saved Messages).

---

## Setup

### 1. Get API credentials
Go to [my.telegram.org](https://my.telegram.org) → **API development tools** →
create an app. You'll get an `api_id` (number) and `api_hash` (string).

### 2. Install
```bash
git clone https://github.com/Muhammadyunusxon/telegram-mcp.git
cd telegram-mcp
pip3 install -r requirements.txt
```

### 3. Configure
```bash
cp .env.example .env
```
Edit `.env` and fill in `TELEGRAM_API_ID` and `TELEGRAM_API_HASH`.

### 4. Log in (once)
```bash
python3 login.py
```
Enter your phone (international format, e.g. `+1555...`), the code Telegram
sends, and your 2FA password if enabled. This creates a `telegram_mcp.session`
file so you won't need to log in again.

### 5. Connect to Claude Desktop
Edit your `claude_desktop_config.json`:
- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "telegram": {
      "command": "python3",
      "args": ["/absolute/path/to/telegram-mcp/server.py"]
    }
  }
}
```

The server reads credentials from `.env` automatically. Fully quit and reopen
Claude Desktop, then look for the `telegram` tools.

## Try it
- "Send 'hello' to my Saved Messages"
- "Send the file ~/report.pdf to @someone with caption 'draft'"
- "React 🔥 to message 1234 in @mychat"
- "Schedule 'Good morning' to @friend at 2026-07-21T06:00"

## Install as a Claude Desktop Extension (.mcpb)

This repo ships a Desktop Extension bundle so it can be installed in one click
and submitted to the [Anthropic Connectors Directory](https://claude.com/docs/connectors/building/submission).

- `manifest.json` — MCPB manifest (all tools annotated with `readOnlyHint` /
  `destructiveHint`; `api_id` / `api_hash` collected as sensitive user config).
- Download the `.mcpb` from [Releases](https://github.com/Muhammadyunusxon/telegram-mcp/releases)
  and open it with Claude Desktop, or build it yourself:

```bash
pip install -r requirements.txt --target lib   # vendor deps into the bundle
npx @anthropic-ai/mcpb pack . telegram-mcp.mcpb
```

> **One-time login:** because this uses your Telegram *account* (MTProto), you
> must create the session once by running `python login.py` locally before the
> extension can connect. See [PRIVACY.md](PRIVACY.md) for how your data is handled.

## Development
```bash
pip install pytest
pytest -q
```
CI runs on Python 3.10–3.12 via GitHub Actions. A `Dockerfile`, `pyproject.toml`
(build with `python -m build`), `server.json` (MCP registry), and
`smithery.yaml` are included.

## License
[MIT](LICENSE)
