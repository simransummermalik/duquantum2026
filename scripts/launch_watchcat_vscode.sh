#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
exec code \
  --new-window \
  --user-data-dir="/tmp/watchcat-vscode-data-v3" \
  --extensionDevelopmentPath="$ROOT_DIR/vscode-extension" \
  --folder-uri="file://$ROOT_DIR"
