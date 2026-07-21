"""
Telegram MCP serveri uchun asosiy testlar.
Tarmoqqa ulanmaydi — faqat tool'lar to'g'ri ro'yxatga olinishini tekshiradi.
"""
import os
import asyncio
import importlib.util
import pathlib

# Import paytida majburiy bo'lgan qiymatlarni soxta o'rnatamiz
os.environ.setdefault("TELEGRAM_API_ID", "1")
os.environ.setdefault("TELEGRAM_API_HASH", "test_hash")

ROOT = pathlib.Path(__file__).resolve().parent.parent
os.environ.setdefault("TELEGRAM_SESSION", str(ROOT / "test_session"))

spec = importlib.util.spec_from_file_location("server", ROOT / "server.py")
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)

EXPECTED_TOOLS = {
    "send_message", "read_messages", "search_messages", "reply_message",
    "edit_message", "forward_message", "delete_message", "pin_message",
    "unpin_message", "react", "schedule_message", "mark_read",
    "send_file", "download_media", "get_me", "list_dialogs",
    "list_contacts", "resolve_entity", "send_to_channel", "create_group",
    "get_participants", "add_participants", "remove_participant",
    "promote_admin", "join_chat", "leave_chat",
    "answer_from_kb", "kb_add", "kb_list",
}


def _tools():
    return asyncio.run(server.mcp.list_tools())


def test_all_tools_registered():
    names = {t.name for t in _tools()}
    assert names == EXPECTED_TOOLS


def test_send_message_schema():
    sm = next(t for t in _tools() if t.name == "send_message")
    assert set(sm.inputSchema["properties"]) == {"peer", "text"}


def test_delete_requires_confirm_param():
    dm = next(t for t in _tools() if t.name == "delete_message")
    assert "confirm" in dm.inputSchema["properties"]


def test_kb_search_finds_relevant_answer():
    import kb
    # Namuna bazada "ish vaqti" haqida yozuv bor — boshqacha so'z bilan qidiramiz
    hits = kb.search("nechida ochilasiz soat", top_k=3)
    assert hits, "Bazadan natija topilishi kerak edi"
    # Eng yuqori natija ish vaqti haqidagi yozuv bo'lishi kerak
    assert "9:00" in hits[0]["a"]
