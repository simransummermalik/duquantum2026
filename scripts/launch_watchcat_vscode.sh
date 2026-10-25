#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
exec code --extensionDevelopmentPath="$ROOT_DIR/vscode-extension" "$ROOT_DIR"
