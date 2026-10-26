#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
长龙航空 · 智能大盘与航网规划助手 (桌面客户端版)
GitHub 官方仓库: https://github.com/eureka-wu/clairline

特性：
1. 原生轻量：基于 Windows Edge Chromium WebView2 内核，内存占用低至 40MB；
2. 零外部依赖：内置 Python HTTP API 服务与 SQLite 数据引擎，开箱即用；
3. 安全守护：窗口退出时自动还原 Windows 代理，绝不悬挂网络。
"""

import os
import sys
import time
import threading
from pathlib import Path

# 兼容普通运行与 PyInstaller 打包环境
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys._MEIPASS).resolve()
else:
    BASE_DIR = Path(__file__).resolve().parent

BACKEND_DIR = BASE_DIR / "backend"

for p in [str(BACKEND_DIR), str(BASE_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    import server
except ImportError:
    from backend import server

try:
    import db
except ImportError:
    from backend import db

try:
    from proxy_util import cleanup_proxy_if_needed
except ImportError:
    from backend.proxy_util import cleanup_proxy_if_needed

GITHUB_REPO_URL = "https://github.com/eureka-wu/clairline"
APP_TITLE = "长龙航空 · 畅飞智能助手 v2.0 (GitHub: eureka-wu/clairline)"

def start_backend_server(port: int = 3000):
    """在后台线程中启动前后端一体化 HTTP 服务"""
    try:
        server.PORT = port
        server.run()
    except Exception as e:
        print(f"[!] 后端服务异常: {e}", flush=True)

def wait_for_server(port: int = 3000, timeout: float = 5.0) -> bool:
    """等待本地后端 HTTP 服务端口就绪"""
    import urllib.request
    start = time.time()
    url = f"http://127.0.0.1:{port}/api/status"
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(url, timeout=0.8) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.15)
    return False

def on_closed():
    """桌面窗口关闭时的退出清理 Hook"""
    print("[*] 桌面客户端正在关闭，执行安全退出与代理还原...", flush=True)
    cleanup_proxy_if_needed()
    # 强制退出所有常驻守护线程
    os._exit(0)

def main():
    # 1. 初始化数据库与种子航线拓扑
    try:
        db.init_db()
    except Exception as ex:
        print(f"[*] 数据库初始化提示: {ex}")

    # 2. 检查并确保系统代理在冷启动时处于关闭正常直连状态
    cleanup_proxy_if_needed()

    # 3. 启动后台 HTTP 服务
    port = 3000
    server_thread = threading.Thread(target=start_backend_server, args=(port,), daemon=True)
    server_thread.start()

    ready = wait_for_server(port)
    if not ready:
        print(f"[!] 警告：后端服务启动较慢，继续拉起桌面窗口...")

    # 4. 拉起 WebView2 桌面窗口
    import webview

    window = webview.create_window(
        title=APP_TITLE,
        url=f"http://127.0.0.1:{port}",
        width=1380,
        height=880,
        min_size=(1080, 680),
        text_select=True,
        zoomable=True
    )
    window.events.closed += on_closed

    # 使用 Edge Chromium (WebView2) 引擎
    webview.start(gui="edgechromium", debug=False)

if __name__ == "__main__":
    main()
