#!/usr/bin/env python3
"""
register_existing_kb.py — one-time helper.

You already OCR'd and QA'd kb/UL864 with the old pipeline — no need to
re-upload or re-run OCR through the new app just to see it in Page 1.
This registers it directly as a document and ingests it into the shared
Chroma collection.

Usage:
    python3 register_existing_kb.py --kb-dir ~/uci-ocr-pipeline/kb/UL864 --standard "UL 864" --filename "UL864_Combined_Standard.pdf"
"""

import argparse
from pathlib import Path

import doc_store
from rag_core import UciRag


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--kb-dir", required=True, help="Path to an already-generated kb/<STANDARD> folder")
    parser.add_argument("--standard", required=True, help='e.g. "UL 864"')
    parser.add_argument("--filename", default="", help="Display name to show in the document list")
    args = parser.parse_args()

    kb_dir = Path(args.kb_dir)
    if not kb_dir.exists():
        raise SystemExit(f"Not found: {kb_dir}")

    filename = args.filename or kb_dir.name
    doc_id = doc_store.create_document(filename=filename, standard=args.standard)
    doc_store.update_document(doc_id, status="processing")

    print(f"Registered as doc_id={doc_id}. Ingesting into Chroma...")
    rag = UciRag()
    num_chunks = rag.ingest_markdown_dir(doc_id, kb_dir)
    doc_store.update_document(doc_id, status="indexed", num_chunks=num_chunks)

    print(f"Done. {num_chunks} chunks indexed. doc_id = {doc_id}")
    print("It will now show up in Page 1's document list.")


if __name__ == "__main__":
    main()
