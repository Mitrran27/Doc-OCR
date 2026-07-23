#!/usr/bin/env python3
"""
UCI OCR Pipeline — Step 1 of the Unarvu Compliance Intelligence build.

Takes a scanned standard PDF (e.g. UL 864), runs it through MinerU 2.5 locally,
then splits the result into per-clause markdown files matching the KB schema
defined in the project charter (§6):

    /kb/<STANDARD>/
        00-index.md
        section-19-power-supply.md
        section-21-wiring.md
        ...

Usage:
    python3 run_pipeline.py --pdf input/UL864.pdf --standard "UL 864" --edition "2020, 11th Ed."

Requires: MinerU already installed and models downloaded (see setup.sh).
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from clause_splitter import split_into_clauses, write_kb_files


def run_mineru(pdf_path: Path, raw_output_dir: Path, backend: str) -> Path:
    """
    Calls the MinerU CLI to OCR the PDF. Returns the path to the folder
    MinerU writes its output into (it creates a subfolder named after the PDF).
    """
    raw_output_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "mineru",
        "-p", str(pdf_path),
        "-o", str(raw_output_dir),
        "-b", backend,   # "pipeline" for CPU-only, "hybrid" (default) for GPU boxes
    ]
    print(f"[run_pipeline] Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise RuntimeError(f"MinerU failed with exit code {result.returncode}")

    print(result.stdout)

    # MinerU writes output to raw_output_dir/<pdf_stem>/<backend>/
    pdf_stem = pdf_path.stem
    candidate_dirs = list(raw_output_dir.glob(f"{pdf_stem}/**/"))
    content_list_files = [
        p for p in raw_output_dir.rglob(f"{pdf_stem}_content_list.json")
    ]
    if not content_list_files:
        raise FileNotFoundError(
            f"Could not find {pdf_stem}_content_list.json under {raw_output_dir}. "
            f"Check MinerU's output structure — it may have changed versions."
        )
    return content_list_files[0]


def main():
    parser = argparse.ArgumentParser(description="UCI local OCR + clause-split pipeline")
    parser.add_argument("--pdf", required=True, help="Path to the scanned standard PDF")
    parser.add_argument("--standard", required=True, help='Standard name, e.g. "UL 864"')
    parser.add_argument("--edition", default="[confirm from title page]", help="Edition/year")
    parser.add_argument("--kb-root", default="./kb", help="Root of the knowledge base repo")
    parser.add_argument("--raw-output", default="./raw_ocr_output", help="Scratch dir for MinerU's raw output")
    parser.add_argument(
        "--backend", default="pipeline",
        choices=["pipeline", "vlm-engine", "hybrid-engine", "vlm-http-client", "hybrid-http-client"],
        help="MinerU backend. 'pipeline' = CPU-friendly baseline. Use 'hybrid' on a GPU box "
             "for MinerU2.5's full accuracy. Confirm your choice in the Phase 0 bake-off.",
    )
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        sys.exit(f"PDF not found: {pdf_path}")

    raw_output_dir = Path(args.raw_output)
    kb_root = Path(args.kb_root)

    # Folder name inside /kb/ — e.g. "UL 864" -> "UL864"
    standard_folder = args.standard.replace(" ", "").replace(".", "")

    print(f"[run_pipeline] Step 1/2 — OCR via MinerU ({args.backend} backend)")
    content_list_path = run_mineru(pdf_path, raw_output_dir, args.backend)

    print(f"[run_pipeline] Step 2/2 — Splitting into per-clause KB files")
    with open(content_list_path, "r", encoding="utf-8") as f:
        content_list = json.load(f)

    clauses = split_into_clauses(content_list)
    kb_dir = kb_root / standard_folder
    write_kb_files(
        clauses=clauses,
        kb_dir=kb_dir,
        standard_name=args.standard,
        edition=args.edition,
    )

    print(f"\nDone. Knowledge base written to: {kb_dir}")
    print(f"Next steps:")
    print(f"  1. Human QA pass — verify numeric tables against the original scans (Phase 1, §7/§8).")
    print(f"  2. git add/commit {kb_dir} into your private KB repo.")
    print(f"  3. Ingest the repo into your AWS Bedrock Knowledge Base once QA'd.")


if __name__ == "__main__":
    main()
