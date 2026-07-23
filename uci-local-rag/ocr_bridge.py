# """
# ocr_bridge.py — connects this app to your existing uci-ocr-pipeline repo,
# without merging the two codebases or their venvs.

# Two separate repos, two separate venvs, on the same machine:
#     ~/uci-ocr-pipeline        <- has MinerU + clause_splitter.py installed
#     ~/uci-ocr-pipeline/uci-local-rag-v2  <- this app (chromadb/fastapi/etc)

# How the connection works:
# 1. We call the OTHER repo's MinerU binary by its absolute path
#    (~/uci-ocr-pipeline/.venv/bin/mineru). subprocess doesn't care which
#    venv is "active" in this process — it just runs whatever executable
#    path you give it. This sidesteps the cross-venv import problem entirely.
# 2. We import clause_splitter.py directly from that repo (via sys.path),
#    since it's a plain, dependency-light module — reusing your already-QA'd
#    splitting logic instead of duplicating it.

# If you ever move uci-ocr-pipeline to a different path, update
# OCR_PIPELINE_DIR below.
# """

# import json
# import subprocess
# import sys
# from pathlib import Path

# OCR_PIPELINE_DIR = Path.home() / "uci-ocr-pipeline"
# MINERU_BIN = OCR_PIPELINE_DIR / ".venv" / "bin" / "mineru"

# if str(OCR_PIPELINE_DIR) not in sys.path:
#     sys.path.insert(0, str(OCR_PIPELINE_DIR))

# from clause_splitter import split_into_clauses, write_kb_files  # noqa: E402  (reused from the sibling repo)

# BASE_DIR = Path(__file__).parent
# RAW_OCR_DIR = BASE_DIR / "raw_ocr_output"
# KB_PER_DOC_DIR = BASE_DIR / "kb_per_doc"


# def _run_mineru(pdf_path: Path, raw_output_dir: Path, backend: str = "pipeline") -> Path:
#     raw_output_dir.mkdir(parents=True, exist_ok=True)
#     mineru_bin = str(MINERU_BIN) if MINERU_BIN.exists() else "mineru"

#     cmd = [mineru_bin, "-p", str(pdf_path), "-o", str(raw_output_dir), "-b", backend]
#     print(f"[ocr_bridge] Running: {' '.join(cmd)}")
#     result = subprocess.run(cmd, capture_output=True, text=True)

#     if result.returncode != 0:
#         raise RuntimeError(
#             f"MinerU failed (exit {result.returncode}).\n"
#             f"stderr (last 2000 chars): {result.stderr[-2000:]}"
#         )

#     matches = list(raw_output_dir.rglob("*_content_list.json"))
#     if not matches:
#         raise RuntimeError(f"No *_content_list.json found under {raw_output_dir} after MinerU ran.")
#     return matches[0]


# def ocr_and_split(pdf_path: Path, doc_id: str, standard: str, edition: str = "", backend: str = "pipeline") -> Path:
#     """Runs MinerU (via the OCR pipeline repo's own venv binary) on pdf_path,
#     then splits the result into per-clause .md files using clause_splitter.py.
#     Returns the directory containing those .md files."""
#     raw_output_dir = RAW_OCR_DIR / doc_id
#     kb_dir = KB_PER_DOC_DIR / doc_id

#     content_list_path = _run_mineru(pdf_path, raw_output_dir, backend)
#     blocks = json.loads(content_list_path.read_text(encoding="utf-8"))
#     clauses = split_into_clauses(blocks)
#     write_kb_files(clauses, kb_dir, standard_name=standard, edition=edition)
#     return kb_dir



"""
ocr_bridge.py — connects this app to your existing uci-ocr-pipeline repo,
without merging the two codebases or their venvs.

Two separate repos, two separate venvs, on the same machine:
    ~/uci-ocr-pipeline        <- has MinerU + clause_splitter.py installed
    ~/uci-ocr-pipeline/uci-local-rag-v2  <- this app (chromadb/fastapi/etc)

How the connection works:
1. We call the OTHER repo's MinerU binary by its absolute path
   (~/uci-ocr-pipeline/.venv/bin/mineru). subprocess doesn't care which
   venv is "active" in this process — it just runs whatever executable
   path you give it. This sidesteps the cross-venv import problem entirely.
2. We import clause_splitter.py directly from that repo (via sys.path),
   since it's a plain, dependency-light module — reusing your already-QA'd
   splitting logic instead of duplicating it.

If you ever move uci-ocr-pipeline to a different path, update
OCR_PIPELINE_DIR below.
"""

import json
import subprocess
import sys
from pathlib import Path

OCR_PIPELINE_DIR = Path.home() / "uci-ocr-pipeline"
MINERU_BIN = OCR_PIPELINE_DIR / ".venv" / "bin" / "mineru"

if str(OCR_PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(OCR_PIPELINE_DIR))

from clause_splitter import split_into_clauses, write_kb_files  # noqa: E402  (reused from the sibling repo)

BASE_DIR = Path(__file__).parent
RAW_OCR_DIR = BASE_DIR / "raw_ocr_output"
KB_PER_DOC_DIR = BASE_DIR / "kb_per_doc"


def _run_mineru(pdf_path: Path, raw_output_dir: Path, backend: str = "pipeline") -> Path:
    raw_output_dir.mkdir(parents=True, exist_ok=True)
    mineru_bin = str(MINERU_BIN) if MINERU_BIN.exists() else "mineru"

    cmd = [mineru_bin, "-p", str(pdf_path), "-o", str(raw_output_dir), "-b", backend]
    print(f"[ocr_bridge] Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(
            f"MinerU failed (exit {result.returncode}).\n"
            f"stderr (last 2000 chars): {result.stderr[-2000:]}"
        )

    matches = list(raw_output_dir.rglob("*_content_list.json"))
    if not matches:
        raise RuntimeError(f"No *_content_list.json found under {raw_output_dir} after MinerU ran.")
    return matches[0]


def ocr_and_split(pdf_path: Path, doc_id: str, standard: str, edition: str = "", backend: str = "pipeline") -> Path:
    """Runs MinerU (via the OCR pipeline repo's own venv binary) on pdf_path,
    then splits the result into per-clause .md files using clause_splitter.py.
    Returns the directory containing those .md files."""
    raw_output_dir = RAW_OCR_DIR / doc_id
    kb_dir = KB_PER_DOC_DIR / doc_id

    content_list_path = _run_mineru(pdf_path, raw_output_dir, backend)
    blocks = json.loads(content_list_path.read_text(encoding="utf-8"))
    clauses = split_into_clauses(
        blocks,
        kb_dir=kb_dir,
        assets_dir=content_list_path.parent,
    )
    write_kb_files(clauses, kb_dir, standard_name=standard, edition=edition)
    return kb_dir
