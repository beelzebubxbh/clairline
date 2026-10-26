#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一键从长龙官方服务器同步最新个人会员档案与资产信息
"""

import sys
import json
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import db
from loongair_client import fetch_full_user_profile

CRED_FILE = BACKEND_DIR / "data" / "credentials.json"

def sync_current_user_profile() -> dict:
    if not CRED_FILE.exists():
        return {"ok": False, "error": "未检测到 credentials.json，请先通过微信小程序嗅探凭据"}
    
    try:
        with open(CRED_FILE, "r", encoding="utf-8") as f:
            c = f.read().strip()
            cred = json.loads(c) if c else {}
    except Exception as e:
        return {"ok": False, "error": f"读取凭据文件失败: {e}"}
        
    headers = cred.get("headers", {})
    token = headers.get("authorization") or headers.get("Authorization") or ""
    if not token:
        return {"ok": False, "error": "凭据文件中缺少有效的 Authorization"}
        
    print(f"[*] 正在主动向长龙官方服务器查询会员全量档案 (Token: {token[:12]}...)...")
    prof = fetch_full_user_profile(headers)
    print(f"[+] 成功获取长龙会员档案: {prof.get('user_name')} | 等级: {prof.get('member_level')} | 实名: {prof.get('is_verified')}")
    
    # 回写 credentials.json
    cred["profile"] = prof
    try:
        with open(CRED_FILE, "w", encoding="utf-8") as f:
            json.dump(cred, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
        
    # 保存进 SQLite
    prof_db = {
        "user_name": prof.get("user_name") or "长龙会员",
        "mobile": prof.get("mobile") or "",
        "member_level": prof.get("member_level") or "乘云会员",
        "cert_number": prof.get("cert_number") or "",
        "token": token,
        "cookie": headers.get("cookie") or headers.get("Cookie") or "",
        "card_name": prof.get("card_name") or "长龙畅飞卡",
        "encrypted_user_id": prof.get("encrypted_user_id") or "",
        "sec_card_grant_tid": prof.get("sec_card_grant_tid") or "",
        "coupons_count": prof.get("coupons_count", 0),
        "cards_count": prof.get("cards_count", 0),
        "points": prof.get("points", 0),
        "is_verified": prof.get("is_verified", 0),
        "updated_at": cred.get("update_time", "")
    }
    db.save_user_profile(prof_db)
    print("[+] 会员全量资料已成功持久化至 SQLite user_profile 表！")
    return {"ok": True, "profile": prof_db}

if __name__ == "__main__":
    res = sync_current_user_profile()
    print("Result:", json.dumps(res, ensure_ascii=False, indent=2))
