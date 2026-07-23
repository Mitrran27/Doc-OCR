# """
# rag_core.py — shared retrieval + generation logic, multi-document version.

# All uploaded documents live in ONE Chroma collection, each chunk tagged
# with metadata["doc_id"]. Retrieval filters by doc_id so a chat session only
# ever searches the document the user selected on Page 1.
# """

# from pathlib import Path

# import chromadb
# import requests

# from chunking import chunk_body, parse_clause_file

# SYSTEM_PROMPT = """You are UCI, an internal research aid for engineers asking design questions \
# about the selected standard document.

# Rules you must always follow:
# - Answer ONLY using the context passages provided below. Do not use outside knowledge.
# - Always cite the exact clause number and source page for every factual claim you make, \
# using the format (Clause X.Y.Z, page N).
# - If the provided context does not contain a clear answer, say so directly instead of guessing.
# - Always end your answer with this exact line: \
# "Verify against the official standard before relying on this for compliance sign-off."
# """


# class UciRag:
#     def __init__(
#         self,
#         db_dir: str = "./chroma_db",
#         collection_name: str = "uci_documents",
#         embed_model: str = "all-MiniLM-L6-v2",
#         ollama_model: str = "qwen2.5:1.5b",
#         ollama_host: str = "http://localhost:11434",
#         top_k: int = 6,
#     ):
#         from sentence_transformers import SentenceTransformer  # imported lazily — slow to load

#         self.client = chromadb.PersistentClient(path=db_dir)
#         self.collection = self.client.get_or_create_collection(collection_name)
#         self.embedder = SentenceTransformer(embed_model)
#         self.ollama_model = ollama_model
#         self.ollama_host = ollama_host
#         self.top_k = top_k

#     # ---- ingestion (called from server.py's /documents/upload) ----

#     def ingest_markdown_dir(self, doc_id: str, kb_dir: Path) -> int:
#         """Chunks + embeds every .md file in kb_dir and upserts into the
#         shared collection, tagged with this doc_id. Returns chunk count."""
#         md_files = sorted(f for f in Path(kb_dir).glob("*.md") if f.name != "00-index.md")

#         ids, documents, metadatas = [], [], []
#         for f in md_files:
#             parsed = parse_clause_file(f)
#             for i, chunk in enumerate(chunk_body(parsed["body"])):
#                 if not chunk.strip():
#                     continue
#                 ids.append(f"{doc_id}-{f.stem}-{i}")
#                 documents.append(chunk)
#                 metadatas.append({
#                     "doc_id": doc_id,
#                     "standard": parsed.get("standard", ""),
#                     "clause": parsed.get("clause", ""),
#                     "title": parsed.get("title", ""),
#                     "source_pages": parsed.get("source_pages", ""),
#                     "filename": f.name,
#                 })

#         if not documents:
#             return 0

#         embeddings = self.embedder.encode(documents, show_progress_bar=False).tolist()

#         batch_size = 500
#         for i in range(0, len(ids), batch_size):
#             self.collection.upsert(
#                 ids=ids[i:i + batch_size],
#                 documents=documents[i:i + batch_size],
#                 embeddings=embeddings[i:i + batch_size],
#                 metadatas=metadatas[i:i + batch_size],
#             )

#         return len(documents)

#     def delete_document(self, doc_id: str) -> None:
#         self.collection.delete(where={"doc_id": doc_id})

#     # ---- retrieval + generation (called from server.py's /chat/) ----

#     def retrieve(self, question: str, doc_id: str) -> list[dict]:
#         query_embedding = self.embedder.encode([question]).tolist()
#         results = self.collection.query(
#             query_embeddings=query_embedding,
#             n_results=self.top_k,
#             where={"doc_id": doc_id},
#         )

#         chunks = []
#         docs = results["documents"][0] if results["documents"] else []
#         metas = results["metadatas"][0] if results["metadatas"] else []
#         for doc, meta in zip(docs, metas):
#             chunks.append({"text": doc, "meta": meta})
#         return chunks

#     def generate(self, question: str, chunks: list[dict]) -> str:
#         context_blocks = []
#         for c in chunks:
#             m = c["meta"]
#             context_blocks.append(
#                 f"[Clause {m['clause']} — {m['title']} — page(s) {m['source_pages']}]\n{c['text']}"
#             )
#         context_text = "\n\n---\n\n".join(context_blocks) if context_blocks else "(no relevant context found)"

#         prompt = f"{SYSTEM_PROMPT}\n\nContext:\n{context_text}\n\nQuestion: {question}\n\nAnswer:"

#         response = requests.post(
#             f"{self.ollama_host}/api/generate",
#             json={"model": self.ollama_model, "prompt": prompt, "stream": False},
#             timeout=180,
#         )
#         response.raise_for_status()
#         return response.json()["response"].strip()

#     def ask(self, question: str, doc_id: str) -> dict:
#         chunks = self.retrieve(question, doc_id)
#         answer = self.generate(question, chunks)
#         return {
#             "answer": answer,
#             "sources": [
#                 {"clause": c["meta"]["clause"], "title": c["meta"]["title"], "pages": c["meta"]["source_pages"]}
#                 for c in chunks
#             ],
#         }




"""
rag_core.py — shared retrieval + generation logic, multi-document version.

CHANGES:
- System prompt now explicitly instructs the model to answer only for
  United States requirements and to disregard any Canada-specific content
  (defense in depth — the primary guarantee is that Canada-only text is
  already stripped at ingestion time in chunking.py, so it usually isn't
  even in the retrieved context to begin with).
- ingest_markdown_dir() now resolves and stores image file paths per chunk.
- ask() returns a deduplicated "images" list alongside "sources", so the
  frontend can render figures relevant to the retrieved context.
"""

import re
from pathlib import Path

import chromadb
import requests

from chunking import chunk_body, extract_image_refs, parse_clause_file

# Deterministic guard for Canada-related QUESTIONS (as opposed to Canada-only
# CONTENT, which is handled separately at ingestion time in chunking.py).
# A 1.5B local model can't be trusted to reliably follow a negative
# instruction like "don't speculate about Canada" every time — when asked a
# Canada-shaped question with no Canada content in its retrieved context, it
# will sometimes fill the gap with a plausible-sounding hallucination instead
# of saying it doesn't know. So we intercept the question itself before it
# ever reaches retrieval or generation, and return a fixed refusal.
CANADA_QUERY_RE = re.compile(r"\bcanad(?:a|ian)\b", re.IGNORECASE)

OUT_OF_SCOPE_MESSAGE = (
    "That's out of my bounds — this assistant is tailored to United States "
    "specifications only and does not provide Canada-specific requirements "
    "or comparisons.\n\n"
    "Verify against the official standard before relying on this for compliance sign-off."
)

SYSTEM_PROMPT = """You are UCI, an internal research aid for engineers asking design questions \
about the selected standard document.

Rules you must always follow:
- Answer ONLY using the context passages provided below. Do not use outside knowledge.
- This document may contain requirements for multiple countries. Answer ONLY for United \
States requirements. If a passage is specific to Canada (e.g. marked "In Canada only"), \
disregard it entirely — do not mention it, compare it, or let it influence your answer.
- Always cite the exact clause number and source page for every factual claim you make, \
using the format (Clause X.Y.Z, page N).
- If the provided context does not contain a clear answer for the US requirement, say so \
directly instead of guessing.
- Always end your answer with this exact line: \
"Verify against the official standard before relying on this for compliance sign-off."
"""


class UciRag:
    def __init__(
        self,
        db_dir: str = "./chroma_db",
        collection_name: str = "uci_documents",
        embed_model: str = "all-MiniLM-L6-v2",
        ollama_model: str = "qwen2.5:1.5b",
        ollama_host: str = "http://localhost:11434",
        top_k: int = 6,
    ):
        from sentence_transformers import SentenceTransformer  # imported lazily — slow to load

        self.client = chromadb.PersistentClient(path=db_dir)
        self.collection = self.client.get_or_create_collection(collection_name)
        self.embedder = SentenceTransformer(embed_model)
        self.ollama_model = ollama_model
        self.ollama_host = ollama_host
        self.top_k = top_k

    # ---- ingestion ----

    def ingest_markdown_dir(self, doc_id: str, kb_dir: Path) -> int:
        kb_dir = Path(kb_dir)
        md_files = sorted(f for f in kb_dir.glob("*.md") if f.name != "00-index.md")

        ids, documents, metadatas = [], [], []
        for f in md_files:
            parsed = parse_clause_file(f)
            for i, chunk in enumerate(chunk_body(parsed["body"])):
                if not chunk.strip():
                    continue

                # Resolve relative image paths (e.g. "images/19-3_fig1.jpg")
                # to absolute paths on disk, relative to this clause file's
                # own kb_dir — stored "||"-joined since Chroma metadata
                # values must be simple scalars, not lists.
                image_refs = extract_image_refs(chunk)
                abs_images = [str((kb_dir / rel).resolve()) for rel in image_refs]

                ids.append(f"{doc_id}-{f.stem}-{i}")
                documents.append(chunk)
                metadatas.append({
                    "doc_id": doc_id,
                    "standard": parsed.get("standard", ""),
                    "clause": parsed.get("clause", ""),
                    "title": parsed.get("title", ""),
                    "source_pages": parsed.get("source_pages", ""),
                    "filename": f.name,
                    "images": "||".join(abs_images),
                })

        if not documents:
            return 0

        embeddings = self.embedder.encode(documents, show_progress_bar=False).tolist()

        batch_size = 500
        for i in range(0, len(ids), batch_size):
            self.collection.upsert(
                ids=ids[i:i + batch_size],
                documents=documents[i:i + batch_size],
                embeddings=embeddings[i:i + batch_size],
                metadatas=metadatas[i:i + batch_size],
            )

        return len(documents)

    def delete_document(self, doc_id: str) -> None:
        self.collection.delete(where={"doc_id": doc_id})

    # ---- retrieval + generation ----

    def retrieve(self, question: str, doc_id: str) -> list[dict]:
        query_embedding = self.embedder.encode([question]).tolist()
        results = self.collection.query(
            query_embeddings=query_embedding,
            n_results=self.top_k,
            where={"doc_id": doc_id},
        )

        chunks = []
        docs = results["documents"][0] if results["documents"] else []
        metas = results["metadatas"][0] if results["metadatas"] else []
        for doc, meta in zip(docs, metas):
            chunks.append({"text": doc, "meta": meta})
        return chunks

    def generate(self, question: str, chunks: list[dict]) -> str:
        context_blocks = []
        for c in chunks:
            m = c["meta"]
            context_blocks.append(
                f"[Clause {m['clause']} — {m['title']} — page(s) {m['source_pages']}]\n{c['text']}"
            )
        context_text = "\n\n---\n\n".join(context_blocks) if context_blocks else "(no relevant context found)"

        prompt = f"{SYSTEM_PROMPT}\n\nContext:\n{context_text}\n\nQuestion: {question}\n\nAnswer:"

        response = requests.post(
            f"{self.ollama_host}/api/generate",
            json={"model": self.ollama_model, "prompt": prompt, "stream": False},
            timeout=180,
        )
        response.raise_for_status()
        return response.json()["response"].strip()

    def ask(self, question: str, doc_id: str) -> dict:
        if CANADA_QUERY_RE.search(question):
            return {"answer": OUT_OF_SCOPE_MESSAGE, "sources": [], "images": []}

        chunks = self.retrieve(question, doc_id)
        answer = self.generate(question, chunks)

        seen_images = set()
        images = []
        for c in chunks:
            raw = c["meta"].get("images", "")
            if not raw:
                continue
            for path in raw.split("||"):
                if path and path not in seen_images and Path(path).exists():
                    seen_images.add(path)
                    images.append({
                        "path": path,
                        "clause": c["meta"]["clause"],
                        "caption": f"Clause {c['meta']['clause']} — {c['meta']['title']}",
                    })

        return {
            "answer": answer,
            "sources": [
                {"clause": c["meta"]["clause"], "title": c["meta"]["title"], "pages": c["meta"]["source_pages"]}
                for c in chunks
            ],
            "images": images,
        }
