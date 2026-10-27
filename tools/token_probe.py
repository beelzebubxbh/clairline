#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Token 寿命探针

目的：搞清楚长龙 Token 到底能活多久。
做法：每隔 N 分钟用当前的 Authorization 调一次最轻的接口
      （AccountService_checkIfLogin，响应约 130 字节），
      一旦返回 100001 / 403 就判定失效，记录精确时间并退出。

注意（实验设计上的坑）：
    如果服务端采用「滑动过期」（每次访问都续命），那么探测本身会延长寿命，
    测出来的是「至少活了这么久」，而不是真实 TTL。所以间隔不宜太密，默认 15 分钟。
    另外你在网页上正常使用也会打接口，同样会影响结果。

用法：
    python3 tools/token_probe.py                 # 默认 15 分钟一次
    python3 tools/token_probe.py --interval 300  # 5 分钟一次
    python3 tools/token_probe.py --once          # 只探一次，现场判断当前是否有效

日志：~/.clairline/token-probe.log（一行一个 JSON）
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

import loongair_client as lc  # noqa: E402

CRED_PATH = Path.home() / ".clairline" / "credentials.json"
LOG_PATH = Path.home() / ".clairline" / "token-probe.log"

ENDPOINTS = [
    ("AccountService_checkIfLogin", {"SaleChannel": 76, "saleChannel": 76, "language": "zh-cn"}),
]


def now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def token_fp(token: str) -> str:
    return hashlib.sha1(token.encode()).hexdigest()[:8]


def load_token() -> tuple[str, float]:
    """返回 (token, 凭据文件 mtime)"""
    try:
        data = json.loads(CRED_PATH.read_text(encoding="utf-8"))
        token = (data.get("headers") or {}).get("Authorization", "")
        return token, CRED_PATH.stat().st_mtime
    except Exception:
        return "", 0.0


def probe_once(token: str) -> dict:
    headers = lc._base_headers(token)
    for method, params in ENDPOINTS:
        t0 = time.time()
        res = lc._post(method, params, headers, timeout=15)
        elapsed = int((time.time() - t0) * 1000)
        if res is None:
            return {"ok": False, "transport_error": True, "ms": elapsed}
        code = res.get("ErrorCode")
        return {
            "ok": code == 0,
            "code": code,
            "message": (res.get("message") or "").strip(),
            "ms": elapsed,
        }
    return {"ok": False, "transport_error": True}


def write_log(rec: dict):
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=int, default=900, help="探测间隔（秒），默认 900")
    ap.add_argument("--once", action="store_true", help="只探测一次")
    args = ap.parse_args()

    token, mtime = load_token()
    if not token:
        print("[!] 未找到有效凭据，请先在网页里登录")
        return 1

    fp = token_fp(token)
    started_at = mtime  # 用凭据文件写入时间近似「签发时间」
    print(f"[*] 开始探测  token={fp}  签发≈{datetime.fromtimestamp(started_at).strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"[*] 间隔 {args.interval}s  日志 {LOG_PATH}")

    while True:
        token, mtime = load_token()
        if not token:
            print("[!] 凭据文件消失，停止探测")
            return 1

        cur_fp = token_fp(token)
        if cur_fp != fp:
            # 用户重新登录了，换新基线重新计
            fp = cur_fp
            started_at = mtime
            rec = {"ts": now_iso(), "event": "TOKEN_ROTATED", "token": fp,
                   "issued_approx": datetime.fromtimestamp(started_at).strftime("%Y-%m-%d %H:%M:%S")}
            write_log(rec)
            print(f"[↻] 检测到新 Token {fp}，重新计时")

        res = probe_once(token)
        alive_h = (time.time() - started_at) / 3600
        rec = {
            "ts": now_iso(),
            "token": fp,
            "alive_hours": round(alive_h, 2),
            **res,
        }
        write_log(rec)

        if res.get("ok"):
            print(f"[+] {rec['ts']}  存活 {alive_h:.2f}h  {res.get('ms')}ms")
        elif res.get("transport_error"):
            print(f"[?] {rec['ts']}  网络异常，下轮重试")
        else:
            print(f"[✗] {rec['ts']}  失效！存活 {alive_h:.2f} 小时（{alive_h*60:.0f} 分钟）")
            print(f"    返回: ErrorCode={res.get('code')} {res.get('message')}")
            write_log({"ts": now_iso(), "event": "EXPIRED", "token": fp,
                       "alive_hours": round(alive_h, 2),
                       "issued_approx": datetime.fromtimestamp(started_at).strftime("%Y-%m-%d %H:%M:%S")})
            return 0

        if args.once:
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n[!] 已手动停止")
        sys.exit(130)