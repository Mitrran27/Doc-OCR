# """
# chunking.py — shared markdown parsing + chunking logic.

# Used by both ingest.py (bulk, one-shot ingestion of an existing kb/ folder)
# and server.py (per-document ingestion on upload), so the two stay consistent.
# """

# import re
# from pathlib import Path


# def parse_clause_file(path: Path) -> dict:
#     """Split a clause .md file into its frontmatter dict + body text."""
#     text = path.read_text(encoding="utf-8")
#     match = re.match(r"^---\n(.*?)\n---\n\n?(.*)$", text, re.DOTALL)
#     if not match:
#         return {"standard": "", "clause": "", "title": path.stem, "source_pages": "", "body": text}

#     frontmatter_raw, body = match.groups()
#     meta = {}
#     for line in frontmatter_raw.split("\n"):
#         if ":" in line:
#             key, _, value = line.partition(":")
#             meta[key.strip()] = value.strip()
#     meta["body"] = body.strip()
#     return meta


# def chunk_body(body: str, max_chars: int = 1500) -> list[str]:
#     """Simple paragraph-aware chunking. Keeps chunks under max_chars,
#     splitting on blank lines (paragraph boundaries) rather than mid-sentence."""
#     if len(body) <= max_chars:
#         return [body] if body else []

#     paragraphs = body.split("\n\n")
#     chunks, current = [], ""
#     for para in paragraphs:
#         if len(current) + len(para) + 2 <= max_chars:
#             current = f"{current}\n\n{para}" if current else para
#         else:
#             if current:
#                 chunks.append(current)
#             current = para
#     if current:
#         chunks.append(current)
#     return chunks



"""
chunking.py — shared markdown parsing + chunking logic.

- strip_canada_only(): removes any PARAGRAPH containing "in canada only",
  so Canada-specific content can never enter the vector DB and can never
  be retrieved — a stronger guarantee than just prompting the LLM to
  ignore it. Paragraph-level substring matching (not line-start regex
  anchoring) so it catches real phrasings like "3) In Canada only: ..."
  and "b) In Canada only: ..." where the phrase isn't the first thing on
  the line.
- is_canada_only_clause(): whole clause files whose TITLE itself is
  Canada-specific (e.g. "In Canada only: Remote connection functions")
  are skipped entirely, not just filtered sentence-by-sentence.
- extract_image_refs(): pulls out markdown image paths (![...](images/x.jpg))
  from a chunk's text so they can be surfaced back through the chat UI.
"""

import re
from pathlib import Path

IMAGE_REF_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")

CANADA_MARKER = "in canada only"


def strip_canada_only(text: str) -> str:
    """Removes every paragraph that mentions 'in canada only' anywhere in
    it (case-insensitive) — not just when the phrase starts the line.
    Paragraphs are split on blank lines, matching how clause_splitter.py
    joins blocks (body_lines joined with "\\n\\n")."""
    paragraphs = text.split("\n\n")
    kept = [p for p in paragraphs if CANADA_MARKER not in p.lower()]
    return "\n\n".join(kept)


def is_canada_only_clause(title: str) -> bool:
    """True if the clause's own title marks it as Canada-specific — the
    whole file should be skipped, not just individual sentences within it."""
    return CANADA_MARKER in (title or "").lower()


def extract_image_refs(text: str) -> list[str]:
    """Returns the relative image paths (e.g. 'images/19-3_fig1.jpg')
    referenced via markdown image syntax in this chunk's text."""
    return IMAGE_REF_RE.findall(text)


def parse_clause_file(path: Path) -> dict:
    """Split a clause .md file into its frontmatter dict + body text.
    Canada-only content is stripped here, before chunking — this is the one
    place all ingestion paths (bulk ingest.py, per-doc upload) funnel through."""
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n\n?(.*)$", text, re.DOTALL)
    if not match:
        return {"standard": "", "clause": "", "title": path.stem, "source_pages": "", "body": strip_canada_only(text)}

    frontmatter_raw, body = match.groups()
    meta = {}
    for line in frontmatter_raw.split("\n"):
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()

    title = meta.get("title", "")
    if is_canada_only_clause(title):
        # Whole clause is Canada-specific (e.g. title itself says
        # "In Canada only: ...") — exclude it entirely from ingestion.
        meta["body"] = ""
    else:
        meta["body"] = strip_canada_only(body.strip())

    return meta


def chunk_body(body: str, max_chars: int = 1500) -> list[str]:
    """Simple paragraph-aware chunking. Keeps chunks under max_chars,
    splitting on blank lines (paragraph boundaries) rather than mid-sentence."""
    if len(body) <= max_chars:
        return [body] if body else []

    paragraphs = body.split("\n\n")
    chunks, current = [], ""
    for para in paragraphs:
        if len(current) + len(para) + 2 <= max_chars:
            current = f"{current}\n\n{para}" if current else para
        else:
            if current:
                chunks.append(current)
            current = para
    if current:
        chunks.append(current)
    return chunks


def chunk_body(body: str, max_chars: int = 1500) -> list[str]:
    """Simple paragraph-aware chunking. Keeps chunks under max_chars,
    splitting on blank lines (paragraph boundaries) rather than mid-sentence."""
    if len(body) <= max_chars:
        return [body] if body else []

    paragraphs = body.split("\n\n")
    chunks, current = [], ""
    for para in paragraphs:
        if len(current) + len(para) + 2 <= max_chars:
            current = f"{current}\n\n{para}" if current else para
        else:
            if current:
                chunks.append(current)
            current = para
    if current:
        chunks.append(current)
    return chunks