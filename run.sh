#!/bin/bash
# 长龙航空航网助手 · macOS 启动脚本
set -e
cd "$(dirname "$0")"

DATA_DIR="$HOME/.clairline/data"
mkdir -p "$DATA_DIR"

# 首次运行：把航线种子复制到用户数据目录
if [ ! -f "$DATA_DIR/routes_seed.json" ]; then
  cp backend/data/routes_seed.json "$DATA_DIR/routes_seed.json"
  echo "[+] 已初始化航线种子数据"
fi

# 数据与凭据都放用户目录，仓库保持干净
export CLAIRLINE_DATA_DIR="$DATA_DIR"

# 前端构建产物检查
if [ ! -f frontend/dist/index.html ]; then
  echo "[!] 未找到前端构建产物，正在构建（首次约需 1 分钟）..."
  (cd frontend && npm install --no-audit --no-fund && npm run build)
fi

echo "[*] 长龙航网助手启动中 → http://127.0.0.1:3000"
exec python3 backend/server.py