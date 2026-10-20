#!/usr/bin/env bash
# Génère le modèle ONNX du mot d’appel dans Docker (équivalent Linux de build.ps1).
# Usage : ./build.sh [étape] [--cpu]
# Étapes : build (par défaut), doctor, prepare, generate, augment, train.
set -euo pipefail
cd "$(dirname "$0")"
image=wakeword-fr-training
step=build
cpu=0
for argument in "$@"; do
  case "$argument" in
    --cpu) cpu=1 ;;
    build|doctor|prepare|generate|augment|train) step=$argument ;;
    *) echo "Argument inconnu : $argument (voir docs/entrainer.md)" >&2; exit 2 ;;
  esac
done

# Seul l’entraînement profite du GPU : les autres étapes tournent sur le processeur.
gpu=()
if [ "$cpu" = 0 ] && { [ "$step" = build ] || [ "$step" = train ]; }; then
  gpu=(--gpus all)
fi

if ! docker image inspect "$image" >/dev/null 2>&1; then
  docker build -t "$image" .
fi
docker run --rm --shm-size=8g "${gpu[@]}" -v "$(pwd):/workspace" -w /workspace \
  "$image" --config training.yml "$step"
if [ "$step" = build ] || [ "$step" = train ]; then
  echo "Modèle ONNX prêt dans output/."
fi
