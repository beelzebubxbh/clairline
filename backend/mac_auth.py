#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
macOS 版凭据管理层

替代原项目的 capture_manager.py（Windows 专属：winreg 改注册表代理 + certutil 装根证书）。

核心思路：
    Token 只是一个 base64 的 UUID，接口没有任何请求签名，
    所以日常使用根本不需要常驻抓包 —— 只需要在登录态失效时抓一次。
    抓取通过 backend/refresh_token.py（一次性 mitmproxy 会话）完成，
    结果写进 ~/.clairline/credentials.json。

本模块只负责：读状态、同步到 SQLite、重置、给出刷新指引。
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path

try:
    import db
except Exception:  # 允许独立导入做测试
    db = None

CRED_PATH = Path.home() / ".clairline" / "credentials.json"

# 记录最近一次「服务端判定凭据失效」的时间戳。
# 用它把「本地有 Token」和「Token 还能用」区分开 —— 否则界面会一直显示已登录但处处报错。
EXPIRED_FLAG = Path.home() / ".clairline" / ".expired"
_expired_at = 0.0


def _read_expired_flag() -> float:
    try:
        return float(EXPIRED_FLAG.read_text(encoding="utf-8").strip() or 0)
    except Exception:
        return 0.0


def mark_expired():
    """服务端返回 100001/403 时调用；落盘以便重启后仍然生效"""
    global _expired_at
    _expired_at = time.time()
    try:
        EXPIRED_FLAG.parent.mkdir(parents=True, exist_ok=True)
        EXPIRED_FLAG.write_text(str(_expired_at), encoding="utf-8")
    except Exception:
        pass


def is_marked_expired() -> bool:
    """当前凭据是否已被判定失效（文件比失效标记新则视为重新登录过）"""
    marked = max(_expired_at, _read_expired_flag())
    if marked <= 0:
        return False
    try:
        cred_mtime = CRED_PATH.stat().st_mtime
    except Exception:
        cred_mtime = 0
    return cred_mtime <= marked


def clear_expired():
    """重新登录成功后调用"""
    global _expired_at
    _expired_at = 0.0
    try:
        EXPIRED_FLAG.unlink(missing_ok=True)
    except Exception:
        pass
REFRESH_HINT = "登录态已失效：点击右上角会员胶囊，用手机号 + 短信验证码重新登录。注意：在微信小程序里打开长龙也会顶掉这里的会话。"


def _load_cred_file() -> dict:
    try:
        if CRED_PATH.exists():
            with open(CRED_PATH, "r", encoding="utf-8") as f:
                return json.load(f) or {}
    except Exception:
        pass
    return {}


def _mask(v: str, head: int = 10, tail: int = 6) -> str:
    if not v:
        return ""
    if len(v) <= head + tail:
        return v[:4] + "***"
    return f"{v[:head]}...{v[-tail:]}"


def sync_credential_file_to_db() -> bool:
    """把 credentials.json 回填进 SQLite，保证两条读取路径看到同一份凭据。"""
    if db is None:
        return False
    data = _load_cred_file()
    headers = data.get("headers") or {}
    token = headers.get("Authorization") or headers.get("authorization") or ""
    if not token:
        return False
    template = data.get("template") or {}
    profile = {
        "user_name": data.get("user_name") or "长龙会员",
        "mobile": data.get("mobile") or "",
        "member_level": data.get("member_level") or "乘云会员",
        "cert_number": data.get("cert_number") or template.get("certNumber", ""),
        "token": token,
        "cookie": headers.get("Cookie") or f"SESSION={token}",
        "card_name": data.get("card_name") or "长龙畅飞卡",
        "encrypted_user_id": template.get("encryptedUserId", ""),
        "sec_card_grant_tid": str(template.get("secCardGrantTid", "")),
        "headers": headers,
        "template": template,
        "updated_at": data.get("captured_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    try:
        db.save_user_profile(profile)
        return True
    except Exception:
        return False


class MacCaptureManager:
    """保持与原 capture_manager.capture_mgr 一致的接口，供 server.py 无感调用。"""

    def __init__(self):
        self.status = "idle"
        self.message = ""
        self.last_capture_time = ""

    def get_auth_status(self) -> dict:
        sync_credential_file_to_db()
        data = _load_cred_file()
        headers = data.get("headers") or {}
        token = headers.get("Authorization") or headers.get("authorization") or ""
        template = data.get("template") or {}
        has_card = bool(str(template.get("secCardGrantTid") or ""))
        captured_at = data.get("captured_at") or ""

        # 凭据文件比「失效标记」新 → 说明刚重新登录过，视为有效
        try:
            cred_mtime = CRED_PATH.stat().st_mtime
        except Exception:
            cred_mtime = 0
        marked = max(_expired_at, _read_expired_flag())
        expired = marked > 0 and cred_mtime <= marked

        if not token:
            self.status = "idle"
            self.message = "尚未登录"
        elif expired:
            self.status = "expired"
            self.message = "登录态已失效（在微信小程序里登录会顶掉网页端会话），请重新登录"
        else:
            self.status = "success"
            self.message = f"已登录（{captured_at or '未知时间'}）"
            self.last_capture_time = captured_at

        return {
            "ok": True,
            "is_logged_in": bool(token) and not expired,
            "needs_login": (not token) or expired,
            "user_name": data.get("user_name") or "长龙会员",
            "mobile": _mask(data.get("mobile") or "", 3, 4),
            "member_level": data.get("member_level") or ("乘云会员" if token else "未登录"),
            "is_verified": 1 if data.get("cert_number") else 0,
            "update_time": captured_at,
            "auth_preview": _mask(token),
            "cert_installed": False,  # macOS 版不再常驻安装根证书
            "capture_status": self.status,
            "capture_message": self.message,
            "has_card": has_card,
            "platform": "macos",
            "refresh_hint": "" if token else REFRESH_HINT,
        }

    def start_capture(self) -> dict:
        return {
            "ok": False,
            "status": "unsupported",
            "message": REFRESH_HINT,
            "manual": True,
        }

    def stop_capture(self) -> dict:
        return {"ok": True, "status": "idle", "message": "macOS 版无常驻抓包进程"}


def reset_user_auth() -> dict:
    """清空本地登录态（凭据文件 + SQLite 档案）"""
    try:
        if CRED_PATH.exists():
            CRED_PATH.unlink()
    except Exception as e:
        return {"ok": False, "error": f"删除凭据文件失败: {e}"}
    try:
        if db is not None:
            db.save_user_profile({
                "user_name": "长龙会员", "mobile": "", "member_level": "未登录",
                "cert_number": "", "token": "", "cookie": "", "card_name": "长龙畅飞卡",
                "encrypted_user_id": "", "sec_card_grant_tid": "",
                "headers": {}, "template": {}, "updated_at": "",
            })
    except Exception:
        pass
    return {"ok": True, "message": "本地登录态已清空"}


def install_root_cert() -> dict:
    return {
        "ok": False,
        "error": "macOS 版不需要常驻安装根证书",
        "message": "刷新 Token 时由 refresh-token.sh 临时启用 mitmproxy，结束后自动清理。",
    }


def uninstall_root_cert() -> dict:
    return {"ok": True, "message": "macOS 版未安装根证书，无需清理"}


capture_mgr = MacCaptureManager()