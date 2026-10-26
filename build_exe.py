#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
长龙航空 · 智能大盘与航网规划助手 (一键 PyInstaller 封包脚本)
GitHub: https://github.com/eureka-wu/clairline

执行本脚本将生成无需 Python/Node.js 环境的单文件绿色版桌面程序：
dist/长龙航空畅飞助手.exe
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT_DIR = Path(__file__).resolve().parent
FRONTEND_DIST = ROOT_DIR / "frontend" / "dist"
ROUTES_SEED = ROOT_DIR / "backend" / "data" / "routes_seed.json"

def build():
    print("=" * 65)
    print("[*] 开始构建 长龙航空畅飞助手 (Windows 绿色单文件 Exe)")
    print("[*] GitHub: https://github.com/eureka-wu/clairline")
    print("=" * 65)

    # 1. 检查前端静态产物
    if not (FRONTEND_DIST / "index.html").exists():
        print("[!] 未检测到前端构建产物，正在执行 npm run build...")
        subprocess.run("npm run build", shell=True, cwd=str(ROOT_DIR / "frontend"), check=True)
    else:
        print("[+] 前端静态产物已就绪 (frontend/dist)")

    # 2. 检查种子数据
    if not ROUTES_SEED.exists():
        print(f"[!] 警告：未检测到 {ROUTES_SEED}")
    else:
        print("[+] 航网直飞种子数据已就绪")

    # 3. 构造 PyInstaller 命令行 (直接生成中文可执行文件并注入高清 Logo 图标)
    icon_path = ROOT_DIR / "app_icon.ico"
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name=长龙航空畅飞助手",
        f"--icon={icon_path}",
        "--paths=backend",
        "--paths=.",
        f"--add-data={FRONTEND_DIST};frontend/dist",
        f"--add-data={ROUTES_SEED};backend/data",
        f"--add-data={ROOT_DIR / 'backend' / 'capture_addon.py'};backend",
        f"--add-data={ROOT_DIR / 'backend' / 'loongair_client.py'};backend",
        f"--add-data={ROOT_DIR / 'backend' / 'proxy_util.py'};backend",
        "--hidden-import=server",
        "--hidden-import=db",
        "--hidden-import=seccard_client",
        "--hidden-import=auto_patrol",
        "--hidden-import=scheduler",
        "--hidden-import=loongair_client",
        "--hidden-import=capture_manager",
        "--hidden-import=proxy_util",
        "--hidden-import=webview",
        "--hidden-import=webview.platforms.edgechromium",
        "--hidden-import=pythonnet",
        "--hidden-import=clr_loader",
        "--hidden-import=bottle",
        "--hidden-import=requests",
        "--hidden-import=sqlite3",
        "app_desktop.py"
    ]

    print("\n[*] 正在调用 PyInstaller 封包中 (耗时约 30~50 秒，请稍候)...")
    res = subprocess.run(cmd, cwd=str(ROOT_DIR))
    if res.returncode == 0:
        dist_dir = ROOT_DIR / "dist"
        cn_exe = dist_dir / "长龙航空畅飞助手.exe"
        v2_exe = dist_dir / "长龙航空畅飞助手-v2.0.0.exe"

        # 在 dist 目录下生成版本号规范命名的中文发布版
        try:
            if cn_exe.exists():
                shutil.copy2(str(cn_exe), str(v2_exe))
        except Exception:
            pass

        # 清除可能残留的英文版过渡文件
        en_exe = dist_dir / "LoongAirHelper.exe"
        if en_exe.exists():
            try: en_exe.unlink()
            except Exception: pass

        # 强制通知 Windows 资源管理器即时刷新图标缓存
        try:
            import ctypes
            ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)
        except Exception:
            pass

        size_mb = v2_exe.stat().st_size / (1024 * 1024) if v2_exe.exists() else 0
        print("\n" + "=" * 65)
        print("[SUCCESS] 打包圆满成功！纯中文正式版已就绪于 dist/ 目录：")
        print(f"[FILE 1] {v2_exe}")
        print(f"[FILE 2] {cn_exe}")
        print(f"[INFO]   文件体积: {size_mb:.2f} MB")
        print("[TIP]    发布方式：直接将 dist/长龙航空畅飞助手-v2.0.0.exe 上传至 GitHub Releases")
        print("=" * 65)
    else:
        print("[!] 打包过程中发生异常，请检查上方控制台报错。")

if __name__ == "__main__":
    build()
