#!/usr/bin/env bash
# Génère le modèle ONNX du mot d’appel dans Docker (équivalent Linux de build.ps1).
# Usage : ./build.sh [--cpu]
set -euo pipefail
cd "$(dirname "$0")"
image=wakeword-fr-training
gpu=(--gpus all)
if [ "${1:-}" = --cpu ]; then gpu=(); fi

if ! docker image inspect "$image" >/dev/null 2>&1; then
  docker build -t "$image" .
fi
docker run --rm --shm-size=8g "${gpu[@]}" -v "$(pwd):/workspace" -w /workspace \
  "$image" --config training.yml build
echo "Modèle ONNX prêt dans output/."
