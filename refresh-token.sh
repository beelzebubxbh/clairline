#!/bin/bash
# 长龙航网助手 · 刷新登录态（登录态失效时运行）
set -e
cd "$(dirname "$0")"
command -v mitmdump >/dev/null || { echo "[!] 缺少 mitmproxy，请先执行: brew install mitmproxy"; exit 1; }
exec python3 backend/refresh_token.py
