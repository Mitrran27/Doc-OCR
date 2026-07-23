# UCI — 2-Page App (Upload & Chat)

Extends your local `uci-local-rag` pilot into the requested shape:

```
Page 1: Upload & Select Docs  ->  POST /documents/upload,  GET /documents/
Page 2: Chat Interface        ->  POST /chat/
```

Runs entirely on your own machine — same local stack as before (ChromaDB +
Qwen2.5 via Ollama), just reorganized behind a proper API and a real
multi-document flow instead of one hardcoded knowledge base.

## How this connects to your existing uci-ocr-pipeline repo

This is a **separate app**, in its own folder, with its own venv — but when
you upload a PDF, it calls out to your existing OCR pipeline directly:

- It runs `~/uci-ocr-pipeline/.venv/bin/mineru` **by its exact file path**,
  which works regardless of which venv this app's own server is running in.
- It imports `clause_splitter.py` straight from that repo (via `sys.path`),
  so clause-splitting logic isn't duplicated or copy-pasted — one source of
  truth, reused.

If you ever move `uci-ocr-pipeline` to a different location on disk, update
`OCR_PIPELINE_DIR` at the top of `ocr_bridge.py`.

## Setup

```bash
cd uci-local-rag-v2
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
ollama pull qwen2.5:1.5b   # skip if already pulled
```

## Register your already-OCR'd UL 864 content (skip re-uploading it)

You already ran the full 265-page OCR + QA earlier — no need to redo that
through the new upload flow:

```bash
python3 register_existing_kb.py \
  --kb-dir ~/uci-ocr-pipeline/kb/UL864 \
  --standard "UL 864" \
  --filename "UL864_Combined_Standard.pdf"
```

## Run the app

```bash
uvicorn server:app --reload --port 8020
```

Open **http://localhost:8020** — that's Page 1. Your registered UL 864
document should already show up with status `indexed`. Click **Chat →** to
go to Page 2 and start asking questions.

## Uploading a brand new document through the UI

- **.md files** (already clause-split, e.g. copied from a `kb/<STANDARD>/`
  folder) ingest almost instantly.
- **.pdf files** run through MinerU first — this can take a while for a
  large scan (your 265-page UL 864 run took a real chunk of time earlier),
  and runs as a background task so the upload request doesn't hang. Page 1
  polls every 4 seconds and flips the status from `uploaded` → `processing`
  → `indexed` (or `failed`, with the error shown on hover) automatically.

## API contract

| Endpoint | Method | Body | Returns |
|---|---|---|---|
| `/documents/upload` | POST | multipart form: `file`, `standard` | `{doc_id, filename, status}` |
| `/documents/` | GET | — | list of `{doc_id, filename, standard, status, num_chunks, error, uploaded_at}` |
| `/chat/` | POST | JSON: `{query, doc_id}` | `{answer, sources}` |

## Known limitations (pilot stage)

- **"Saves to S3"** is currently "saves to `uploaded_docs/` on local disk."
  Swapping in a real S3 upload only requires changing a few lines in
  `server.py`'s `upload_document()` — the rest of the flow doesn't change.
- **Document registry** is a JSON file (`documents_db.json`), not a real
  database — fine for a pilot, not for concurrent multi-user use.
- **Large PDF uploads through the UI can hit the same OOM risk** you saw
  earlier processing 265 images directly — uploading the full combined PDF
  is fine (goes through MinerU's PDF path, which handled it before); avoid
  uploading a raw folder of loose images through this flow.
- Answer quality depends on the same local embedding model + Qwen2.5
  limitations already noted in `uci-local-rag`'s README — this hasn't
  changed, just been reorganized into a proper multi-document app.
