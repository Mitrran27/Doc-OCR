# Unarvu Compliance Intelligence — Project Charter & Task Assignment

**Project Name:** Unarvu Compliance Intelligence (UCI)
**From:** [Owner]
**To:** CTO
**Date:** 2026-07-13
**Status:** Draft for CTO review — please confirm the Open Decisions in §10 before kickoff

## 1. Project Description

Unarvu Compliance Intelligence (UCI) is Unarvu's internal AI advisor for navigating standards, compliance, and regulatory documents — starting with UL 864 for fire alarm control panels and built to expand to UL 268, NFPA 72, and other governing standards over time. It lets firmware and hardware engineers ask design questions in plain language and receive answers grounded in the actual standard text, with the exact clause, edition, and page cited, so every answer can be independently verified.

Unlike a fine-tuned model, UCI is built on retrieval-augmented generation (RAG): a curated, clause-accurate Markdown knowledge base paired with a strong general-purpose model. This keeps answers traceable and correctable — mistakes are fixed by editing the source knowledge base, not retraining a model — and keeps the system open to swapping the underlying LLM later without rebuilding the hard part: the knowledge base itself.

Source documents are paid, copyrighted scans, so all OCR/conversion happens entirely on local, private hardware; only the resulting text knowledge base is used for cloud-based retrieval and chat, keeping raw scans in-house at all times.

UCI is an internal research aid for Unarvu engineers during product design — not a substitute for formal compliance sign-off. Every response includes its clause citation and a reminder to verify against the official standard before relying on it. The pilot targets UL 864; the architecture is namespaced per standard from day one so additional regulatory bodies can be added without re-architecting the system.

## 2. Vision / End Goal

We are converting our scanned copy of UL 864 (and eventually other listing standards) into a structured, searchable knowledge base, and putting a chat-style advisor — Unarvu Compliance Intelligence — in front of it. Firmware and hardware developers should be able to ask a question in plain language — *"does our supervised NAC circuit need a 4-hour standby per this standard?"* — and get an answer grounded in the actual standard text, with the exact clause cited, so the engineer can verify it themselves.

This is **not** a replacement for compliance sign-off. It's a first-pass research aid that turns "search a 277-page scanned PDF" into "ask a question and get pointed at the right clause."

The pilot covers UL 864. The architecture should not need to be rebuilt when we add UL 268, NFPA 72, or other standards later.

## 3. Important terminology note: this is RAG, not a fine-tuned "SLM"

Worth aligning on this early so the team doesn't build the wrong thing.

"Private SLM" (fine-tuning a small language model on our documents) and **RAG — Retrieval-Augmented Generation** (having a strong general-purpose model look up relevant passages from our documents before answering) sound similar but are very different projects:

- **Fine-tuning** requires large amounts of training data (thousands of examples, not 277 pages of one standard) and expensive, specialized ML work. Even done well, it does **not** reliably improve factual/citation accuracy — a fine-tuned model can still confidently cite the wrong clause number, and it's much harder to fix a wrong answer (retrain) than in a RAG system (just fix the source document).
- **RAG** grounds every answer in the actual retrieved clause text at question time. Wrong answers are traceable and fixable by correcting the knowledge base, not by retraining a model. This is the standard, proven approach for "answer questions accurately from a specific proprietary document set with citations" — which is exactly our use case.

**Recommendation: build this as RAG on top of a strong existing model (e.g., Claude), not a fine-tuned model.** The real proprietary asset we're building is the curated, clause-accurate Markdown knowledge base — not a custom model. This also means we're not locked into one model vendor; we can swap the underlying LLM later without redoing the hard part.

## 4. Recommended Architecture

```
[Scanned page images]  (stay on local/private hardware — never uploaded)
        |
        v
[Local OCR / vision-model conversion]   <- self-hosted, e.g. GLM-OCR, MinerU, or Qwen2.5-VL
        |  (output: clean Markdown text, per page)
        v
[Assembly into per-clause Markdown files + master index]
        |
        v
[Private Git repo — the Knowledge Base]  <- source of truth, versioned, PR-reviewed
        |  (text only, no images — much lower sensitivity than raw scans)
        v
[AWS Bedrock Knowledge Base]  <- managed ingestion, chunking, embeddings, vector store
        |
        v
[Claude on Bedrock, retrieval-grounded]  <- answers questions, cites clause numbers
        |
        v
[Chat interface for developers]  <- internal web chat or Slack bot (pilot); VS Code extension later
```

**Why this split:**
- The scanned images are the sensitive, paid, copyrighted artifact — those stay entirely on local/private hardware for OCR conversion and never touch a cloud API. This was a hard requirement from our earlier discussion.
- Once converted to plain clause text, the sensitivity is much lower (it's now our own structured document, similar to internal engineering notes), so it's reasonable to use a managed cloud RAG service for the retrieval/chat layer rather than building and maintaining that infrastructure ourselves.
- **Why AWS Bedrock specifically** (vs. building fully local, vs. Alibaba Cloud, vs. raw Claude API): with a small team on a "few weeks" timeline, Bedrock Knowledge Bases removes the need to build and operate our own embedding pipeline and vector database — that's the part of a RAG system that takes the most engineering time to get right. Bedrock also runs Claude models with enterprise data-handling controls (not used for model training) and keeps everything inside our own AWS account/region. If we later have a hard data-residency requirement (e.g., China operations), Alibaba Cloud's equivalent managed services are a reasonable substitute for the same architecture — this doc's structure doesn't change, only that one component.
- Fully local (self-hosted LLM + local vector DB) is the most private option but is real infrastructure to build and maintain (GPU serving, vector DB ops, model updates). Given team capacity, recommend **not** taking this on for the pilot — revisit only if Bedrock's data handling terms turn out to be unacceptable.

## 5. Data Confidentiality & Governance

- Raw scanned page images: **never leave local/private hardware.** OCR conversion happens on-premises.
- Converted Markdown text: treated as confidential internal IP, stored in a private git repo, access limited to the project team.
- Cloud usage (Bedrock/Claude): only the converted **text** is sent, under AWS's standard enterprise data handling (not used to train models). Confirm this is acceptable before ingesting into Bedrock — flagged as an open decision in §10.
- Every answer the advisor gives must include the source clause citation, so any output can be traced back and verified against the original standard by a human before being relied on for a real compliance decision.

## 6. Knowledge Base Design (multi-standard from day one)

Folder structure, namespaced by standard so we can add more later without rework:

```
/kb/
  UL864/
    00-index.md              <- clause -> filename -> source page range
    section-19-power-supply.md
    section-21-wiring.md
    ...
  UL268/                      <- added later, same convention
  NFPA72/                     <- added later, same convention
```

Each clause file should carry consistent metadata (as frontmatter or a header block) so retrieval can filter and cite precisely:

```
standard: UL 864
edition/year: [confirm from title page]
clause: 19.3.2
title: [clause heading]
source_pages: 142-144
```

Tables render as Markdown tables (not prose) and diagrams get a bracketed description, e.g. `[Figure 19.2: NAC wiring diagram — see source page 143]`, since the model can describe a diagram but not redraw it — the citation lets an engineer pull the original page when a diagram matters.

## 7. Phased Roadmap

**Phase 0 — Setup & Validation (~2–3 days)**
- Bake-off: run 10–15 representative pages (include the densest table page and a wiring-diagram page) through 2–3 candidate OCR models (GLM-OCR, MinerU, Qwen2.5-VL) and judge table fidelity by eye.
- Decide OCR model + confirm/provision local hardware (a single 24GB-class GPU is likely sufficient for a 7B-class vision model — validate in the bake-off before spending on anything bigger).
- Set up the private KB git repo and finalize the file/metadata convention above.
- Provision AWS account/Bedrock access and region; confirm data-handling terms are acceptable.

**Phase 1 — Full Conversion + QA (~1–2 weeks)**
- Run all 265 source pages through the chosen OCR pipeline.
- Assemble into per-clause files + master index for UL 864.
- **Dedicated QA pass** (see §8 — this is the most safety-critical step): verify every safety-critical numeric table (wire gauge, spacing, device listings, etc.) against the original scans.

**Phase 2 — Retrieval + Chat, overlapping with tail of Phase 1 (~1 week)**
- Ingest the QA'd KB into an AWS Bedrock Knowledge Base.
- Configure the advisor's system prompt: require clause citations on every answer, and require a standard disclaimer ("verify against the official standard before relying on this for compliance sign-off").
- Build a validation set of 20–30 known Q&A pairs with known-correct clause citations; measure retrieval accuracy against it before opening to pilot users.
- Stand up the simplest workable chat interface (internal web chat or Slack bot) — skip building a custom VS Code extension for the pilot; that's a good Phase 4 addition once usage patterns are known.

**Phase 3 — Pilot with real developers (~1 week)**
- Onboard 2–3 firmware/hardware developers to test it on real design questions.
- Log every wrong or unhelpful answer; use these to refine chunking, prompt, or KB content.
- Go/no-go checklist before treating it as a trusted internal tool (see §9).

**Phase 4 — Scale (ongoing, after pilot succeeds)**
- Add UL 268, NFPA 72, and other standards using the same pipeline and KB schema.
- Consider deeper developer-workflow integration (VS Code extension, IDE chat panel) once we know how people actually use it.

## 8. Team Workstreams / Roles

- **OCR/Conversion engineer** — owns the model bake-off, batch conversion pipeline, and local hardware.
- **Domain QA reviewer** — ideally someone with fire-alarm compliance background, not just an engineer — verifies converted clauses and tables are correct. This is the highest-risk role: a wrong number in a safety table is far worse than a wrong sentence of prose.
- **Cloud/RAG engineer** — sets up the Bedrock Knowledge Base, tunes retrieval, builds the chat interface.
- **Pilot users** — 2–3 firmware/hardware developers who use it on real questions and give feedback in Phase 3.

## 9. Success Criteria / Go-No-Go for Pilot

- Citation accuracy on the validation Q&A set meets an agreed bar (e.g., correct clause cited ≥90% of the time) before opening to pilot users.
- 100% of spot-checked safety-critical table values match the source scans.
- Every advisor response includes a clause citation and the "verify before relying on this" disclaimer.
- Pilot users report it's faster than manually searching the scanned document.

## 10. Open Decisions for CTO

1. Confirm AWS Bedrock as the retrieval/chat platform, or flag a reason (existing infra, cost, data residency) to use Alibaba Cloud or a fully local stack instead.
2. Approve budget for local OCR hardware (pending bake-off results in Phase 0).
3. Assign the domain QA reviewer — this role has the most impact on whether the tool can be trusted.
4. Confirm AWS data-handling terms for Bedrock are acceptable for our converted (text-only) standard content.
5. Confirm team allocation for the "small dedicated push" timeline above (roughly 3–4 weeks across Phases 0–3).

## 11. Appendix: Candidate Tools

- **OCR/conversion (local, self-hosted):** GLM-OCR (Zhipu/Z.ai), MinerU (open source, layout+table aware), Qwen2.5-VL, GOT-OCR2.0, olmOCR.
- **Retrieval/chat platform:** AWS Bedrock Knowledge Bases (recommended), Alibaba Cloud equivalent (if data residency requires it), fully local stack (Ollama + local vector DB, e.g. Qdrant/Chroma) as a fallback if cloud data terms are unacceptable.
- **LLM for answering:** Claude via Bedrock (recommended for citation-grounded technical Q&A).
