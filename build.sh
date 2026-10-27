#!/usr/bin/env bash
# Génère le modèle ONNX du mot d’appel dans Docker (équivalent Linux de build.ps1).
# Usage : ./build.sh [étape] [--cpu] [--config=recette.yml]
# Étapes : build (par défaut), doctor, prepare, generate, augment, train, ecoute.
set -euo pipefail
cd "$(dirname "$0")"
image=wakeword-fr-training
step=build
cpu=0
config=training.yml
for argument in "$@"; do
  case "$argument" in
    --cpu) cpu=1 ;;
    --config=*) config=${argument#--config=} ;;
    build|doctor|prepare|generate|augment|train|ecoute) step=$argument ;;
    *) echo "Argument inconnu : $argument (voir docs/entrainer.md)" >&2; exit 2 ;;
  esac
done

# Seul l’entraînement profite du GPU : les autres étapes tournent sur le processeur (la génération en parallèle).
gpu=()
if [ "$cpu" = 0 ] && { [ "$step" = build ] || [ "$step" = train ]; }; then
  gpu=(--gpus all)
fi

if ! docker image inspect "$image" >/dev/null 2>&1; then
  docker build -t "$image" .
fi
# Clips et caractéristiques dans un volume Docker : bien plus rapide que le dossier partagé.
# « ecoute » en copie quelques-uns dans output/<model_name>-ecoute/.
docker run --rm --shm-size=8g "${gpu[@]}" -v wakeword-travail:/travail -e WAKEWORD_WORK=/travail \
  -v "$(pwd):/workspace" -w /workspace \
  "$image" --config "$config" "$step"
if [ "$step" = build ] || [ "$step" = train ]; then
  echo "Modèle ONNX prêt dans output/."
fi
