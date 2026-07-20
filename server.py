#!/usr/bin/env python3
"""
Telegram MCP Server (user-akkaunt / MTProto orqali)
====================================================

Bu MCP server Telethon kutubxonasi yordamida sizning SHAXSIY Telegram
akkauntingiz nomidan ishlaydi. Claude quyidagi tool'lar orqali Telegram'ni
boshqara oladi:

  Xabar:      send_message, read_messages, search_messages, forward_message,
              delete_message, mark_read
  Ro'yxat:    list_dialogs, list_contacts, get_me, resolve_entity
  Kanal/guruh: create_group, get_participants, add_participants,
              remove_participant, promote_admin, send_to_channel,
              join_chat, leave_chat

Login birinchi marta `python login.py` orqali qilinadi va session faylga
saqlanadi — shundan keyin server parolsiz ishlaydi.

Kerakli o'zgaruvchilar (.env yoki muhit o'zgaruvchisi):
  TELEGRAM_API_ID     - my.telegram.org dan
  TELEGRAM_API_HASH   - my.telegram.org dan
  TELEGRAM_SESSION    - session fayl nomi (default: "telegram_mcp")
"""

import os
import asyncio
from typing import Optional

from telethon import TelegramClient, functions, errors
from telethon.tl.types import User, Chat, Channel
from mcp.server.fastmcp import FastMCP

# --- Sozlamalar / Configuration -------------------------------------------

_HERE = os.path.dirname(os.path.abspath(__file__))

try:
    from dotenv import load_dotenv
    # .env ni har doim server.py joylashgan papkadan o'qiymiz
    # (Claude Desktop serverni boshqa cwd dan ishga tushiradi)
    load_dotenv(os.path.join(_HERE, ".env"))
except Exception:
    pass

API_ID = os.environ.get("TELEGRAM_API_ID")
API_HASH = os.environ.get("TELEGRAM_API_HASH")
SESSION = os.environ.get("TELEGRAM_SESSION", "telegram_mcp")
# Session fayl nomini absolyut yo'lga aylantiramiz, aks holda Telethon
# uni noto'g'ri papkadan qidiradi va login topilmaydi.
if not os.path.isabs(SESSION):
    SESSION = os.path.join(_HERE, SESSION)

if not API_ID or not API_HASH:
    raise RuntimeError(
        "TELEGRAM_API_ID va TELEGRAM_API_HASH o'rnatilmagan. "
        "Ularni my.telegram.org dan oling va .env fayliga yozing."
    )

# Telethon klienti (bitta global, event loop MCP ichida yuritiladi)
client = TelegramClient(SESSION, int(API_ID), API_HASH)

mcp = FastMCP("telegram")

_started = False


async def _ensure_connected():
    """Klient ulangan va avtorizatsiyadan o'tganini ta'minlaydi."""
    global _started
    if not _started:
        await client.connect()
        if not await client.is_user_authorized():
            raise RuntimeError(
                "Telegram akkaunt avtorizatsiyadan o'tmagan. "
                "Avval `python login.py` ni ishga tushiring."
            )
        _started = True


def _describe(entity) -> dict:
    """Entity'ni (User/Chat/Channel) qisqa dict ko'rinishida qaytaradi."""
    d = {"id": getattr(entity, "id", None)}
    if isinstance(entity, User):
        d["type"] = "user"
        name = " ".join(filter(None, [entity.first_name, entity.last_name]))
        d["name"] = name or (entity.username or str(entity.id))
        d["username"] = entity.username
        d["phone"] = entity.phone
        d["bot"] = entity.bot
    elif isinstance(entity, Channel):
        d["type"] = "channel" if entity.broadcast else "supergroup"
        d["name"] = entity.title
        d["username"] = getattr(entity, "username", None)
    elif isinstance(entity, Chat):
        d["type"] = "group"
        d["name"] = entity.title
    else:
        d["type"] = "unknown"
        d["name"] = str(entity)
    return d


# --- Xabar tool'lari / Messaging ------------------------------------------

@mcp.tool()
async def send_message(peer: str, text: str) -> str:
    """Berilgan chat/foydalanuvchi/kanalga matnli xabar yuboradi.

    Args:
        peer: qabul qiluvchi. @username, telefon raqam, chat ID yoki
              "me" (o'zingizga saqlangan xabarlar) bo'lishi mumkin.
        text: yuboriladigan matn (Markdown qo'llab-quvvatlanadi).
    """
    await _ensure_connected()
    entity = await client.get_entity(peer)
    msg = await client.send_message(entity, text)
    return f"Yuborildi. message_id={msg.id}, peer={_describe(entity)['name']}"


@mcp.tool()
async def read_messages(peer: str, limit: int = 20) -> str:
    """Chat/foydalanuvchidan so'nggi xabarlarni o'qiydi.

    Args:
        peer: @username, telefon, chat ID yoki "me".
        limit: nechta so'nggi xabar (default 20, maksimum 100).
    """
    await _ensure_connected()
    limit = max(1, min(limit, 100))
    entity = await client.get_entity(peer)
    lines = []
    async for m in client.iter_messages(entity, limit=limit):
        who = "me" if m.out else (
            (m.sender.first_name if m.sender and hasattr(m.sender, "first_name")
             else str(m.sender_id))
        )
        when = m.date.strftime("%Y-%m-%d %H:%M") if m.date else "?"
        body = m.text or (f"[{m.media.__class__.__name__}]" if m.media else "")
        lines.append(f"[{when}] {who} (id={m.id}): {body}")
    lines.reverse()  # eskidan yangiga
    header = f"=== {_describe(entity)['name']} (so'nggi {len(lines)}) ==="
    return header + "\n" + "\n".join(lines) if lines else header + "\n(xabar yo'q)"


@mcp.tool()
async def search_messages(peer: str, query: str, limit: int = 20) -> str:
    """Chat ichida yoki (peer='') global bo'yicha xabar qidiradi.

    Args:
        peer: qidiriladigan chat; bo'sh string berilsa barcha chatlarda.
        query: qidiruv so'zi.
        limit: natijalar soni (default 20).
    """
    await _ensure_connected()
    limit = max(1, min(limit, 100))
    entity = await client.get_entity(peer) if peer else None
    lines = []
    async for m in client.iter_messages(entity, search=query, limit=limit):
        when = m.date.strftime("%Y-%m-%d %H:%M") if m.date else "?"
        chat_name = ""
        if entity is None and m.chat:
            chat_name = f" | {getattr(m.chat, 'title', getattr(m.chat, 'first_name', ''))}"
        lines.append(f"[{when}] id={m.id}{chat_name}: {m.text or ''}")
    return "\n".join(lines) if lines else "(hech narsa topilmadi)"


@mcp.tool()
async def forward_message(from_peer: str, message_id: int, to_peer: str) -> str:
    """Xabarni bir chatdan boshqasiga forward qiladi.

    Args:
        from_peer: xabar qayerdan.
        message_id: forward qilinadigan xabar ID.
        to_peer: qayerga yuboriladi.
    """
    await _ensure_connected()
    src = await client.get_entity(from_peer)
    dst = await client.get_entity(to_peer)
    await client.forward_messages(dst, message_id, src)
    return f"Forward qilindi -> {_describe(dst)['name']}"


@mcp.tool()
async def delete_message(peer: str, message_id: int, revoke: bool = True) -> str:
    """Xabarni o'chiradi.

    Args:
        peer: qaysi chat.
        message_id: o'chiriladigan xabar ID.
        revoke: True bo'lsa hamma uchun o'chiradi (default True).
    """
    await _ensure_connected()
    entity = await client.get_entity(peer)
    await client.delete_messages(entity, message_id, revoke=revoke)
    return f"O'chirildi: id={message_id}"


@mcp.tool()
async def mark_read(peer: str) -> str:
    """Chatdagi barcha xabarlarni o'qilgan deb belgilaydi."""
    await _ensure_connected()
    entity = await client.get_entity(peer)
    await client.send_read_acknowledge(entity)
    return f"O'qilgan deb belgilandi: {_describe(entity)['name']}"


# --- Ro'yxat / Discovery ---------------------------------------------------

@mcp.tool()
async def get_me() -> str:
    """Joriy (login qilingan) akkaunt haqida ma'lumot."""
    await _ensure_connected()
    me = await client.get_me()
    return str(_describe(me))


@mcp.tool()
async def list_dialogs(limit: int = 30) -> str:
    """So'nggi chatlar (dialoglar) ro'yxati: shaxsiy, guruh, kanal.

    Args:
        limit: nechta dialog (default 30, maksimum 200).
    """
    await _ensure_connected()
    limit = max(1, min(limit, 200))
    lines = []
    async for d in client.iter_dialogs(limit=limit):
        info = _describe(d.entity)
        unread = f" | o'qilmagan: {d.unread_count}" if d.unread_count else ""
        uname = f" (@{info['username']})" if info.get("username") else ""
        lines.append(f"{info['type']}: {info['name']}{uname} | id={info['id']}{unread}")
    return "\n".join(lines) if lines else "(dialog yo'q)"


@mcp.tool()
async def list_contacts() -> str:
    """Barcha Telegram kontaktlaringiz ro'yxati."""
    await _ensure_connected()
    result = await client(functions.contacts.GetContactsRequest(hash=0))
    lines = []
    for u in result.users:
        info = _describe(u)
        uname = f" (@{info['username']})" if info.get("username") else ""
        phone = f" | {info['phone']}" if info.get("phone") else ""
        lines.append(f"{info['name']}{uname} | id={info['id']}{phone}")
    return "\n".join(lines) if lines else "(kontakt yo'q)"


@mcp.tool()
async def resolve_entity(peer: str) -> str:
    """@username, telefon yoki ID bo'yicha entity ma'lumotini oladi (id topish uchun)."""
    await _ensure_connected()
    entity = await client.get_entity(peer)
    return str(_describe(entity))


# --- Kanal / guruh boshqaruvi / Channel & group management ----------------

@mcp.tool()
async def send_to_channel(channel: str, text: str) -> str:
    """Kanal yoki guruhga post joylaydi (send_message bilan bir xil, aniqlik uchun alohida)."""
    await _ensure_connected()
    entity = await client.get_entity(channel)
    msg = await client.send_message(entity, text)
    return f"Post joylandi: {_describe(entity)['name']}, id={msg.id}"


@mcp.tool()
async def create_group(title: str, members: list[str]) -> str:
    """Yangi guruh yaratadi va a'zolarni qo'shadi.

    Args:
        title: guruh nomi.
        members: @username yoki telefon raqamlar ro'yxati.
    """
    await _ensure_connected()
    users = [await client.get_entity(m) for m in members]
    result = await client(functions.messages.CreateChatRequest(
        users=users, title=title))
    return f"Guruh yaratildi: {title}"


@mcp.tool()
async def get_participants(chat: str, limit: int = 100) -> str:
    """Guruh/kanal a'zolari ro'yxatini oladi.

    Args:
        chat: @username yoki ID.
        limit: maksimum a'zolar soni (default 100).
    """
    await _ensure_connected()
    entity = await client.get_entity(chat)
    lines = []
    async for u in client.iter_participants(entity, limit=limit):
        info = _describe(u)
        uname = f" (@{info['username']})" if info.get("username") else ""
        lines.append(f"{info['name']}{uname} | id={info['id']}")
    return "\n".join(lines) if lines else "(a'zo topilmadi)"


@mcp.tool()
async def add_participants(chat: str, members: list[str]) -> str:
    """Guruh/kanalga yangi a'zolar qo'shadi.

    Args:
        chat: qaysi guruh/kanal.
        members: @username yoki telefon raqamlar ro'yxati.
    """
    await _ensure_connected()
    entity = await client.get_entity(chat)
    added, failed = [], []
    for m in members:
        try:
            user = await client.get_entity(m)
            await client(functions.channels.InviteToChannelRequest(
                channel=entity, users=[user]))
            added.append(m)
        except Exception as e:
            failed.append(f"{m} ({e.__class__.__name__})")
    res = f"Qo'shildi: {', '.join(added) or '—'}"
    if failed:
        res += f"\nXato: {', '.join(failed)}"
    return res


@mcp.tool()
async def remove_participant(chat: str, member: str) -> str:
    """Guruh/kanaldan a'zoni chiqaradi (ban qiladi).

    Args:
        chat: qaysi guruh/kanal.
        member: chiqariladigan foydalanuvchi (@username/telefon/ID).
    """
    await _ensure_connected()
    entity = await client.get_entity(chat)
    user = await client.get_entity(member)
    await client.edit_permissions(entity, user, view_messages=False)
    return f"Chiqarildi: {_describe(user)['name']}"


@mcp.tool()
async def promote_admin(chat: str, member: str) -> str:
    """Foydalanuvchini guruh/kanalda administrator qiladi.

    Args:
        chat: qaysi guruh/kanal.
        member: admin qilinadigan foydalanuvchi.
    """
    await _ensure_connected()
    entity = await client.get_entity(chat)
    user = await client.get_entity(member)
    await client.edit_admin(
        entity, user,
        change_info=True, post_messages=True, edit_messages=True,
        delete_messages=True, ban_users=True, invite_users=True,
        pin_messages=True, add_admins=False)
    return f"Admin qilindi: {_describe(user)['name']}"


@mcp.tool()
async def join_chat(link: str) -> str:
    """Public @username yoki invite link orqali guruh/kanalga qo'shiladi."""
    await _ensure_connected()
    try:
        if "joinchat" in link or "+" in link:
            invite_hash = link.rstrip("/").split("/")[-1].lstrip("+")
            await client(functions.messages.ImportChatInviteRequest(invite_hash))
        else:
            entity = await client.get_entity(link)
            await client(functions.channels.JoinChannelRequest(entity))
        return f"Qo'shildingiz: {link}"
    except errors.UserAlreadyParticipantError:
        return "Siz allaqachon a'zosiz."


@mcp.tool()
async def leave_chat(chat: str) -> str:
    """Guruh/kanaldan chiqadi."""
    await _ensure_connected()
    entity = await client.get_entity(chat)
    await client.delete_dialog(entity)
    return f"Chiqdingiz: {_describe(entity)['name']}"


# --- Ishga tushirish / Entry point ----------------------------------------

if __name__ == "__main__":
    # FastMCP stdio transport orqali ishlaydi (Claude Desktop shu orqali ulanadi)
    mcp.run()
