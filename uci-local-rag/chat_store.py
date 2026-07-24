# """
# conversation_store.py — persistent chat history, JSON-backed (same simple
# pattern as doc_store.py — good enough for a single-machine pilot, swap for
# a real DB later without changing the API contract in server.py).

# Each conversation belongs to exactly one doc_id and holds an ordered list
# of messages. Every assistant message stores its sources AND its images
# (the actual image URLs shown at the time), so reopening a past conversation
# shows exactly what was seen originally — it does not re-run retrieval.
# """

# import json
# import threading
# import uuid
# from datetime import datetime, timezone
# from pathlib import Path

# BASE_DIR = Path(__file__).parent
# DB_PATH = BASE_DIR / "conversations_db.json"

# _lock = threading.Lock()


# def _load() -> dict:
#     if not DB_PATH.exists():
#         return {}
#     return json.loads(DB_PATH.read_text(encoding="utf-8"))


# def _save(data: dict) -> None:
#     DB_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


# def create_conversation(doc_id: str) -> str:
#     conversation_id = uuid.uuid4().hex[:8]
#     with _lock:
#         data = _load()
#         data[conversation_id] = {
#             "conversation_id": conversation_id,
#             "doc_id": doc_id,
#             "title": None,  # set from the first user message once one arrives
#             "messages": [],
#             "created_at": datetime.now(timezone.utc).isoformat(),
#             "updated_at": datetime.now(timezone.utc).isoformat(),
#         }
#         _save(data)
#     return conversation_id


# def add_message(conversation_id: str, role: str, text: str, sources: list = None, images: list = None) -> None:
#     """role is 'user' or 'assistant'. sources/images are only meaningful for
#     assistant messages — stored as-given so history replays exactly what
#     was originally shown, not a freshly re-computed answer."""
#     with _lock:
#         data = _load()
#         conv = data.get(conversation_id)
#         if conv is None:
#             return

#         message = {"role": role, "text": text, "sources": sources or [], "images": images or []}
#         conv["messages"].append(message)
#         conv["updated_at"] = datetime.now(timezone.utc).isoformat()

#         if conv["title"] is None and role == "user":
#             conv["title"] = text[:80]

#         _save(data)


# def get_conversation(conversation_id: str) -> dict | None:
#     return _load().get(conversation_id)


# def list_conversations(doc_id: str = None) -> list[dict]:
#     """Returns lightweight summaries (no full message text) for the history
#     list — sorted most-recently-updated first."""
#     data = _load()
#     convs = list(data.values())
#     if doc_id:
#         convs = [c for c in convs if c["doc_id"] == doc_id]

#     convs.sort(key=lambda c: c["updated_at"], reverse=True)
#     return [
#         {
#             "conversation_id": c["conversation_id"],
#             "doc_id": c["doc_id"],
#             "title": c["title"] or "(new conversation)",
#             "message_count": len(c["messages"]),
#             "updated_at": c["updated_at"],
#         }
#         for c in convs
#     ]


# def delete_conversation(conversation_id: str) -> None:
#     with _lock:
#         data = _load()
#         data.pop(conversation_id, None)
#         _save(data)



"""
chat_store.py — lightweight local chat history registry.

Standing in for a real DB for now (same approach as doc_store.py): a JSON
file on disk mapping doc_id -> ordered list of chat messages. Good enough
for a single-machine pilot; swap for a real DB/table later without changing
the API contract in server.py.

Each message looks like:
    {
        "role": "user" | "assistant",
        "text": "...",
        "sources": [...],   # only populated for assistant messages
        "images": [...],    # only populated for assistant messages
        "at": "2026-07-24T09:15:00+00:00",
    }
"""

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).parent
CHAT_DB_PATH = BASE_DIR / "chat_history.json"

_lock = threading.Lock()


def _load() -> dict:
    if not CHAT_DB_PATH.exists():
        return {}
    return json.loads(CHAT_DB_PATH.read_text(encoding="utf-8"))


def _save(data: dict) -> None:
    CHAT_DB_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def append_message(
    doc_id: str,
    role: str,
    text: str,
    sources: list | None = None,
    images: list | None = None,
) -> None:
    with _lock:
        data = _load()
        data.setdefault(doc_id, [])
        data[doc_id].append({
            "role": role,
            "text": text,
            "sources": sources or [],
            "images": images or [],
            "at": datetime.now(timezone.utc).isoformat(),
        })
        _save(data)


def get_history(doc_id: str) -> list[dict]:
    return _load().get(doc_id, [])


def delete_history(doc_id: str) -> None:
    with _lock:
        data = _load()
        if doc_id in data:
            del data[doc_id]
            _save(data)
