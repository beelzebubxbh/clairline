#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
长龙航网助手 · macOS 登录态刷新工具

为什么需要它：
    接口没有请求签名，凭据就是一个 base64 的 UUID Session。
    日常使用不需要常驻抓包，只有登录态失效时才需要重新抓一次。

用法：
    ./refresh-token.sh          # 推荐（带环境检查）
    python3 backend/refresh_token.py

流程：
    1. 确认 mitmproxy 根证书已装入系统信任区（未装则给出一次性命令）
    2. 在 8080 端口启动 mitmdump，自动把系统代理指过去
    3. 你在微信里打开长龙航空小程序「我的」页
    4. 捕获到请求头后立刻落盘到 ~/.clairline/credentials.json，并自动关代理

安全性：
    证书是你本机 mitmproxy 生成的，私钥只在这台 Mac 上；
    代理只在抓取期间开启，结束（含异常/中断）一定恢复。
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

CRED_PATH = Path.home() / ".clairline" / "credentials.json"
CA_PEM = Path.home() / ".mitmproxy" / "mitmproxy-ca-cert.pem"
ADDON_PATH = Path.home() / ".clairline" / ".capture_addon.py"
PORT = 8080
TIMEOUT = 180

ADDON_SRC = r'''
import json, os, time
from mitmproxy import http

OUT = os.path.expanduser("~/.clairline/capture_raw.jsonl")
KEEP = ("Authorization", "NESign", "Cookie", "X-App-Version", "User-Agent",
        "Referer", "xweb_xhr", "Accept", "Accept-Language")

class Cap:
    def request(self, flow):
        if "loongair.cn" not in flow.request.pretty_url:
            return
        body = flow.request.get_text(strict=False) or ""
        if "secCardSearchFlights" not in body and "getSecCardRedeemedCalendar" not in body:
            return
        rec = {
            "t": time.strftime("%H:%M:%S"),
            "url": flow.request.pretty_url,
            "headers": {k: v for k, v in flow.request.headers.items() if k in KEEP},
            "body": body,
        }
        with open(OUT, "w", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False))

addons = [Cap()]
'''


def run(cmd, **kw):
    return subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True, text=True, **kw)


def active_service() -> str:
    """找到默认路由网卡对应的网络服务名（macOS 的 networksetup 按服务名操作）"""
    try:
        out = run(["route", "-n", "get", "default"]).stdout
        iface = re.search(r"interface:\s*(\w+)", out).group(1)
    except Exception:
        return "Wi-Fi"
    order = run(["networksetup", "-listnetworkserviceorder"]).stdout
    current = None
    for line in order.splitlines():
        m = re.match(r"\(\d+\)\s+(.+)", line.strip())
        if m:
            current = m.group(1).strip()
        if f"Device: {iface}" in line and current:
            return current
    return "Wi-Fi"


def set_proxy(service: str, enable: bool):
    if enable:
        run(["networksetup", "-setwebproxy", service, "127.0.0.1", str(PORT)])
        run(["networksetup", "-setsecurewebproxy", service, "127.0.0.1", str(PORT)])
        run(["networksetup", "-setproxybypassdomains", service, "localhost", "127.0.0.1", "*.local"])
    else:
        run(["networksetup", "-setwebproxystate", service, "off"])
        run(["networksetup", "-setsecurewebproxystate", service, "off"])


def cert_trusted() -> bool:
    if not CA_PEM.exists():
        return False
    r = run(["security", "verify-cert", "-p", "ssl", "-c", str(CA_PEM)])
    return "successful" in (r.stdout + r.stderr)


def ensure_cert():
    if not CA_PEM.exists():
        print("[*] 首次运行，正在生成 mitmproxy 根证书...")
        p = subprocess.Popen(["mitmdump", "-q", "--listen-port", "18099"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(3)
        p.terminate()
        try:
            p.wait(timeout=5)
        except Exception:
            p.kill()
    if cert_trusted():
        return True
    print("\n" + "=" * 68)
    print("首次使用需要把 mitmproxy 根证书加入系统信任区（只做一次）")
    print("请复制下面这行到终端执行，输入开机密码：\n")
    print(f"  sudo security add-trusted-cert -d -r trustRoot "
          f"-k /Library/Keychains/System.keychain {CA_PEM}")
    print("\n执行完再重新运行本工具即可。")
    print("=" * 68)
    return False


def capture() -> dict | None:
    raw = Path.home() / ".clairline" / "capture_raw.jsonl"
    if raw.exists():
        raw.unlink()
    ADDON_PATH.write_text(ADDON_SRC, encoding="utf-8")

    service = active_service()
    print(f"[*] 网络服务: {service}")
    print(f"[*] 启动嗅探器 :{PORT} ...")
    proc = subprocess.Popen(
        ["mitmdump", "-q", "-p", str(PORT), "-s", str(ADDON_PATH)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(2.5)
    set_proxy(service, True)
    print("[✓] 系统代理已开启")

    try:
        print("\n" + "=" * 68)
        print("👉 现在请在 微信 → 长龙航空小程序 → 「我的」页面")
        print("   随便点一次畅飞卡 / 积分兑换查询，程序会自动捕获。")
        print(f"   等待中（最长 {TIMEOUT} 秒，Ctrl+C 可随时中止）...")
        print("=" * 68 + "\n")
        deadline = time.time() + TIMEOUT
        while time.time() < deadline:
            if raw.exists() and raw.stat().st_size > 10:
                try:
                    return json.loads(raw.read_text(encoding="utf-8"))
                except Exception:
                    pass
            time.sleep(0.5)
        return None
    finally:
        set_proxy(service, False)
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
        print("[✓] 系统代理已恢复直连")


def save(rec: dict) -> bool:
    body = rec.get("body") or ""
    if "paras=" not in body:
        return False
    try:
        paras = json.loads(body.split("paras=", 1)[1])
        params = json.loads(paras["Parameters"])
    except Exception:
        return False

    headers = dict(rec.get("headers") or {})
    headers["Accept-Encoding"] = "gzip, deflate"
    if not headers.get("Authorization"):
        return False

    data = {
        "headers": headers,
        "template": {k: v for k, v in params.items() if k != "certNumber"},
        "cert_number": params.get("certNumber", ""),
        "captured_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "note": "由 refresh_token.py 抓取",
    }
    CRED_PATH.parent.mkdir(parents=True, exist_ok=True)
    CRED_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.chmod(CRED_PATH, 0o600)
    return True


def enrich_profile():
    """抓完顺手把会员姓名/等级补进档案"""
    try:
        from seccard_client import SecCardClient
        c = SecCardClient()
        r = c.call_api("sales_user_userDetailInfo",
                       {"SaleChannel": 76, "saleChannel": 76, "language": "zh-cn"})
        data = json.loads(CRED_PATH.read_text(encoding="utf-8"))
        data["user_name"] = r.get("Name") or data.get("user_name")
        data["member_level"] = f"乘云会员 L{r.get('Level')}" if r.get("Level") else "乘云会员"
        data["mobile"] = r.get("Mobile", "")
        data["card_no"] = r.get("BU_FPCardNo", "")
        data["is_verified"] = 1 if r.get("IsCertified") else 0
        if r.get("encryptedUserId"):
            data["template"]["encryptedUserId"] = r["encryptedUserId"]
        CRED_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.chmod(CRED_PATH, 0o600)
        import mac_auth
        mac_auth.sync_credential_file_to_db()
        print(f"[✓] 会员档案: {data['user_name']} / {data['member_level']}")
    except Exception as e:
        print(f"[!] 补充会员档案失败（不影响使用）: {e}")


def main():
    if not ensure_cert():
        return 1
    rec = capture()
    if not rec:
        print("\n[!] 超时未捕获到请求。请确认：")
        print("    1. 微信里确实打开了长龙航空小程序并且进入了「我的」")
        print("    2. 小程序是重新打开的（旧连接不走代理）")
        return 1
    if not save(rec):
        print("[!] 解析捕获数据失败，请重试")
        return 1
    print(f"[✓] 登录态已保存到 {CRED_PATH}")
    enrich_profile()
    print("\n完成，刷新浏览器页面即可使用。")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n[!] 已中止，代理已恢复")
        sys.exit(130)