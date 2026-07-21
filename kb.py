"""
Bilimlar bazasi (knowledge base) — gibrid qidiruv.
==================================================

Javoblar `knowledge.json` faylida saqlanadi:
  {"entries": [{"id": 1, "q": "savol", "a": "javob", "tags": ["teg"]}, ...]}

Qidiruv gibrid:
  1) Lexical  — token (so'z) mosligi (Jaccard)
  2) Fuzzy    — rapidfuzz orqali xato/boshqacha yozilishga chidamli moslik
  3) Semantik — IXTIYORIY: fastembed o'rnatilgan va TELEGRAM_KB_SEMANTIC=1
                bo'lsa, ma'no bo'yicha embedding cosine qo'shiladi.

Semantik yo'q bo'lsa, lexical+fuzzy avtomatik ishlaydi (hech narsa buzilmaydi).
"""

import os
import re
import json
import threading

_HERE = os.path.dirname(os.path.abspath(__file__))
KB_PATH = os.environ.get("TELEGRAM_KB_PATH") or os.path.join(_HERE, "knowledge.json")
SEMANTIC_ON = os.environ.get("TELEGRAM_KB_SEMANTIC", "").strip() in ("1", "true", "yes")
SEMANTIC_MODEL = os.environ.get("TELEGRAM_KB_MODEL", "intfloat/multilingual-e5-small")

_lock = threading.Lock()
_WORD_RE = re.compile(r"\w+", re.UNICODE)

# --- fuzzy (ixtiyoriy, lekin odatda mavjud) -------------------------------
try:
    from rapidfuzz import fuzz as _fuzz
except Exception:
    _fuzz = None

# --- semantik (ixtiyoriy) -------------------------------------------------
_embed_model = None
_embed_cache = {}  # id -> vector


def _tokens(text: str):
    return [t.lower() for t in _WORD_RE.findall(text or "")]


def _seed_if_missing():
    """knowledge.json bo'lmasa, namuna (knowledge.example.json) dan nusxa oladi."""
    if os.path.exists(KB_PATH):
        return
    example = os.path.join(_HERE, "knowledge.example.json")
    if os.path.exists(example):
        try:
            with open(example, encoding="utf-8") as f:
                data = f.read()
            with open(KB_PATH, "w", encoding="utf-8") as f:
                f.write(data)
        except Exception:
            pass


def load() -> list:
    """knowledge.json dan yozuvlarni o'qiydi (bo'lmasa namunadan seed qiladi)."""
    _seed_if_missing()
    if not os.path.exists(KB_PATH):
        return []
    try:
        with open(KB_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("entries", []) if isinstance(data, dict) else list(data)
    except Exception:
        return []


def save(entries: list):
    with _lock:
        with open(KB_PATH, "w", encoding="utf-8") as f:
            json.dump({"entries": entries}, f, ensure_ascii=False, indent=2)
    # baza o'zgardi -> embedding keshini tozalaymiz
    _embed_cache.clear()


def add(question: str, answer: str, tags=None) -> dict:
    """Bazaga yangi savol-javob qo'shadi va yozuvni qaytaradi."""
    entries = load()
    new_id = (max((e.get("id", 0) for e in entries), default=0) + 1)
    entry = {"id": new_id, "q": question, "a": answer, "tags": tags or []}
    entries.append(entry)
    save(entries)
    return entry


def _entry_text(e: dict) -> str:
    return " ".join([e.get("q", ""), e.get("a", ""), " ".join(e.get("tags", []))])


def _lexical_score(q_tokens, e: dict) -> float:
    e_tokens = set(_tokens(_entry_text(e)))
    if not e_tokens or not q_tokens:
        return 0.0
    inter = len(q_tokens & e_tokens)
    union = len(q_tokens | e_tokens)
    jaccard = inter / union if union else 0.0
    coverage = inter / len(q_tokens)  # savol so'zlarining qanchasi qamrab olindi
    return 0.5 * jaccard + 0.5 * coverage


def _fuzzy_score(query: str, e: dict) -> float:
    if _fuzz is None:
        return 0.0
    # savolga eng yaqin qismni topamiz (savol matni ustuvor)
    best = _fuzz.token_set_ratio(query, e.get("q", ""))
    best = max(best, _fuzz.partial_ratio(query, _entry_text(e)))
    return best / 100.0


# --- semantik yordamchi ---------------------------------------------------

def _get_model():
    global _embed_model
    if _embed_model is None:
        from fastembed import TextEmbedding
        _embed_model = TextEmbedding(model_name=SEMANTIC_MODEL)
    return _embed_model


def _vec(text: str):
    model = _get_model()
    return list(model.embed([text]))[0]


def _cosine(a, b) -> float:
    import math
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def _semantic_scores(query: str, entries: list) -> dict:
    """id -> cosine. fastembed yo'q bo'lsa bo'sh dict qaytadi."""
    if not SEMANTIC_ON:
        return {}
    try:
        qv = _vec(query)
    except Exception:
        return {}  # fastembed o'rnatilmagan yoki model yuklanmadi -> lexicalga qaytadi
    scores = {}
    for e in entries:
        eid = e.get("id")
        if eid not in _embed_cache:
            try:
                _embed_cache[eid] = _vec(_entry_text(e))
            except Exception:
                continue
        scores[eid] = _cosine(qv, _embed_cache[eid])
    return scores


def search(query: str, top_k: int = 3, min_score: float = 0.15) -> list:
    """
    Gibrid qidiruv. Har bir yozuvga ball beradi va eng yaxshi top_k ni qaytaradi.
    Qaytadi: [{id, q, a, tags, score}], balli kamaygan tartibda.
    """
    entries = load()
    if not entries:
        return []
    q_tokens = set(_tokens(query))
    sem = _semantic_scores(query, entries)

    ranked = []
    for e in entries:
        lex = _lexical_score(q_tokens, e)
        fuz = _fuzzy_score(query, e)
        base = 0.4 * lex + 0.6 * fuz
        if sem:
            s = sem.get(e.get("id"), 0.0)
            score = 0.5 * base + 0.5 * s
        else:
            score = base
        ranked.append((score, e))

    ranked.sort(key=lambda x: x[0], reverse=True)
    out = []
    for score, e in ranked[:top_k]:
        if score < min_score:
            continue
        out.append({**e, "score": round(float(score), 3)})
    return out


def stats() -> dict:
    entries = load()
    return {
        "path": KB_PATH,
        "count": len(entries),
        "fuzzy": _fuzz is not None,
        "semantic": bool(SEMANTIC_ON),
        "model": SEMANTIC_MODEL if SEMANTIC_ON else None,
    }
