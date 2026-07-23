# UCI Local OCR Pipeline (MinerU 2.5)

This is Phase 0/1 of the Unarvu Compliance Intelligence project — the part
that runs **entirely on local/private hardware** (charter §4, §5). It takes
a scanned standard PDF (UL 864 to start) and produces a per-clause markdown
knowledge base ready for human QA and later ingestion into AWS Bedrock.

**Nothing in this folder ever calls a cloud API.** The PDF, the OCR model,
and all intermediate output stay on this machine.

---

## 1. Requirements

- Python 3.10–3.13
- A GPU is strongly recommended (24GB-class, e.g. RTX 4090 / A6000). CPU-only
  works but is slow — fine for the Phase 0 bake-off on a few pages, not for
  the full 265-page run.
- ~15GB free disk for model weights (downloaded once, cached locally).
- Linux or macOS 14+ (Windows works too, see MinerU's Windows CUDA notes if
<<<<<<< HEAD
  GPU acceleration doesn't kick in automatically).

## 2. One-time setup

```bash
=======
  GPU acceleration doesn't kick in automatically — or run it inside WSL2,
  which this project has been tested on).
- **~16GB+ RAM recommended.** See the OOM note in §7 if you're on a
  memory-constrained machine — this affects which workflows are safe to run.

## 2. Clone and one-time setup

```bash
git clone <your-repo-url> uci-ocr-pipeline
cd uci-ocr-pipeline
```

**Set up a virtual environment first.** Modern Ubuntu/Debian (including WSL2
Ubuntu) block system-wide `pip install` by default (PEP 668,
"externally-managed-environment") — a venv isn't optional here:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

If `python3 -m venv` fails with an `ensurepip is not available` error, install
the venv package first, then retry the two lines above:
```bash
sudo apt update && sudo apt install python3-venv
```

**Then run setup:**
```bash
>>>>>>> df1426b (Initial commit)
chmod +x setup.sh
./setup.sh
```

<<<<<<< HEAD
This installs MinerU with all backends, downloads the MinerU2.5 model
weights locally, and verifies the install. If your network can't reach
HuggingFace, it automatically falls back to ModelScope.
=======
This installs MinerU with all backends, downloads the MinerU model weights
locally, and verifies the install. If your network can't reach HuggingFace,
it automatically falls back to ModelScope.

**Every new terminal session, reactivate the venv before running anything:**
```bash
cd uci-ocr-pipeline
source .venv/bin/activate
```
Forgetting this is the most common cause of `mineru: command not found` /
`ModuleNotFoundError` errors — if you hit one, check `(.venv)` is showing at
the start of your prompt first.
>>>>>>> df1426b (Initial commit)

## 3. Phase 0 — Bake-off (do this first, before running the full document)

Pull 10–15 representative pages from UL 864 — **include the densest table
page and a wiring-diagram page**, per the charter's Phase 0 instructions —
into their own mini-PDF, and run:

```bash
mkdir -p input
# put your 10-15 page sample PDF at input/UL864_sample.pdf
python3 run_pipeline.py --pdf input/UL864_sample.pdf --standard "UL 864" --backend pipeline
```

Open the generated files in `./kb/UL864/` and judge table fidelity by eye —
specifically, does every number in the wire-gauge/spacing tables match the
<<<<<<< HEAD
original scan? This is the decision point for whether MinerU2.5 is good
enough on its own, or whether specific pages need a different backend.

If you have a GPU and want MinerU2.5's full accuracy (not just the
CPU-friendly `pipeline` backend), rerun with:

```bash
python3 run_pipeline.py --pdf input/UL864_sample.pdf --standard "UL 864" --backend hybrid
```
=======
original scan? This is the decision point for whether MinerU is good enough
on its own, or whether specific pages need a different backend.

**Backend options** (MinerU 3.x — check `mineru --help` on your installed
version, as these names have changed between releases):
- `pipeline` — CPU-friendly, lower memory footprint. Use this by default,
  especially on a GPU with less than ~8GB VRAM.
- `hybrid-engine` — MinerU's full-accuracy vLLM-based engine. Needs
  significantly more GPU memory than `pipeline`; on a smaller GPU (e.g. a
  4GB-class laptop GPU) this will likely fail with a CUDA out-of-memory
  error during engine initialization. Try it if you have the VRAM to spare:
  ```bash
  python3 run_pipeline.py --pdf input/UL864_sample.pdf --standard "UL 864" --backend hybrid-engine
  ```
  If it OOMs, just go back to `pipeline` — it's what's actually been
  validated end-to-end on the full document in this project so far.
- `vlm-engine`, `vlm-http-client`, `hybrid-http-client` — see MinerU's own
  docs; not used in this project's tested workflow.
>>>>>>> df1426b (Initial commit)

## 4. Phase 1 — Full conversion

Once the backend is confirmed:

```bash
python3 run_pipeline.py \
  --pdf input/UL864_full.pdf \
  --standard "UL 864" \
  --edition "2020, 11th Ed." \
<<<<<<< HEAD
  --backend hybrid \
=======
  --backend pipeline \
>>>>>>> df1426b (Initial commit)
  --kb-root ./kb
```

Output lands in `./kb/UL864/`:

```
kb/UL864/
  00-index.md                          <- clause -> filename -> source page range
  section-19-power-supply.md
  section-21-wiring.md
  ...
```

Each file has the frontmatter block the charter's KB schema (§6) specifies:

```
---
standard: UL 864
edition/year: 2020, 11th Ed.
clause: 19.3.2
title: Standby Battery Capacity
source_pages: 143-144
---
```

<<<<<<< HEAD
=======
**Note:** `write_kb_files()` does not clear `kb/UL864/` before writing — it
only adds/overwrites files. If you've run smaller test batches before the
full run, delete the folder first so old test output doesn't linger mixed in
with the real thing:
```bash
rm -rf kb/UL864
```

>>>>>>> df1426b (Initial commit)
## 5. What happens next (outside this repo)

1. **Human QA pass** (charter §7/§8, the most safety-critical step) —
   a domain reviewer checks every numeric safety table in `./kb/UL864/`
   against the original scans before anything is trusted.
2. **Commit to your private KB git repo** — this pipeline just generates
   the files; version control and PR review happen in your actual repo.
3. **Ingest into AWS Bedrock Knowledge Base** — only after QA sign-off,
   per the confidentiality rule in charter §5 (only converted text leaves
   local hardware, never the raw scans).

## 6. Files in this project

| File | Purpose |
|---|---|
| `setup.sh` | One-time install of MinerU + model weights |
| `run_pipeline.py` | CLI entrypoint — runs MinerU, then the clause splitter |
| `clause_splitter.py` | Groups MinerU's flat OCR output into per-clause files |
| `slugify_util.py` | Turns clause titles into safe filenames |
<<<<<<< HEAD

## 7. Known limitation to check in your bake-off

`CLAUSE_HEADING_RE` in `clause_splitter.py` is tuned for UL-style numbering
(`19.3.2 Title`, `SECTION 19 — TITLE`). If a clause heading in your actual
OCR output doesn't get detected (it'll show up lumped into the previous
clause's body instead of its own file), check the regex against the real
text MinerU produced for that page and adjust it — this is exactly the kind
of thing the Phase 0 bake-off is meant to catch before the full 265-page run.
=======
| `uci-local-rag/` | Local RAG pilot (ChromaDB + Ollama/Qwen2.5) built on top of this pipeline's `kb/` output — separate README inside |

## 7. Known limitations to check in your bake-off

- **`CLAUSE_HEADING_RE`** in `clause_splitter.py` is tuned for UL-style
  numbering (`19.3.2 Title`, `SECTION 19 — TITLE`). If a clause heading in
  your actual OCR output doesn't get detected (it'll show up lumped into the
  previous clause's body instead of its own file), check the regex against
  the real text MinerU produced for that page and adjust it — this is
  exactly the kind of thing the Phase 0 bake-off is meant to catch before
  the full 265-page run.
- **Don't feed a raw folder of page images directly to `--pdf`** on a
  memory-constrained machine (under ~16GB RAM). MinerU will try to hold all
  images in memory at once and can be killed by the Linux OOM killer (seen
  in practice: ~58GB virtual memory requested against 15GB available RAM
  processing 265 loose images). Convert images to a single PDF first — the
  PDF path processes pages more memory-efficiently and has been validated
  end-to-end on the full 265-page document without issue.
>>>>>>> df1426b (Initial commit)
