#!/usr/bin/env bash
# UCI — Local OCR Setup (MinerU 2.5)
# Run this once on the OCR machine (the one with the local GPU).
set -euo pipefail

echo "== 1. Checking Python version (need 3.10–3.13) =="
python3 --version

echo "== 2. Checking for NVIDIA GPU =="
if command -v nvidia-smi &> /dev/null; then
    nvidia-smi --query-gpu=name,memory.total --format=csv
else
    echo "WARNING: nvidia-smi not found. MinerU will fall back to CPU (very slow) unless"
    echo "you have Apple MPS. For a 24GB-class GPU box, make sure NVIDIA drivers + CUDA are installed."
fi

echo "== 3. Installing uv (fast Python package manager) =="
pip install --upgrade pip
pip install uv

echo "== 4. Installing MinerU with all backends (pipeline + vlm + hybrid) =="
uv pip install -U "mineru[all]"

echo "== 5. Downloading MinerU2.5 models locally (so nothing needs internet at run-time) =="
# This pulls the pipeline + vlm model weights into a local cache dir and writes mineru.json
mineru-models-download -s huggingface -m all || mineru-models-download -s modelscope -m all

echo "== 6. Verifying install =="
mineru --version

echo ""
echo "Setup complete."
echo "If you're in a region where HuggingFace is blocked, models were pulled from ModelScope instead."
echo "Next: put your UL 864 PDF in ./input/ and run: python3 run_pipeline.py --pdf input/UL864.pdf"
