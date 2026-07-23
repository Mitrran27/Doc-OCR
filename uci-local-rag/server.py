# #!/usr/bin/env python3
# """
# server.py — FastAPI backend for the 2-page UCI app.

# Endpoints (matching the required contract):
#     POST /documents/upload  -> saves raw file + OCRs (if PDF) + ingests into ChromaDB
#     GET  /documents/        -> lists indexed documents with doc_id & metadata
#     POST /chat/             -> query + doc_id -> retrieve from Chroma -> generate via Qwen

# Run:
#     uvicorn server:app --reload --port 8020
# Then open http://localhost:8020 (Page 1 — upload/select) in a browser.
# """

# import shutil
# import traceback
# from pathlib import Path

# from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
# from fastapi.responses import FileResponse
# from fastapi.staticfiles import StaticFiles
# from pydantic import BaseModel

# import doc_store
# import ocr_bridge
# from rag_core import UciRag

# app = FastAPI(title="UCI — Document Upload & Chat")
# app.mount("/static", StaticFiles(directory="static"), name="static")

# rag = UciRag()  # loaded once at startup, reused across requests


# # ---------------------------------------------------------------- pages ----

# @app.get("/")
# def serve_page1():
#     return FileResponse("static/page1_upload.html")


# @app.get("/chat.html")
# def serve_page2():
#     return FileResponse("static/page2_chat.html")


# # ------------------------------------------------------------ documents ----

# ALLOWED_EXTENSIONS = {".pdf", ".md"}


# def _process_document(doc_id: str, saved_path: Path, standard: str):
#     """Runs in the background after upload responds, so the HTTP request
#     doesn't hang for the duration of OCR on a large PDF."""
#     try:
#         doc_store.update_document(doc_id, status="processing")

#         if saved_path.suffix.lower() == ".pdf":
#             kb_dir = ocr_bridge.ocr_and_split(saved_path, doc_id=doc_id, standard=standard)
#         else:  # .md — already OCR'd/clause-split content, e.g. from uci-ocr-pipeline's kb/UL864
#             kb_dir = saved_path.parent / f"{doc_id}_mdsource"
#             kb_dir.mkdir(exist_ok=True)
#             shutil.copy(saved_path, kb_dir / saved_path.name)

#         num_chunks = rag.ingest_markdown_dir(doc_id, kb_dir)
#         doc_store.update_document(doc_id, status="indexed", num_chunks=num_chunks)

#     except Exception as e:
#         traceback.print_exc()
#         doc_store.update_document(doc_id, status="failed", error=str(e))


# @app.post("/documents/upload")
# async def upload_document(
#     background_tasks: BackgroundTasks,
#     file: UploadFile = File(...),
#     standard: str = Form(default=""),
# ):
#     ext = Path(file.filename).suffix.lower()
#     if ext not in ALLOWED_EXTENSIONS:
#         raise HTTPException(400, f"Unsupported file type '{ext}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}")

#     doc_id = doc_store.create_document(filename=file.filename, standard=standard)

#     # Save raw file to local disk — stand-in for "saves raw file to S3" for
#     # now (see README). Swapping this line for an S3 upload later doesn't
#     # change anything else in this endpoint.
#     saved_path = doc_store.UPLOAD_DIR / f"{doc_id}_{file.filename}"
#     with open(saved_path, "wb") as f:
#         shutil.copyfileobj(file.file, f)

#     # OCR (if needed) + ingestion happens in the background — upload
#     # returns immediately so the UI can show a "processing" status and poll.
#     background_tasks.add_task(_process_document, doc_id, saved_path, standard)

#     return {"doc_id": doc_id, "filename": file.filename, "status": "uploaded"}


# @app.get("/documents/")
# def list_documents():
#     return doc_store.list_documents()


# # ------------------------------------------------------------------ chat ----

# class ChatRequest(BaseModel):
#     query: str
#     doc_id: str


# @app.post("/chat/")
# def chat(request: ChatRequest):
#     doc = doc_store.get_document(request.doc_id)
#     if doc is None:
#         raise HTTPException(404, f"Unknown doc_id: {request.doc_id}")
#     if doc["status"] != "indexed":
#         raise HTTPException(409, f"Document is not ready yet (status: {doc['status']})")

#     try:
#         result = rag.ask(request.query, request.doc_id)
#     except Exception as e:
#         raise HTTPException(500, str(e))

#     return {"answer": result["answer"], "sources": result["sources"]}



#!/usr/bin/env python3
"""
server.py — FastAPI backend for the 2-page UCI app.

Endpoints (matching the required contract):
    POST /documents/upload  -> saves raw file + OCRs (if PDF) + ingests into ChromaDB
    GET  /documents/        -> lists indexed documents with doc_id & metadata
    POST /chat/             -> query + doc_id -> retrieve from Chroma -> generate via Qwen

Run:
    uvicorn server:app --reload --port 8020
Then open http://localhost:8020 (Page 1 — upload/select) in a browser.
"""

import shutil
import traceback
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import doc_store
import ocr_bridge
from rag_core import UciRag

app = FastAPI(title="UCI — Document Upload & Chat")
app.mount("/static", StaticFiles(directory="static"), name="static")

rag = UciRag()  # loaded once at startup, reused across requests

# Only paths under these roots can ever be served via /images — prevents
# the endpoint from being used to read arbitrary files off the server.
ALLOWED_IMAGE_ROOTS = [
    (Path.home() / "uci-ocr-pipeline" / "kb").resolve(),
    (Path(__file__).parent / "kb_per_doc").resolve(),
]


# ---------------------------------------------------------------- pages ----

@app.get("/")
def serve_page1():
    return FileResponse("static/page1_upload.html")


@app.get("/chat.html")
def serve_page2():
    return FileResponse("static/page2_chat.html")


# ------------------------------------------------------------ documents ----

ALLOWED_EXTENSIONS = {".pdf", ".md"}


def _process_document(doc_id: str, saved_path: Path, standard: str):
    """Runs in the background after upload responds, so the HTTP request
    doesn't hang for the duration of OCR on a large PDF."""
    try:
        doc_store.update_document(doc_id, status="processing")

        if saved_path.suffix.lower() == ".pdf":
            kb_dir = ocr_bridge.ocr_and_split(saved_path, doc_id=doc_id, standard=standard)
        else:  # .md — already OCR'd/clause-split content, e.g. from uci-ocr-pipeline's kb/UL864
            kb_dir = saved_path.parent / f"{doc_id}_mdsource"
            kb_dir.mkdir(exist_ok=True)
            shutil.copy(saved_path, kb_dir / saved_path.name)

        num_chunks = rag.ingest_markdown_dir(doc_id, kb_dir)
        doc_store.update_document(doc_id, status="indexed", num_chunks=num_chunks)

    except Exception as e:
        traceback.print_exc()
        doc_store.update_document(doc_id, status="failed", error=str(e))


@app.post("/documents/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    standard: str = Form(default=""),
):
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type '{ext}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}")

    doc_id = doc_store.create_document(filename=file.filename, standard=standard)

    # Save raw file to local disk — stand-in for "saves raw file to S3" for
    # now (see README). Swapping this line for an S3 upload later doesn't
    # change anything else in this endpoint.
    saved_path = doc_store.UPLOAD_DIR / f"{doc_id}_{file.filename}"
    with open(saved_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # OCR (if needed) + ingestion happens in the background — upload
    # returns immediately so the UI can show a "processing" status and poll.
    background_tasks.add_task(_process_document, doc_id, saved_path, standard)

    return {"doc_id": doc_id, "filename": file.filename, "status": "uploaded"}


@app.get("/documents/")
def list_documents():
    return doc_store.list_documents()


# ------------------------------------------------------------------ images ----

@app.get("/images")
def get_image(path: str = Query(...)):
    """Serves a figure image extracted during OCR. Restricted to known kb
    directories only — see ALLOWED_IMAGE_ROOTS above."""
    resolved = Path(path).resolve()

    if not any(str(resolved).startswith(str(root)) for root in ALLOWED_IMAGE_ROOTS):
        raise HTTPException(403, "That path is outside the allowed image directories.")
    if not resolved.exists():
        raise HTTPException(404, "Image not found.")

    return FileResponse(resolved)


# ------------------------------------------------------------------ chat ----

class ChatRequest(BaseModel):
    query: str
    doc_id: str


@app.post("/chat/")
def chat(request: ChatRequest):
    doc = doc_store.get_document(request.doc_id)
    if doc is None:
        raise HTTPException(404, f"Unknown doc_id: {request.doc_id}")
    if doc["status"] != "indexed":
        raise HTTPException(409, f"Document is not ready yet (status: {doc['status']})")

    try:
        result = rag.ask(request.query, request.doc_id)
    except Exception as e:
        raise HTTPException(500, str(e))

    # Convert local file paths into URLs the frontend can actually load
    images = [
        {"url": f"/images?path={img['path']}", "caption": img["caption"]}
        for img in result["images"]
    ]

    return {"answer": result["answer"], "sources": result["sources"], "images": images}
