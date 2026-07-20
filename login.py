#!/usr/bin/env python3
"""
Telegram akkauntga BIRINCHI MARTA login qilish skripti.
=======================================================

Buni faqat bir marta ishga tushirasiz. U telefon raqamingizga kod yuboradi,
sizdan kodni (va agar yoqilgan bo'lsa 2FA parolni) so'raydi va session faylni
saqlaydi. Shundan keyin server.py parolsiz ishlaydi.

Ishga tushirish:
    python login.py
"""

import os
import asyncio
from telethon import TelegramClient

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

API_ID = os.environ.get("TELEGRAM_API_ID")
API_HASH = os.environ.get("TELEGRAM_API_HASH")
SESSION = os.environ.get("TELEGRAM_SESSION", "telegram_mcp")

if not API_ID or not API_HASH:
    raise SystemExit(
        "TELEGRAM_API_ID va TELEGRAM_API_HASH o'rnatilmagan.\n"
        "Avval .env faylini to'ldiring (.env.example dan nusxa oling)."
    )


async def main():
    client = TelegramClient(SESSION, int(API_ID), API_HASH)
    # start() interaktiv: telefon, kod va 2FA parolni so'raydi
    await client.start()
    me = await client.get_me()
    name = " ".join(filter(None, [me.first_name, me.last_name]))
    print("\n✅ Muvaffaqiyatli login qilindi!")
    print(f"   Akkaunt: {name} (@{me.username or '—'}, id={me.id})")
    print(f"   Session fayl: {SESSION}.session")
    print("\nEndi Claude Desktop config'ini sozlab, serverdan foydalanishingiz mumkin.")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
