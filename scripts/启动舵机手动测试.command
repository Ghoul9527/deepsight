#!/bin/zsh
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
cd "$REPO_DIR" || exit 1
if [[ -x "$REPO_DIR/.venv-coreml/bin/python" ]]; then
  exec "$REPO_DIR/.venv-coreml/bin/python" -m deepsight_host.servo_tester
else
  exec "$REPO_DIR/.venv/bin/python" -m deepsight_host.servo_tester
fi
