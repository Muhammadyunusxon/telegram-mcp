#!/usr/bin/env python3
"""
Telegram realtime auto-responder (bilimlar bazasidan AI javob).
================================================================

Doim ishlab turadigan skript. Kelayotgan xabarni eshitadi, javoblar bazasidan
(knowledge.json) qidiradi va FAQAT ishonchli mos javob topilsa, uni Claude API
orqali tabiiy tilda yozib avtomatik javob yuboradi.

XAVFSIZLIK (o'rnatilgan):
  - Faqat ALLOWLIST'dagi chatlarga javob beradi (AUTORESPONDER_CHATS majburiy).
  - Faqat baza balli chegaradan yuqori bo'lsa yozadi (aks holda jim turadi).
  - O'z xabarlariga va boshqa botlarga javob bermaydi.
  - Har bir chatga qisqa "cooldown" (spam bo'lmasligi uchun).

Kerakli muhit o'zgaruvchilari:
  TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_SESSION  (server bilan bir xil)
  AUTORESPONDER_CHATS     - MAJBURIY. Vergul bilan: @username yoki chat ID.
  ANTHROPIC_API_KEY       - AI javob uchun (bo'lmasa bazadagi javob aynan yuboriladi).
  AUTORESPONDER_MODEL     - default "claude-3-5-haiku-latest"
  AUTORESPONDER_MIN_SCORE - ishonch chegarasi, default 0.35
  AUTORESPONDER_COOLDOWN  - bitta chatga javoblar orasidagi minimal soniya, default 5

Ishga tushirish:
  AUTORESPONDER_CHATS="@mijozlarim" ANTHROPIC_API_KEY="sk-..." python3 autoresponder.py

Sinov (Telegram/API'siz, faqat bazani tekshirish):
  python3 autoresponder.py --test "savol matni"
"""

import os
import sys
import time
import asyncio
import logging

import kb as knowledge_base

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except Exception:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("autoresponder")

MIN_SCORE = float(os.environ.get("AUTORESPONDER_MIN_SCORE", "0.35"))
COOLDOWN = float(os.environ.get("AUTORESPONDER_COOLDOWN", "5"))
MODEL = os.environ.get("AUTORESPONDER_MODEL", "claude-3-5-haiku-latest")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

# LLM backend: auto | anthropic | ollama | none
#   auto  -> API kalit bo'lsa Anthropic, bo'lmasa lokal Ollama, u ham bo'lmasa
#            bazadagi javob aynan yuboriladi.
LLM_BACKEND = os.environ.get("AUTORESPONDER_LLM", "auto").lower()
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")

_allowed_raw = {
    p.strip().lstrip("@").lower()
    for p in os.environ.get("AUTORESPONDER_CHATS", "").split(",")
    if p.strip()
}

_last_reply = {}  # chat_id -> timestamp (cooldown uchun)


# --- Javob matnini tayyorlash ---------------------------------------------

_anthropic = None


def _prompt(question: str, hits: list) -> str:
    context = "\n".join(f"- S: {h.get('q','')}\n  J: {h.get('a','')}" for h in hits)
    return (
        "Sen mijozlarga yordam beradigan qisqa va samimiy yordamchisan. "
        "Quyidagi bilimlar bazasidagi javoblarga TAYANIB, mijoz savoliga "
        "tabiiy, do'stona javob yoz. Faqat shu ma'lumotdan foydalan — "
        "yangi narsa to'qib chiqarma. Mijoz qaysi tilda yozgan bo'lsa, "
        "o'sha tilda javob ber.\n\n"
        f"Bilimlar bazasi:\n{context}\n\n"
        f"Mijoz savoli: {question}\n\n"
        "Javob (qisqa, 1-3 gap):"
    )


def _choose_backend() -> str:
    if LLM_BACKEND in ("anthropic", "ollama", "none"):
        return LLM_BACKEND
    # auto
    if ANTHROPIC_API_KEY:
        return "anthropic"
    if _ollama_ready():
        return "ollama"
    return "none"


def _ollama_ready() -> bool:
    import urllib.request
    try:
        with urllib.request.urlopen(OLLAMA_URL + "/api/tags", timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def _ollama_generate(prompt: str) -> str:
    import json
    import urllib.request
    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }).encode()
    req = urllib.request.Request(
        OLLAMA_URL + "/api/chat", data=payload,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.load(r)
    return (data.get("message", {}) or {}).get("content", "").strip()


def _get_anthropic():
    global _anthropic
    if _anthropic is None:
        from anthropic import Anthropic
        _anthropic = Anthropic(api_key=ANTHROPIC_API_KEY)
    return _anthropic


def _anthropic_generate(prompt: str) -> str:
    client = _get_anthropic()
    msg = client.messages.create(
        model=MODEL, max_tokens=300,
        messages=[{"role": "user", "content": prompt}])
    return msg.content[0].text.strip()


def build_reply(question: str, hits: list) -> str:
    """
    KB natijalaridan javob matnini yasaydi. Backend:
      anthropic -> Claude API (kalit kerak)
      ollama    -> lokal model (bepul, API kalitsiz)
      none      -> bazadagi javob aynan
    Xatolik bo'lsa har doim bazadagi javobga qaytadi.
    """
    backend = _choose_backend()
    if backend == "none":
        return hits[0].get("a", "")
    prompt = _prompt(question, hits)
    try:
        if backend == "anthropic":
            return _anthropic_generate(prompt) or hits[0].get("a", "")
        if backend == "ollama":
            return _ollama_generate(prompt) or hits[0].get("a", "")
    except Exception as e:
        log.warning(f"AI javob xatosi ({backend}: {e.__class__.__name__}): "
                    f"bazadagi javob yuboriladi")
    return hits[0].get("a", "")


# --- Telegram real-time listener ------------------------------------------

def _is_allowed(chat_id, username) -> bool:
    ident = {str(chat_id).lower()}
    if username:
        ident.add(username.lower())
    return not ident.isdisjoint(_allowed_raw)


async def run():
    from telethon import TelegramClient, events

    api_id = os.environ.get("TELEGRAM_API_ID")
    api_hash = os.environ.get("TELEGRAM_API_HASH")
    session = os.environ.get("TELEGRAM_SESSION", "telegram_mcp")
    if not os.path.isabs(session):
        session = os.path.join(os.path.dirname(os.path.abspath(__file__)), session)

    if not api_id or not api_hash:
        log.error("TELEGRAM_API_ID / TELEGRAM_API_HASH yo'q. .env ni tekshiring.")
        return
    if not _allowed_raw:
        log.error("AUTORESPONDER_CHATS bo'sh! Xavfsizlik uchun allowlist MAJBURIY. "
                  "Masalan: AUTORESPONDER_CHATS=\"@mijozlarim,123456789\"")
        return

    client = TelegramClient(session, int(api_id), api_hash)

    @client.on(events.NewMessage(incoming=True))
    async def handler(event):
        try:
            # botlarга va servis xabarlarga javob bermaymiz
            if event.via_bot_id or not event.raw_text:
                return
            sender = await event.get_sender()
            if getattr(sender, "bot", False):
                return
            chat = await event.get_chat()
            username = getattr(chat, "username", None)
            if not _is_allowed(event.chat_id, username):
                return

            # cooldown
            now = time.time()
            if now - _last_reply.get(event.chat_id, 0) < COOLDOWN:
                return

            question = event.raw_text.strip()
            hits = knowledge_base.search(question, top_k=3)
            if not hits or hits[0]["score"] < MIN_SCORE:
                log.info(f"[{event.chat_id}] mos javob yo'q (jim) — {question[:40]!r}")
                return

            reply = build_reply(question, hits)
            if not reply:
                return
            await event.reply(reply)
            _last_reply[event.chat_id] = now
            log.info(f"[{event.chat_id}] javob yuborildi "
                     f"(ball {hits[0]['score']}) — {question[:40]!r}")
        except Exception as e:
            log.warning(f"handler xatosi: {e.__class__.__name__}: {e}")

    await client.start()
    me = await client.get_me()
    log.info(f"✅ Auto-responder ishga tushdi. Akkaunt: {me.first_name} "
             f"(@{me.username or '—'})")
    backend = _choose_backend()
    backend_desc = {
        "anthropic": f"Anthropic API ({MODEL})",
        "ollama": f"Lokal Ollama ({OLLAMA_MODEL})",
        "none": "AI yo'q (bazadagi javob aynan)",
    }.get(backend, backend)
    log.info(f"Allowlist: {sorted(_allowed_raw)} | min_score={MIN_SCORE} | "
             f"backend={backend_desc}")
    log.info("Kutyapman... (to'xtatish uchun Ctrl+C)")
    await client.run_until_disconnected()


# --- Sinov rejimi (Telegram'siz) ------------------------------------------

def _test(question: str):
    hits = knowledge_base.search(question, top_k=3)
    print(f"Savol: {question}")
    if not hits or hits[0]["score"] < MIN_SCORE:
        print(f"-> Mos javob yo'q (eng yuqori ball "
              f"{hits[0]['score'] if hits else 0} < {MIN_SCORE}). Jim turadi.")
        return
    print(f"-> Topildi (ball {hits[0]['score']}). Javob:")
    print(build_reply(question, hits))


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--test":
        _test(" ".join(sys.argv[2:]))
    else:
        try:
            asyncio.run(run())
        except KeyboardInterrupt:
            log.info("To'xtatildi.")
