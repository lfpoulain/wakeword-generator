#!/usr/bin/env bash
# Testeur micro du mot d’appel (équivalent Linux de tester.bat).
# Usage : ./tester.sh [options de tester.py]
set -euo pipefail
cd "$(dirname "$0")"
python=.venv-test/bin/python
if [ ! -x "$python" ]; then
  echo "Environnement du testeur absent. Suivez README.md, section Tester au microphone." >&2
  exit 1
fi
"$python" tester.py --prepare
exec "$python" tester.py "$@"
