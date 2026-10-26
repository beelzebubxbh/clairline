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

    # 3. 构造 PyInstaller 命令行
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name=LoongAirHelper",
        f"--icon={ROOT_DIR / 'app_icon.ico'}",
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
        en_exe = dist_dir / "LoongAirHelper.exe"
        cn_exe = dist_dir / "长龙航空畅飞助手.exe"
        target_exe = cn_exe

        # 直接保留中文名字的 Exe，移除英文过渡文件
        if en_exe.exists():
            try:
                if cn_exe.exists():
                    cn_exe.unlink()
                shutil.move(str(en_exe), str(cn_exe))
                target_exe = cn_exe
            except PermissionError:
                print("\n[!] 提示：检测到《长龙航空畅飞助手.exe》当前正在运行中（被 Windows 保护锁定）。")
                print(f"[!] 最新构建好的版本已生成在: {en_exe}")
                print("[!] 请先关闭正在运行的客户端窗口，再次运行 build_exe.py 或将该文件覆盖即可。")
                target_exe = en_exe

        size_mb = target_exe.stat().st_size / (1024 * 1024) if target_exe.exists() else 0
        print("\n" + "=" * 65)
        print("[SUCCESS] 打包圆满成功！")
        print(f"[FILE] 客户端 Exe 路径: {target_exe}")
        print(f"[INFO] 文件体积: {size_mb:.2f} MB")
        print("[TIP] 推荐发布方式：直接上传至 GitHub Releases (https://github.com/eureka-wu/clairline/releases)")
        print("=" * 65)
    else:
        print("[!] 打包过程中发生异常，请检查上方控制台报错。")

if __name__ == "__main__":
    build()
