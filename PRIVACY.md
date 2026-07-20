# Privacy Policy — Telegram MCP Server

_Last updated: 2026-07-20_

This is a **local, open-source MCP server**. It runs entirely on your own
machine. There is no hosted service, no backend operated by the author, and no
telemetry.

## What data is involved

- **Telegram API credentials** (`api_id`, `api_hash`) and your **login session**
  are stored **only on your device** — in your `.env` file and the local
  `.session` file. They are never transmitted anywhere except directly to
  Telegram's own servers, exactly as the official Telegram apps do.
- **Message and account data** (chats, contacts, messages, media) is read from
  Telegram and passed to your MCP client (e.g. Claude) **only when you invoke a
  tool**. It is not stored, logged, or sent to any third party by this server.

## What the author receives

Nothing. The author of this software does not operate any server and does not
receive your credentials, messages, or usage data.

## Third parties

- **Telegram** — all Telegram operations go directly to Telegram's servers and
  are governed by [Telegram's Privacy Policy](https://telegram.org/privacy).
- **Your MCP client** (e.g. Claude Desktop) — tool inputs and outputs are
  handled by that client under its own privacy policy.

## Your control

- Delete the `.session` file to revoke this server's access to your account.
- You can also terminate the session from any Telegram app under
  **Settings → Devices → Active sessions**.
- Enable read-only mode (`TELEGRAM_READONLY=1`) to prevent any write actions.

## Contact

Questions or concerns: open an issue at
https://github.com/Muhammadyunusxon/telegram-mcp/issues
