# Telegram MCP Server

An [MCP](https://modelcontextprotocol.io) server that lets Claude (or any MCP
client) control **your personal Telegram account** via the MTProto API
([Telethon](https://github.com/LonamiWebs/Telethon)) — not a bot.

Send and read messages, search, manage contacts, and administer groups and
channels, all from your AI assistant.

> 🇺🇿 O'zbekcha qo'llanma: [README.uz.md](README.uz.md)

---

## ⚠️ Security & responsible use

- This server has **full access** to your account. Your `.session` file and
  `api_hash` act like a login — never share them or commit them to git
  (`.gitignore` already excludes them).
- Telegram limits automation. Sending bulk or spam messages can get your
  account limited or banned. Use responsibly, on your own account.
- Each user runs this with **their own** API credentials. There is no shared
  hosted service.

## Features (18 tools)

| Tool | Description |
|------|-------------|
| `send_message` | Send a text message |
| `read_messages` | Read recent messages from a chat |
| `search_messages` | Search messages (in a chat or globally) |
| `forward_message` | Forward a message |
| `delete_message` | Delete a message |
| `mark_read` | Mark a chat as read |
| `get_me` | Info about the logged-in account |
| `list_dialogs` | List recent chats |
| `list_contacts` | List your contacts |
| `resolve_entity` | Look up an @username/phone/ID |
| `send_to_channel` | Post to a channel/group |
| `create_group` | Create a new group |
| `get_participants` | List members of a group/channel |
| `add_participants` | Add members |
| `remove_participant` | Remove/ban a member |
| `promote_admin` | Promote a member to admin |
| `join_chat` | Join a group/channel by @username or invite link |
| `leave_chat` | Leave a group/channel |

`peer` accepts an `@username`, phone number, chat ID, or `"me"` (Saved Messages).

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
Edit `.env` and fill in your `TELEGRAM_API_ID` and `TELEGRAM_API_HASH`.

### 4. Log in (once)
```bash
python3 login.py
```
Enter your phone number (international format, e.g. `+1555...`), the code
Telegram sends you, and your 2FA password if enabled. This creates a
`telegram_mcp.session` file so you won't need to log in again.

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

The server reads your credentials from `.env` automatically. Fully quit and
reopen Claude Desktop, then look for the `telegram` tools.

## Try it
- "Send 'hello' to my Saved Messages"
- "Show my last 10 chats"
- "Read the last 5 messages from @some_channel"

## License
[MIT](LICENSE)
