#!/usr/bin/env python3
"""
resplit_with_images.py

Your PDF has already been through MinerU (raw_ocr_output/ already has the
content_list.json + extracted images) — this script re-runs just the
clause-splitting step with the new image-preserving logic, skipping OCR
entirely. Much faster than a full rerun.

Usage:
    python3 resplit_with_images.py \
        --raw-output-dir raw_ocr_output/UL864_Combined_Standard \
        --standard "UL 864" \
        --edition "2024 Combined (US/Canada)" \
        --kb-root ./kb
"""

import argparse
import json
import sys
from pathlib import Path

from clause_splitter import split_into_clauses, write_kb_files


def find_content_list(raw_output_dir: Path) -> Path:
    matches = list(raw_output_dir.rglob("*_content_list.json"))
    if not matches:
        sys.exit(f"No *_content_list.json found under {raw_output_dir}. "
                  f"Point --raw-output-dir at the folder from your original run_pipeline.py run.")
    return matches[0]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-output-dir", required=True, help="The raw_ocr_output/<pdf_stem> folder from your original run")
    parser.add_argument("--standard", required=True)
    parser.add_argument("--edition", default="[confirm from title page]")
    parser.add_argument("--kb-root", default="./kb")
    args = parser.parse_args()

    raw_output_dir = Path(args.raw_output_dir)
    content_list_path = find_content_list(raw_output_dir)
    assets_dir = content_list_path.parent
    print(f"[resplit] Using {content_list_path}")
    print(f"[resplit] Images resolved relative to {assets_dir}")

    blocks = json.loads(content_list_path.read_text(encoding="utf-8"))

    standard_folder = args.standard.replace(" ", "").replace(".", "")
    kb_dir = Path(args.kb_root) / standard_folder

    clauses = split_into_clauses(blocks, kb_dir=kb_dir, assets_dir=assets_dir)
    write_kb_files(clauses, kb_dir, standard_name=args.standard, edition=args.edition)

    num_images = len(list((kb_dir / "images").glob("*"))) if (kb_dir / "images").exists() else 0
    print(f"[resplit] Done. {num_images} figure images copied into {kb_dir / 'images'}")


if __name__ == "__main__":
    main()
