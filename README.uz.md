# Telegram MCP Server (user-akkaunt / MTProto)

Bu MCP server Claude'ga sizning **shaxsiy Telegram akkauntingiz** nomidan
Telegram'ni boshqarish imkonini beradi: xabar yuborish/o'qish, kontakt va chat
ro'yxatini olish, kanal/guruh boshqaruvi.

Telethon (MTProto) kutubxonasi ustiga qurilgan, ya'ni bot emas — haqiqiy
akkaunt sifatida ishlaydi.

---

## ⚠️ Muhim ogohlantirish

- Bu server sizning akkauntingizga **to'liq kirish** huquqiga ega. `.session`
  faylni va `api_hash`ni hech kimga bermang — ular login sifatida ishlaydi.
- Telegram avtomatlashtirishni cheklaydi. Ko'p / spam xabar yuborsangiz akkaunt
  vaqtincha yoki butunlay bloklanishi mumkin. Ehtiyot bo'lib foydalaning.
- Faqat o'z akkauntingizda va o'z mas'uliyatingiz ostida ishlating.

---

## 1-qadam: API kalitlarini olish

1. https://my.telegram.org saytiga telefon raqamingiz bilan kiring.
2. **API development tools** bo'limiga o'ting.
3. Yangi ilova yarating (istalgan nom, masalan "mcp").
4. Sizga **`api_id`** (raqam) va **`api_hash`** (uzun matn) beriladi.

## 2-qadam: O'rnatish

```bash
cd telegram-mcp

# (tavsiya) virtual muhit
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

## 3-qadam: Sozlash

`.env.example` faylidan nusxa oling va to'ldiring:

```bash
cp .env.example .env
```

`.env` ichida:

```
TELEGRAM_API_ID=123456
TELEGRAM_API_HASH=sizning_hash
TELEGRAM_SESSION=telegram_mcp
```

## 4-qadam: Login (bir marta)

```bash
python login.py
```

- Telefon raqamingizni xalqaro formatda kiriting (masalan `+998901234567`).
- Telegram ilovasiga kelgan **kodni** kiriting.
- Agar 2FA (parol) yoqilgan bo'lsa, uni ham kiriting.

Muvaffaqiyatli bo'lsa `telegram_mcp.session` fayli yaratiladi. Bu faylni
saqlab qo'ying — qayta login qilish shart bo'lmaydi.

## 5-qadam: Claude Desktop'ga ulash

Claude Desktop config faylini oching:

- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

`mcpServers` ichiga quyidagini qo'shing (yo'llarni o'zingiznikiga moslang):

```json
{
  "mcpServers": {
    "telegram": {
      "command": "python3",
      "args": ["/to'liq/yo'l/telegram-mcp/server.py"],
      "env": {
        "TELEGRAM_API_ID": "123456",
        "TELEGRAM_API_HASH": "sizning_hash",
        "TELEGRAM_SESSION": "/to'liq/yo'l/telegram-mcp/telegram_mcp"
      }
    }
  }
}
```

> Agar virtual muhit ishlatgan bo'lsangiz, `command` sifatida
> `.venv/bin/python3` ning to'liq yo'lini ko'rsating, shunda Telethon topiladi.

Claude Desktop'ni qayta ishga tushiring. Endi Claude'da 🔌 belgisi ostida
`telegram` serveri va uning tool'lari ko'rinadi.

---

## Mavjud tool'lar

| Tool | Vazifasi |
|------|----------|
| `send_message(peer, text)` | Xabar yuborish |
| `read_messages(peer, limit)` | So'nggi xabarlarni o'qish |
| `search_messages(peer, query, limit)` | Xabar qidirish (chat ichida yoki global) |
| `forward_message(from_peer, message_id, to_peer)` | Xabarni forward qilish |
| `delete_message(peer, message_id, revoke)` | Xabarni o'chirish |
| `mark_read(peer)` | O'qilgan deb belgilash |
| `get_me()` | Joriy akkaunt ma'lumoti |
| `list_dialogs(limit)` | Chatlar ro'yxati |
| `list_contacts()` | Kontaktlar ro'yxati |
| `resolve_entity(peer)` | @username/telefon/ID bo'yicha ma'lumot va id |
| `send_to_channel(channel, text)` | Kanal/guruhga post |
| `create_group(title, members)` | Yangi guruh yaratish |
| `get_participants(chat, limit)` | Guruh/kanal a'zolari |
| `add_participants(chat, members)` | A'zo qo'shish |
| `remove_participant(chat, member)` | A'zoni chiqarish |
| `promote_admin(chat, member)` | Admin qilish |
| `join_chat(link)` | Guruh/kanalga qo'shilish |
| `leave_chat(chat)` | Guruh/kanaldan chiqish |

`peer` sifatida `@username`, telefon raqam, chat ID yoki `"me"` (Saved
Messages) berish mumkin.

## Sinash misollari (Claude'da yozib ko'ring)

- "Menga saqlangan xabarlarga 'test' deb yoz" → `send_message("me", "test")`
- "Oxirgi 10 ta chatimni ko'rsat" → `list_dialogs(10)`
- "@durov kanalidan so'nggi 5 postni o'qi" → `read_messages("@durov", 5)`

## Muammolar

- **`unauthorized` / avtorizatsiya xatosi** — `python login.py` ni qayta ishga
  tushiring; session yo'li config'da to'g'ri ko'rsatilganini tekshiring.
- **`ModuleNotFoundError: telethon`** — Claude config'dagi `command` sizning
  virtual muhit python'ingizni ko'rsatayotganini tekshiring.
- **`database is locked`** — bir vaqtda `login.py` va `server.py` bir xil
  session'ni ishlatmasin; login tugagach serverni qayta ishga tushiring.
