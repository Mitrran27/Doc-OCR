"""
doc_store.py — lightweight local document registry.

Standing in for a real database for now: just a JSON file on disk tracking
every uploaded document's id, filename, standard, status, and chunk count.
Good enough for a single-machine pilot; swap for a real DB/table later
without changing the API contract in server.py.
"""

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "documents_db.json"
UPLOAD_DIR = BASE_DIR / "uploaded_docs"  # stand-in for S3 for now — see README

UPLOAD_DIR.mkdir(exist_ok=True)
_lock = threading.Lock()


def _load() -> dict:
    if not DB_PATH.exists():
        return {}
    return json.loads(DB_PATH.read_text(encoding="utf-8"))


def _save(data: dict) -> None:
    DB_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def create_document(filename: str, standard: str = "") -> str:
    doc_id = uuid.uuid4().hex[:8]
    with _lock:
        data = _load()
        data[doc_id] = {
            "doc_id": doc_id,
            "filename": filename,
            "standard": standard,
            "status": "uploaded",  # uploaded -> processing -> indexed -> failed
            "num_chunks": 0,
            "error": None,
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        }
        _save(data)
    return doc_id


def update_document(doc_id: str, **fields) -> None:
    with _lock:
        data = _load()
        if doc_id in data:
            data[doc_id].update(fields)
            _save(data)


def get_document(doc_id: str) -> dict | None:
    return _load().get(doc_id)


def list_documents() -> list[dict]:
    return sorted(_load().values(), key=lambda d: d["uploaded_at"], reverse=True)
