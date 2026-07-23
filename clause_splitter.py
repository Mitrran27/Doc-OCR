"""
clause_splitter.py

Splits MinerU's per-page JSON blocks into per-clause markdown files matching
the UCI KB schema (charter §6):

    ---
    standard: UL 864
    edition/year: 2020, 11th Ed.
    clause: 19.3.2
    title: Power Supply — Standby Battery Capacity
    source_pages: 142-144
    ---

    <clause body as markdown, tables preserved, figures embedded as images>

CHANGE FROM PREVIOUS VERSION: image blocks used to become a text-only
placeholder like "[Figure — see source page 103]", discarding the actual
extracted image file. This version copies the real image into
<kb_dir>/images/ and embeds it with markdown image syntax, so it can later
be displayed in the chat UI. This is backward compatible — pass no
assets_dir and you get the old placeholder-only behavior.
"""

import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from slugify_util import slugify

CLAUSE_HEADING_RE = re.compile(
    r"^(?:SECTION\s+)?(\d{1,3}(?:\.\d{1,3}){0,3})\s*[-–—:]?\s*(.+)$",
    re.IGNORECASE,
)


@dataclass
class Clause:
    number: str
    title: str
    body_lines: list = field(default_factory=list)
    pages: set = field(default_factory=set)

    @property
    def page_range(self) -> str:
        if not self.pages:
            return "unknown"
        lo, hi = min(self.pages), max(self.pages)
        return f"{lo + 1}-{hi + 1}" if lo != hi else str(lo + 1)


def _table_to_markdown(block: dict) -> str:
    """MinerU's pipeline backend typically returns table_body as HTML.
    Passed through as-is here; swap in an HTML->MD converter (e.g.
    `markdownify`) if you want tables rendered as markdown tables instead."""
    body = (block.get("table_body") or block.get("text") or "").strip()
    caption = " ".join(block.get("table_caption", [])) if block.get("table_caption") else ""
    if caption:
        return f"**Table: {caption}**\n\n{body}"
    return body


def _copy_image_and_embed(block: dict, page_idx: int, kb_dir: Path, assets_dir: Path | None, clause_number: str) -> str:
    """Copies the real image file (if assets_dir is given) into
    <kb_dir>/images/ and returns markdown image syntax referencing it.
    Falls back to the old text-only placeholder if assets_dir is None or
    the source image can't be found."""
    page = page_idx + 1
    img_path = block.get("img_path")

    if not assets_dir or not img_path:
        return f"[Figure — see source page {page}]"

    src = (assets_dir / img_path).resolve()
    if not src.exists():
        return f"[Figure — see source page {page}] (image file not found: {img_path})"

    images_dir = kb_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    # Prefix with clause number to avoid filename collisions across clauses
    safe_clause = clause_number.replace(".", "-")
    dest_name = f"{safe_clause}_{src.name}"
    dest = images_dir / dest_name
    shutil.copy(src, dest)

    caption = block.get("img_caption") or f"Figure — page {page}"
    if isinstance(caption, list):  # MinerU sometimes returns caption as a list of lines
        caption = " ".join(caption)
    return f"![{caption}](images/{dest_name})"


def split_into_clauses(blocks: list, kb_dir: Path = None, assets_dir: Path = None) -> list:
    """Walk the flat, page-ordered MinerU block list and group blocks under
    detected clause headings.

    kb_dir/assets_dir are optional — pass both to enable image copying;
    omit them (or pass kb_dir=None) to get the old text-placeholder-only
    behavior for image blocks."""
    clauses: list = []
    current = Clause(number="00", title="Front Matter / Unclaused Content")

    for block in blocks:
        page_idx = block.get("page_idx", 0)
        block_type = block.get("type")

        if block_type == "text":
            text = (block.get("text") or "").strip()
            if not text:
                continue

            text_level = block.get("text_level")  # None for body text, 1/2/3 for headings
            if text_level is not None and text_level <= 2:
                match = CLAUSE_HEADING_RE.match(text)
                if match:
                    if current.body_lines or current.number != "00":
                        clauses.append(current)
                    number, title = match.group(1), match.group(2).strip()
                    current = Clause(number=number, title=title)
                    current.pages.add(page_idx)
                    continue
                else:
                    current.body_lines.append(f"### {text}")
                    current.pages.add(page_idx)
                    continue

            current.body_lines.append(text)
            current.pages.add(page_idx)

        elif block_type == "table":
            current.body_lines.append(_table_to_markdown(block))
            current.pages.add(page_idx)

        elif block_type == "image":
            embed = _copy_image_and_embed(block, page_idx, kb_dir, assets_dir, current.number) if kb_dir else f"[Figure — see source page {page_idx + 1}]"
            current.body_lines.append(embed)
            current.pages.add(page_idx)

        elif block_type == "equation":
            latex = (block.get("text") or "").strip()
            current.body_lines.append(f"$$ {latex} $$")
            current.pages.add(page_idx)

    if current.body_lines:
        clauses.append(current)

    return clauses


def write_kb_files(clauses: list, kb_dir: Path, standard_name: str, edition: str) -> None:
    kb_dir = Path(kb_dir)
    kb_dir.mkdir(parents=True, exist_ok=True)
    index_rows = []

    for clause in clauses:
        filename = f"section-{clause.number.split('.')[0]}-{slugify(clause.title)}.md"
        filepath = kb_dir / filename
        if filepath.exists():
            filepath = kb_dir / f"section-{clause.number.replace('.', '-')}-{slugify(clause.title)}.md"

        frontmatter = (
            "---\n"
            f"standard: {standard_name}\n"
            f"edition/year: {edition}\n"
            f"clause: {clause.number}\n"
            f"title: {clause.title}\n"
            f"source_pages: {clause.page_range}\n"
            "---\n\n"
        )
        body = "\n\n".join(clause.body_lines)
        filepath.write_text(frontmatter + body, encoding="utf-8")
        index_rows.append((clause.number, clause.title, filepath.name, clause.page_range))

    index_lines = [
        f"# {standard_name} — Knowledge Base Index\n",
        "| Clause | Title | File | Source Pages |",
        "|---|---|---|---|",
    ]
    for number, title, fname, pages in sorted(index_rows, key=lambda r: _sort_key(r[0])):
        index_lines.append(f"| {number} | {title} | `{fname}` | {pages} |")

    (kb_dir / "00-index.md").write_text("\n".join(index_lines), encoding="utf-8")
    print(f"[clause_splitter] Wrote {len(clauses)} clause files + 00-index.md to {kb_dir}")


def _sort_key(clause_number: str):
    try:
        return [int(p) for p in clause_number.split(".")]
    except ValueError:
        return [999]