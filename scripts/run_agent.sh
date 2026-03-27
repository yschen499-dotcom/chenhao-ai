#!/usr/bin/env bash
# Linux 上手动前台运行（调试用）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ -f ".venv/bin/python" ]]; then
  exec .venv/bin/python dingtalk_agent.py
fi
echo "请先: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
exit 1
