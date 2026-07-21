#!/usr/bin/env python3
"""
Telegram MCP Server (user-akkaunt / MTProto orqali)
====================================================

Bu MCP server Telethon kutubxonasi yordamida sizning SHAXSIY Telegram
akkauntingiz nomidan ishlaydi. Claude quyidagi tool'lar orqali Telegram'ni
boshqara oladi.

Login birinchi marta `python login.py` orqali qilinadi va session faylga
saqlanadi.

Muhit o'zgaruvchilari (.env yoki tizim orqali):
  TELEGRAM_API_ID        - my.telegram.org dan (majburiy)
  TELEGRAM_API_HASH      - my.telegram.org dan (majburiy)
  TELEGRAM_SESSION       - session fayl nomi (default: "telegram_mcp")

  --- Xavfsizlik sozlamalari (ixtiyoriy) ---
  TELEGRAM_READONLY      - "1" bo'lsa barcha yozish/o'zgartirish amallari
                           o'chiriladi (faqat o'qish rejimi).
  TELEGRAM_ALLOWED_PEERS - vergul bilan ajratilgan @username yoki ID'lar.
                           O'rnatilsa, xabar faqat shu chatlarga yuboriladi.
  TELEGRAM_MAX_FLOODWAIT  - avtomatik kutiladigan maksimal FloodWait soniyasi
                           (default 60). Undan katta bo'lsa xato qaytadi.
"""

import os
import asyncio
import functools
import inspect
from datetime import datetime, timezone

from telethon import TelegramClient, functions, errors
from telethon.tl.types import User, Chat, Channel, ReactionEmoji
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

import kb as knowledge_base

# --- Sozlamalar / Configuration -------------------------------------------

_HERE = os.path.dirname(os.path.abspath(__file__))

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_HERE, ".env"))
except Exception:
    pass

API_ID = os.environ.get("TELEGRAM_API_ID")
API_HASH = os.environ.get("TELEGRAM_API_HASH")
SESSION = os.environ.get("TELEGRAM_SESSION", "telegram_mcp")
if not os.path.isabs(SESSION):
    SESSION = os.path.join(_HERE, SESSION)

READONLY = os.environ.get("TELEGRAM_READONLY", "").strip() in ("1", "true", "yes")
ALLOWED_PEERS = {
    p.strip().lstrip("@").lower()
    for p in os.environ.get("TELEGRAM_ALLOWED_PEERS", "").split(",")
    if p.strip()
}
MAX_FLOODWAIT = int(os.environ.get("TELEGRAM_MAX_FLOODWAIT", "60"))

if not API_ID or not API_HASH:
    raise RuntimeError(
        "TELEGRAM_API_ID va TELEGRAM_API_HASH o'rnatilmagan. "
        "Ularni my.telegram.org dan oling va .env fayliga yozing."
    )

client = TelegramClient(SESSION, int(API_ID), API_HASH)
mcp = FastMCP("telegram")

_started = False


# --- Yordamchi funksiyalar / Helpers --------------------------------------

class SafetyError(Exception):
    """Xavfsizlik cheklovi buzilganda ko'taruvchi xatolik."""


async def _ensure_connected():
    global _started
    if not _started:
        await client.connect()
        if not await client.is_user_authorized():
            raise RuntimeError(
                "Telegram akkaunt avtorizatsiyadan o'tmagan. "
                "Avval `python login.py` ni ishga tushiring."
            )
        _started = True


def _guard_write():
    """Read-only rejimda yozish amallarini to'xtatadi."""
    if READONLY:
        raise SafetyError(
            "🔒 Read-only rejim yoqilgan (TELEGRAM_READONLY=1). "
            "Yozish/o'zgartirish amallari o'chirilgan."
        )


def _guard_peer(entity):
    """Allowlist o'rnatilgan bo'lsa, faqat ruxsat berilgan chatlarga yozadi."""
    if not ALLOWED_PEERS:
        return
    ident = {str(getattr(entity, "id", "")).lower()}
    uname = getattr(entity, "username", None)
    if uname:
        ident.add(uname.lower())
    if ident.isdisjoint(ALLOWED_PEERS):
        raise SafetyError(
            f"🔒 Bu chat allowlistda yo'q (TELEGRAM_ALLOWED_PEERS): "
            f"{_describe(entity)['name']}. Yozishga ruxsat yo'q."
        )


def _describe(entity) -> dict:
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


def tg_tool(title, read_only=False, destructive=False):
    """
    Tool dekoratori — annotatsiya (title/readOnlyHint/destructiveHint) bilan.
    Har bir tool uchun umumiy o'ram:
      - ulanishni ta'minlaydi (_ensure_connected)
      - FloodWait xatosini avtomatik ushlaydi va kutib qayta uradi
      - SafetyError'ni tushunarli matn qilib qaytaradi
    FastMCP sxemasi buzilmasligi uchun imzo (signature) saqlanadi.
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                await _ensure_connected()
            except Exception as e:
                return f"❌ Ulanish xatosi: {e}"
            for attempt in range(4):
                try:
                    return await func(*args, **kwargs)
                except errors.FloodWaitError as e:
                    if e.seconds > MAX_FLOODWAIT or attempt == 3:
                        return (f"⏳ FloodWait: Telegram {e.seconds}s kutishni so'radi. "
                                f"Keyinroq urinib ko'ring.")
                    await asyncio.sleep(e.seconds + 1)
                except SafetyError as e:
                    return str(e)
                except Exception as e:
                    return f"❌ Xatolik ({e.__class__.__name__}): {e}"
        wrapper.__wrapped__ = func
        try:
            wrapper.__signature__ = inspect.signature(func)
        except (ValueError, TypeError):
            pass
        wrapper.__annotations__ = getattr(func, "__annotations__", {})
        annotations = ToolAnnotations(
            title=title,
            readOnlyHint=read_only,
            destructiveHint=destructive,
        )
        return mcp.tool(annotations=annotations)(wrapper)
    return decorator


# --- Xabar tool'lari / Messaging ------------------------------------------

@tg_tool("Send message")
async def send_message(peer: str, text: str) -> str:
    """Berilgan chat/foydalanuvchi/kanalga matnli xabar yuboradi.

    Args:
        peer: qabul qiluvchi. @username, telefon, chat ID yoki "me".
        text: yuboriladigan matn (Markdown qo'llab-quvvatlanadi).
    """
    _guard_write()
    entity = await client.get_entity(peer)
    _guard_peer(entity)
    msg = await client.send_message(entity, text)
    return f"✅ Yuborildi. message_id={msg.id}, peer={_describe(entity)['name']}"


@tg_tool("Read messages", read_only=True)
async def read_messages(peer: str, limit: int = 20) -> str:
    """Chat/foydalanuvchidan so'nggi xabarlarni o'qiydi.

    Args:
        peer: @username, telefon, chat ID yoki "me".
        limit: nechta so'nggi xabar (default 20, maksimum 100).
    """
    limit = max(1, min(limit, 100))
    entity = await client.get_entity(peer)
    lines = []
    async for m in client.iter_messages(entity, limit=limit):
        who = "me" if m.out else (
            m.sender.first_name if m.sender and hasattr(m.sender, "first_name")
            else str(m.sender_id))
        when = m.date.strftime("%Y-%m-%d %H:%M") if m.date else "?"
        body = m.text or (f"[{m.media.__class__.__name__}]" if m.media else "")
        lines.append(f"[{when}] {who} (id={m.id}): {body}")
    lines.reverse()
    header = f"=== {_describe(entity)['name']} (so'nggi {len(lines)}) ==="
    return header + "\n" + "\n".join(lines) if lines else header + "\n(xabar yo'q)"


@tg_tool("Search messages", read_only=True)
async def search_messages(peer: str, query: str, limit: int = 20) -> str:
    """Chat ichida yoki (peer='') global bo'yicha xabar qidiradi.

    Args:
        peer: qidiriladigan chat; bo'sh bo'lsa barcha chatlarda.
        query: qidiruv so'zi.
        limit: natijalar soni (default 20).
    """
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


@tg_tool("Reply to message")
async def reply_message(peer: str, reply_to_message_id: int, text: str) -> str:
    """Muayyan xabarga reply (javob) tarzida xabar yuboradi.

    Args:
        peer: qaysi chat.
        reply_to_message_id: javob beriladigan xabar ID.
        text: javob matni.
    """
    _guard_write()
    entity = await client.get_entity(peer)
    _guard_peer(entity)
    msg = await client.send_message(entity, text, reply_to=reply_to_message_id)
    return f"✅ Javob yuborildi. message_id={msg.id}"


@tg_tool("Edit message")
async def edit_message(peer: str, message_id: int, new_text: str) -> str:
    """O'zingiz yuborgan xabarni tahrirlaydi.

    Args:
        peer: qaysi chat.
        message_id: tahrirlanadigan xabar ID.
        new_text: yangi matn.
    """
    _guard_write()
    entity = await client.get_entity(peer)
    _guard_peer(entity)
    await client.edit_message(entity, message_id, new_text)
    return f"✅ Tahrirlandi: id={message_id}"


@tg_tool("Forward message")
async def forward_message(from_peer: str, message_id: int, to_peer: str) -> str:
    """Xabarni bir chatdan boshqasiga forward qiladi."""
    _guard_write()
    src = await client.get_entity(from_peer)
    dst = await client.get_entity(to_peer)
    _guard_peer(dst)
    await client.forward_messages(dst, message_id, src)
    return f"✅ Forward qilindi -> {_describe(dst)['name']}"


@tg_tool("Delete message", destructive=True)
async def delete_message(peer: str, message_id: int, confirm: bool = False,
                         revoke: bool = True) -> str:
    """Xabarni o'chiradi. Xavfsizlik uchun confirm=True talab qilinadi.

    Args:
        peer: qaysi chat.
        message_id: o'chiriladigan xabar ID.
        confirm: True bo'lishi shart (tasodifiy o'chirishdan himoya).
        revoke: True bo'lsa hamma uchun o'chiradi.
    """
    _guard_write()
    if not confirm:
        return ("⚠️ Tasdiqlash kerak: bu xabarni o'chirish uchun confirm=True "
                "bilan qayta chaqiring.")
    entity = await client.get_entity(peer)
    await client.delete_messages(entity, message_id, revoke=revoke)
    return f"✅ O'chirildi: id={message_id}"


@tg_tool("Pin message")
async def pin_message(peer: str, message_id: int, notify: bool = False) -> str:
    """Xabarni chatda pin qiladi.

    Args:
        peer: qaysi chat.
        message_id: pin qilinadigan xabar ID.
        notify: True bo'lsa a'zolarga bildirishnoma yuboriladi.
    """
    _guard_write()
    entity = await client.get_entity(peer)
    _guard_peer(entity)
    await client.pin_message(entity, message_id, notify=notify)
    return f"📌 Pin qilindi: id={message_id}"


@tg_tool("Unpin message")
async def unpin_message(peer: str, message_id: int = 0) -> str:
    """Xabar pinini olib tashlaydi. message_id=0 bo'lsa barcha pinlarni oladi."""
    _guard_write()
    entity = await client.get_entity(peer)
    await client.unpin_message(entity, message_id or None)
    return "✅ Pin olib tashlandi"


@tg_tool("React to message")
async def react(peer: str, message_id: int, emoji: str = "👍") -> str:
    """Xabarga emoji-reaksiya qo'yadi (bo'sh emoji reaksiyani olib tashlaydi).

    Args:
        peer: qaysi chat.
        message_id: reaksiya qo'yiladigan xabar ID.
        emoji: reaksiya emojisi (masalan 👍 ❤️ 🔥). Bo'sh bo'lsa olib tashlaydi.
    """
    _guard_write()
    entity = await client.get_entity(peer)
    _guard_peer(entity)
    reaction = [ReactionEmoji(emoticon=emoji)] if emoji else None
    await client(functions.messages.SendReactionRequest(
        peer=entity, msg_id=message_id, reaction=reaction))
    return f"✅ Reaksiya: {emoji or '(olib tashlandi)'} -> id={message_id}"


@tg_tool("Schedule message")
async def schedule_message(peer: str, text: str, when: str) -> str:
    """Xabarni belgilangan vaqtda yuborilishga rejalashtiradi.

    Args:
        peer: qabul qiluvchi.
        text: xabar matni.
        when: ISO formatdagi vaqt, masalan "2026-07-21T09:00" (UTC deb olinadi).
    """
    _guard_write()
    entity = await client.get_entity(peer)
    _guard_peer(entity)
    try:
        dt = datetime.fromisoformat(when)
    except ValueError:
        return "❌ Vaqt formati noto'g'ri. ISO ishlating, masalan 2026-07-21T09:00"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    msg = await client.send_message(entity, text, schedule=dt)
    return f"🕒 Rejalashtirildi ({when}) -> {_describe(entity)['name']}, id={msg.id}"


@tg_tool("Mark chat as read")
async def mark_read(peer: str) -> str:
    """Chatdagi barcha xabarlarni o'qilgan deb belgilaydi."""
    _guard_write()
    entity = await client.get_entity(peer)
    await client.send_read_acknowledge(entity)
    return f"✅ O'qilgan deb belgilandi: {_describe(entity)['name']}"


# --- Media tool'lari / Media ----------------------------------------------

@tg_tool("Send file")
async def send_file(peer: str, path: str, caption: str = "",
                    voice: bool = False) -> str:
    """Fayl (rasm, hujjat, video, audio) yuboradi.

    Args:
        peer: qabul qiluvchi.
        path: yuboriladigan fayl yo'li (server ishlayotgan mashinada).
        caption: fayl ostidagi matn (ixtiyoriy).
        voice: True bo'lsa audio ovozli xabar (voice note) sifatida yuboriladi.
    """
    _guard_write()
    if not os.path.exists(path):
        return f"❌ Fayl topilmadi: {path}"
    entity = await client.get_entity(peer)
    _guard_peer(entity)
    msg = await client.send_file(entity, path, caption=caption, voice_note=voice)
    return f"✅ Fayl yuborildi: {os.path.basename(path)} -> {_describe(entity)['name']}, id={msg.id}"


@tg_tool("Download media", read_only=True)
async def download_media(peer: str, message_id: int, dest_dir: str = "") -> str:
    """Xabardagi media (rasm/fayl/video)ni yuklab oladi.

    Args:
        peer: qaysi chat.
        message_id: media joylashgan xabar ID.
        dest_dir: saqlash papkasi (bo'sh bo'lsa server papkasi/downloads).
    """
    entity = await client.get_entity(peer)
    msg = await client.get_messages(entity, ids=message_id)
    if not msg or not msg.media:
        return "❌ Bu xabarda media yo'q."
    target = dest_dir or os.path.join(_HERE, "downloads")
    os.makedirs(target, exist_ok=True)
    saved = await client.download_media(msg, file=target)
    return f"✅ Yuklab olindi: {saved}"


# --- Ro'yxat / Discovery ---------------------------------------------------

@tg_tool("Get my account info", read_only=True)
async def get_me() -> str:
    """Joriy (login qilingan) akkaunt haqida ma'lumot."""
    me = await client.get_me()
    info = _describe(me)
    mode = " | READ-ONLY" if READONLY else ""
    return str(info) + mode


@tg_tool("List chats", read_only=True)
async def list_dialogs(limit: int = 30) -> str:
    """So'nggi chatlar (dialoglar) ro'yxati: shaxsiy, guruh, kanal.

    Args:
        limit: nechta dialog (default 30, maksimum 200).
    """
    limit = max(1, min(limit, 200))
    lines = []
    async for d in client.iter_dialogs(limit=limit):
        info = _describe(d.entity)
        unread = f" | o'qilmagan: {d.unread_count}" if d.unread_count else ""
        uname = f" (@{info['username']})" if info.get("username") else ""
        lines.append(f"{info['type']}: {info['name']}{uname} | id={info['id']}{unread}")
    return "\n".join(lines) if lines else "(dialog yo'q)"


@tg_tool("List contacts", read_only=True)
async def list_contacts() -> str:
    """Barcha Telegram kontaktlaringiz ro'yxati."""
    result = await client(functions.contacts.GetContactsRequest(hash=0))
    lines = []
    for u in result.users:
        info = _describe(u)
        uname = f" (@{info['username']})" if info.get("username") else ""
        phone = f" | {info['phone']}" if info.get("phone") else ""
        lines.append(f"{info['name']}{uname} | id={info['id']}{phone}")
    return "\n".join(lines) if lines else "(kontakt yo'q)"


@tg_tool("Resolve username or ID", read_only=True)
async def resolve_entity(peer: str) -> str:
    """@username, telefon yoki ID bo'yicha entity ma'lumotini oladi."""
    entity = await client.get_entity(peer)
    return str(_describe(entity))


# --- Kanal / guruh boshqaruvi / Channel & group management ----------------

@tg_tool("Post to channel")
async def send_to_channel(channel: str, text: str) -> str:
    """Kanal yoki guruhga post joylaydi."""
    _guard_write()
    entity = await client.get_entity(channel)
    _guard_peer(entity)
    msg = await client.send_message(entity, text)
    return f"✅ Post joylandi: {_describe(entity)['name']}, id={msg.id}"


@tg_tool("Create group")
async def create_group(title: str, members: list[str]) -> str:
    """Yangi guruh yaratadi va a'zolarni qo'shadi.

    Args:
        title: guruh nomi.
        members: @username yoki telefon raqamlar ro'yxati.
    """
    _guard_write()
    users = [await client.get_entity(m) for m in members]
    await client(functions.messages.CreateChatRequest(users=users, title=title))
    return f"✅ Guruh yaratildi: {title}"


@tg_tool("List participants", read_only=True)
async def get_participants(chat: str, limit: int = 100) -> str:
    """Guruh/kanal a'zolari ro'yxatini oladi.

    Args:
        chat: @username yoki ID.
        limit: maksimum a'zolar soni (default 100).
    """
    entity = await client.get_entity(chat)
    lines = []
    async for u in client.iter_participants(entity, limit=limit):
        info = _describe(u)
        uname = f" (@{info['username']})" if info.get("username") else ""
        lines.append(f"{info['name']}{uname} | id={info['id']}")
    return "\n".join(lines) if lines else "(a'zo topilmadi)"


@tg_tool("Add participants")
async def add_participants(chat: str, members: list[str]) -> str:
    """Guruh/kanalga yangi a'zolar qo'shadi."""
    _guard_write()
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
    res = f"✅ Qo'shildi: {', '.join(added) or '—'}"
    if failed:
        res += f"\n❌ Xato: {', '.join(failed)}"
    return res


@tg_tool("Remove participant", destructive=True)
async def remove_participant(chat: str, member: str, confirm: bool = False) -> str:
    """Guruh/kanaldan a'zoni chiqaradi. confirm=True talab qilinadi.

    Args:
        chat: qaysi guruh/kanal.
        member: chiqariladigan foydalanuvchi.
        confirm: True bo'lishi shart.
    """
    _guard_write()
    if not confirm:
        return "⚠️ Tasdiqlash kerak: chiqarish uchun confirm=True bilan chaqiring."
    entity = await client.get_entity(chat)
    user = await client.get_entity(member)
    await client.edit_permissions(entity, user, view_messages=False)
    return f"✅ Chiqarildi: {_describe(user)['name']}"


@tg_tool("Promote to admin")
async def promote_admin(chat: str, member: str) -> str:
    """Foydalanuvchini guruh/kanalda administrator qiladi."""
    _guard_write()
    entity = await client.get_entity(chat)
    user = await client.get_entity(member)
    await client.edit_admin(
        entity, user,
        change_info=True, post_messages=True, edit_messages=True,
        delete_messages=True, ban_users=True, invite_users=True,
        pin_messages=True, add_admins=False)
    return f"✅ Admin qilindi: {_describe(user)['name']}"


@tg_tool("Join chat")
async def join_chat(link: str) -> str:
    """Public @username yoki invite link orqali guruh/kanalga qo'shiladi."""
    _guard_write()
    try:
        if "joinchat" in link or "+" in link:
            invite_hash = link.rstrip("/").split("/")[-1].lstrip("+")
            await client(functions.messages.ImportChatInviteRequest(invite_hash))
        else:
            entity = await client.get_entity(link)
            await client(functions.channels.JoinChannelRequest(entity))
        return f"✅ Qo'shildingiz: {link}"
    except errors.UserAlreadyParticipantError:
        return "Siz allaqachon a'zosiz."


@tg_tool("Leave chat", destructive=True)
async def leave_chat(chat: str, confirm: bool = False) -> str:
    """Guruh/kanaldan chiqadi. confirm=True talab qilinadi."""
    _guard_write()
    if not confirm:
        return "⚠️ Tasdiqlash kerak: chiqish uchun confirm=True bilan chaqiring."
    entity = await client.get_entity(chat)
    await client.delete_dialog(entity)
    return f"✅ Chiqdingiz: {_describe(entity)['name']}"


# --- Bilimlar bazasi / Knowledge base -------------------------------------

@mcp.tool(annotations=ToolAnnotations(
    title="Answer from knowledge base", readOnlyHint=True))
async def answer_from_kb(question: str, top_k: int = 3) -> str:
    """Javoblar bazasidan (knowledge.json) savolga eng mos javoblarni topadi.

    Gibrid qidiruv (kalit so'z + fuzzy + ixtiyoriy semantik) ishlatadi.
    Natijadagi javoblarni ASOS qilib, foydalanuvchiga tabiiy javob yozing.
    Agar hech narsa topilmasa, o'zingizdan to'qib chiqarmang — bilmasligingizni
    ayting yoki bazaga javob qo'shishni taklif qiling.

    Args:
        question: foydalanuvchi savoli.
        top_k: nechta mos javob qaytarilsin (default 3).
    """
    hits = knowledge_base.search(question, top_k=top_k)
    if not hits:
        return ("(Bazadan mos javob topilmadi. O'zingizdan to'qimang — "
                "bilmasligingizni ayting yoki kb_add bilan javob qo'shing.)")
    lines = ["Bazadan topilgan javoblar (ball bo'yicha):"]
    for h in hits:
        tags = f" [teglar: {', '.join(h.get('tags', []))}]" if h.get("tags") else ""
        lines.append(f"\n• (ball {h['score']}) S: {h.get('q','')}\n  J: {h.get('a','')}{tags}")
    return "\n".join(lines)


@mcp.tool(annotations=ToolAnnotations(title="Add to knowledge base"))
async def kb_add(question: str, answer: str, tags: list[str] = None) -> str:
    """Javoblar bazasiga yangi savol-javob qo'shadi.

    Args:
        question: savol (yoki savol namunasi).
        answer: shu savolga to'g'ri javob.
        tags: ixtiyoriy teglar (qidiruvni yaxshilaydi).
    """
    entry = knowledge_base.add(question, answer, tags or [])
    return f"✅ Bazaga qo'shildi (id={entry['id']}): {question}"


@mcp.tool(annotations=ToolAnnotations(title="List knowledge base", readOnlyHint=True))
async def kb_list() -> str:
    """Bazadagi barcha savol-javoblarni va statistikani ko'rsatadi."""
    st = knowledge_base.stats()
    entries = knowledge_base.load()
    head = (f"Baza: {st['count']} ta yozuv | fuzzy={st['fuzzy']} | "
            f"semantik={st['semantic']}")
    if not entries:
        return head + "\n(baza bo'sh — kb_add bilan javob qo'shing)"
    lines = [head]
    for e in entries:
        lines.append(f"  id={e.get('id')}: {e.get('q','')}  ->  {e.get('a','')}")
    return "\n".join(lines)


# --- Ishga tushirish / Entry point ----------------------------------------

def main():
    mcp.run()


if __name__ == "__main__":
    main()
