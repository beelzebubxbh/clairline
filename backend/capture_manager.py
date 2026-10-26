#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
长龙航空 · 畅飞卡凭据嗅探服务管理模块 (无弹窗后台运行版)
负责在受控后台线程中启动与管理 mitmdump 嗅探器，提供 REST 状态查询、启停与证书自检。
"""
import os
import sys
import json
import time
import subprocess
import threading
from datetime import datetime
from pathlib import Path

try:
    from . import db
except Exception:
    import db

BACKEND_DIR = Path(__file__).resolve().parent
DATA_DIR = getattr(db, "DATA_DIR", BACKEND_DIR / "data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
CRED_FILE = DATA_DIR / "credentials.json"
ADDON_PATH = BACKEND_DIR / "capture_addon.py"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def mask_mobile(m: str) -> str:
    if not m or len(m) < 7: return m or ""
    return f"{m[:3]}****{m[-4:]}"

def mask_id(c: str) -> str:
    if not c or len(c) < 8: return c or ""
    return f"{c[:6]}********{c[-4:]}"

def check_cert_installed() -> bool:
    """检查 mitmproxy CA 根证书是否已在 Windows 用户受信任根证书库中"""
    cert_path = Path.home() / ".mitmproxy" / "mitmproxy-ca-cert.cer"
    if not cert_path.exists():
        return False
    try:
        res = subprocess.run(
            'certutil -verifystore -user Root "mitmproxy"',
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return res.returncode == 0 or "mitmproxy" in res.stdout
    except Exception:
        return cert_path.exists()

def install_root_cert() -> dict:
    """调用系统 certutil 一键导入根证书至 CurrentUser\\Root"""
    cert_path = Path.home() / ".mitmproxy" / "mitmproxy-ca-cert.cer"
    if not cert_path.exists():
        return {"ok": False, "error": "未在 ~/.mitmproxy/ 检测到证书文件，请先点击启动一次嗅探"}
    try:
        res = subprocess.run(
            f'certutil -addstore -user Root "{cert_path}"',
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if res.returncode == 0:
            return {"ok": True, "message": "根证书已成功导入 Windows 根证书受信任区！"}
        return {"ok": False, "error": res.stderr or res.stdout or "证书导入未通过"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def uninstall_root_cert() -> dict:
    """从 Windows 用户受信任根证书库中移除 mitmproxy 证书（供测试一键重置使用）"""
    try:
        res = subprocess.run(
            'certutil -delstore -user Root "mitmproxy"',
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return {"ok": True, "message": "已成功从 Windows 根证书信任区移除 mitmproxy 证书！"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def reset_user_auth() -> dict:
    """一键重置当前登录凭据（清空 credentials.json 与 SQLite 中的 user_profile），模拟纯净新用户"""
    try:
        if CRED_FILE.exists():
            try:
                CRED_FILE.unlink()
            except Exception:
                CRED_FILE.write_text("{}", encoding="utf-8")
        db.save_user_profile({
            "user_name": "长龙会员",
            "mobile": "",
            "member_level": "未登录",
            "cert_number": "",
            "token": "",
            "cookie": "",
            "card_name": "长龙畅飞卡",
            "encrypted_user_id": "",
            "sec_card_grant_tid": "",
            "updated_at": ""
        })
        return {"ok": True, "message": "会员登录态与本地个人凭据已彻底清空重置！"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

class CaptureManager:

    def __init__(self):
        self.process: subprocess.Popen | None = None
        self.status = "idle"  # "idle" | "capturing" | "success" | "error"
        self.message = ""
        self.last_capture_time = ""
        self.lock = threading.Lock()

    def get_auth_status(self) -> dict:
        """检查数据库与 credentials.json 中是否具备有效会员凭证"""
        profile = db.get_user_profile() or {}
        is_logged_in = bool(profile.get("token"))
        update_time = profile.get("updated_at", "")
        auth = profile.get("token", "")

        # 核心机制：每天北京时间 00:00 自动将凭证标记为过期清空
        # 原因：微信小程序会话 Token 具有自然日生命周期，跨越 0 点后失效
        today_date = datetime.now().strftime("%Y-%m-%d")
        if update_time and update_time[:10] != today_date:
            print(f"[*] 提示：检测到长龙凭证更新日期为 {update_time[:10]}，已跨越北京时间 00:00 自然日周期（微信登录态已失效），自动清空过期凭据。")
            reset_user_auth()
            profile = {}
            is_logged_in = False
            update_time = ""
            auth = ""

        # 如果 SQLite 库中尚未记录，则从 credentials.json 补充并同步进 SQLite
        if not is_logged_in and CRED_FILE.exists():
            try:
                with open(CRED_FILE, "r", encoding="utf-8") as f:
                    c = f.read().strip()
                    if c:
                        data = json.loads(c)
                        headers = data.get("headers", {})
                        auth = headers.get("authorization") or headers.get("Authorization") or ""
                        tpl = data.get("template", {})
                        prof = data.get("profile", {})
                        if auth and len(auth) > 15:
                            is_logged_in = True
                            update_time = data.get("update_time", "")
                            profile = {
                                "user_name": prof.get("user_name") or "长龙会员",
                                "mobile": prof.get("mobile") or tpl.get("mobile", ""),
                                "member_level": prof.get("member_level") or "乘云会员",
                                "cert_number": prof.get("cert_number") or tpl.get("certNumber", ""),
                                "token": auth,
                                "cookie": headers.get("cookie", ""),
                                "card_name": prof.get("card_name") or "长龙畅飞卡",
                                "encrypted_user_id": prof.get("encrypted_user_id") or tpl.get("encryptedUserId", ""),
                                "sec_card_grant_tid": prof.get("sec_card_grant_tid") or tpl.get("secCardGrantTid", ""),
                                "is_verified": prof.get("is_verified", 0),
                                "updated_at": update_time
                            }
                            db.save_user_profile(profile)
            except Exception:
                pass

        auth_preview = f"{auth[:10]}...{auth[-6:]}" if len(auth) > 16 else ""

        return {
            "ok": True,
            "is_logged_in": is_logged_in,
            "user_name": profile.get("user_name", "长龙会员"),
            "mobile": mask_mobile(profile.get("mobile", "")),
            "cert_number": mask_id(profile.get("cert_number", "")),
            "member_level": profile.get("member_level", "乘云会员"),
            "is_verified": profile.get("is_verified", 0),
            "update_time": update_time,
            "auth_preview": auth_preview,
            "cert_installed": check_cert_installed(),
            "capture_status": self.status,
            "capture_message": self.message
        }


    def start_capture(self) -> dict:
        """由网页前端一键发起：在后台静默启动嗅探器，自动开启 Windows 代理"""
        with self.lock:
            if self.process and self.process.poll() is None:
                return {
                    "ok": True,
                    "status": "capturing",
                    "message": "嗅探服务已在后台运行中，请打开微信小程序【我的】"
                }

            # 寻找 mitmdump 可执行文件或 Python 模块
            import shutil
            mitm_cmd = None
            if shutil.which("mitmdump"):
                mitm_cmd = ["mitmdump", "--listen-port", "8080", "-s", str(ADDON_PATH)]
            elif Path(r"D:\bin\mitmdump.exe").exists():
                mitm_cmd = [r"D:\bin\mitmdump.exe", "--listen-port", "8080", "-s", str(ADDON_PATH)]
            else:
                # 回退：直接使用当前 Python 虚拟环境内置的 mitmproxy 模块运行
                mitm_cmd = [sys.executable, "-m", "mitmproxy.tools.dump", "--listen-port", "8080", "-s", str(ADDON_PATH)]

            # 启动前杀除可能残留的旧 mitm 进程
            try:
                subprocess.run(
                    'powershell -NoProfile -Command "Get-Process mitmweb, mitmdump -ErrorAction SilentlyContinue | Stop-Process -Force"',
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            except Exception:
                pass

            # Windows 下通过 CREATE_NO_WINDOW 实现彻底无黑框无弹窗静默运行
            creationflags = 0x08000000 if sys.platform == "win32" else 0

            try:
                self.process = subprocess.Popen(
                    mitm_cmd,
                    creationflags=creationflags,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )

                self.status = "capturing"
                self.message = "嗅探服务已启动！Windows 代理已自动开启 (127.0.0.1:8080)，请在微信中打开长龙航空小程序【我的】"

                # 启动守护线程等待捕获完成
                threading.Thread(target=self._monitor_worker, daemon=True).start()

                return {
                    "ok": True,
                    "status": "capturing",
                    "message": self.message
                }
            except Exception as e:
                self.status = "error"
                self.message = f"启动嗅探器失败: {e}"
                return {
                    "ok": False,
                    "status": "error",
                    "error": str(e)
                }

    def stop_capture(self) -> dict:
        """手动取消/停止抓包，并确保系统代理恢复关闭"""
        with self.lock:
            if self.process and self.process.poll() is None:
                try:
                    self.process.terminate()
                    self.process.kill()
                except Exception:
                    pass
            self.process = None
            self.status = "idle"
            self.message = "嗅探已手动停止"

            # 确保 Windows 系统代理彻底恢复关闭
            self._restore_system_proxy()

            return {
                "ok": True,
                "status": "idle",
                "message": "嗅探已停止，Windows 系统代理已恢复关闭。"
            }

    def _restore_system_proxy(self):
        """恢复系统代理为关闭状态"""
        try:
            from proxy_util import cleanup_proxy_if_needed
            cleanup_proxy_if_needed()
        except Exception:
            pass

    def _monitor_worker(self):
        """后台监控子进程，当抓取到凭据或退出时更新状态"""
        proc = self.process
        if not proc:
            return

        # 等待 mitmdump 正常捕获退出（capture_addon 捕获后会执行 ctx.master.shutdown）
        proc.wait()

        with self.lock:
            # 校验 credentials.json 是否已成功落盘
            if CRED_FILE.exists():
                try:
                    with open(CRED_FILE, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        headers = data.get("headers", {})
                        auth = headers.get("authorization") or headers.get("Authorization") or ""
                        tpl = data.get("template", {})
                        update_time = data.get("update_time", "")
                        if auth and len(auth) > 15:
                            self.status = "success"
                            self.last_capture_time = update_time
                            self.message = f"成功捕获会员凭据！(捕获时间: {update_time})"

                            prof = data.get("profile", {})
                            if not prof.get("user_name") or prof.get("user_name") == "长龙会员":
                                try:
                                    from loongair_client import fetch_full_user_profile
                                    fetched = fetch_full_user_profile(headers)
                                    prof.update(fetched)
                                except Exception:
                                    pass

                            # 持久化同步存入 SQLite user_profile 表
                            profile = {
                                "user_name": prof.get("user_name") or "长龙会员",
                                "mobile": prof.get("mobile") or tpl.get("mobile", ""),
                                "member_level": prof.get("member_level") or "乘云会员",
                                "cert_number": prof.get("cert_number") or tpl.get("certNumber", ""),
                                "token": auth,
                                "cookie": headers.get("cookie", ""),
                                "card_name": prof.get("card_name") or "长龙畅飞卡",
                                "encrypted_user_id": prof.get("encrypted_user_id") or tpl.get("encryptedUserId", ""),
                                "sec_card_grant_tid": prof.get("sec_card_grant_tid") or tpl.get("secCardGrantTid", ""),
                                "is_verified": prof.get("is_verified", 0),
                                "updated_at": update_time
                            }
                            db.save_user_profile(profile)

                            # 热重载本地 client
                            try:
                                from seccard_client import SecCardClient
                                SecCardClient().check_and_reload()
                            except Exception:
                                pass

                            self.process = None
                            self._restore_system_proxy()
                            return
                except Exception:
                    pass

            if self.status == "capturing":
                self.status = "idle"
                self.message = "嗅探服务已退出"

            self.process = None
            self._restore_system_proxy()

# 单例导出
capture_mgr = CaptureManager()
