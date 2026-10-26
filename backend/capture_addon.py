#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
长龙航空 · 畅飞卡全自动凭据嗅探器 (智能双模抓取版)
特性：
1. 启动时自动检测系统代理：未开启则【自动开启】(127.0.0.1:8080)，已开启则保持；
2. 智能嗅探：一旦捕获有效 Token，立即主动向长龙官方接口全量同步【姓名、等级、实名状态、卡包、券包、积分】；
3. 双重保险：同时对微信小程序响应报文进行多层递归反序列化解析；
4. 退出时全自动恢复关闭系统代理，平稳直连，零手动配置。
"""

import os
import sys
import json
import urllib.parse
from datetime import datetime
from pathlib import Path
import ctypes
import winreg
import threading

try:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from mitmproxy import http, ctx

BACKEND_DIR = Path(__file__).resolve().parent
for p in [BACKEND_DIR, BACKEND_DIR.parent, Path.cwd(), Path.cwd() / "backend"]:
    p_str = str(p.resolve())
    if p_str not in sys.path:
        sys.path.insert(0, p_str)

IPC_FILE_ENV = os.environ.get("CLAIRLINE_IPC_FILE")
if IPC_FILE_ENV:
    IPC_FILE = Path(IPC_FILE_ENV).resolve()
else:
    IPC_FILE = BACKEND_DIR / "data" / ".capture_ipc.json"
IPC_FILE.parent.mkdir(parents=True, exist_ok=True)

try:
    from loongair_client import fetch_full_user_profile
except Exception:
    fetch_full_user_profile = None

KEEP_HEADERS = (
    "authorization",
    "nesign",
    "cookie",
    "x-app-version",
    "user-agent",
    "referer",
    "xweb_xhr",
    "accept",
    "accept-encoding",
    "accept-language"
)

def is_proxy_enabled() -> bool:
    """检测当前 Windows 系统代理是否开启"""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
            0,
            winreg.KEY_READ
        )
        val, _ = winreg.QueryValueEx(key, "ProxyEnable")
        winreg.CloseKey(key)
        return bool(val)
    except Exception:
        return False

def set_system_proxy(enable: bool, host: str = "127.0.0.1:8080"):
    """使用 WinINet API 即时开启/关闭系统代理，并设置免代理白名单防 IDE 断连"""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
            0,
            winreg.KEY_WRITE
        )
        winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1 if enable else 0)
        if enable:
            winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, host)
            override = "*.googleapis.com;*.google.com;*.github.com;<local>"
            winreg.SetValueEx(key, "ProxyOverride", 0, winreg.REG_SZ, override)
        winreg.CloseKey(key)

        ctypes.windll.wininet.InternetSetOptionW(0, 39, 0, 0)
        ctypes.windll.wininet.InternetSetOptionW(0, 37, 0, 0)
    except Exception as e:
        print(f"[!] 切换系统代理提示: {e}", flush=True)

def cleanup_proxy_if_needed():
    """恢复系统代理为关闭状态"""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
            0,
            winreg.KEY_READ
        )
        try:
            enable, _ = winreg.QueryValueEx(key, "ProxyEnable")
        except Exception:
            enable = 0
        try:
            server, _ = winreg.QueryValueEx(key, "ProxyServer")
        except Exception:
            server = ""
        winreg.CloseKey(key)

        if enable and "8080" in server:
            set_system_proxy(False)
            print("[*] 已确保系统代理恢复关闭，网络恢复直连。", flush=True)
    except Exception:
        pass

class LoongAirCapture:
    def __init__(self):
        self.captured = False
        self.was_proxy_enabled = is_proxy_enabled()
        self.data = self._load_existing()
        self.sync_trigger_lock = threading.Lock()
        self.has_triggered_sync = False

    def _load_existing(self) -> dict:
        return {
            "update_time": "",
            "headers": {},
            "template": {},
            "search_template": {},
            "calendar_template": {},
            "profile": {}
        }

    def running(self):
        # 智能检测：如果当前没开启，则全自动开启
        if not self.was_proxy_enabled:
            set_system_proxy(True, "127.0.0.1:8080")
            print("[+] 检测到系统代理未开启，已为你【全自动开启代理】(127.0.0.1:8080)！", flush=True)
        else:
            print("[*] 检测到系统代理已处于开启状态，保持当前设置。", flush=True)

        print("\n" + "=" * 65, flush=True)
        print("[+] 智能嗅探服务已就绪 (监听端口: 8080)", flush=True)
        print("[*] 请在微信电脑版打开【长龙航空】小程序，程序将智能完成捕获！", flush=True)
        print("=" * 65 + "\n", flush=True)

    def done(self):
        # 如果是脚本自动开启的，退出时自动关闭还原
        if not self.was_proxy_enabled:
            set_system_proxy(False)
            print("\n[-] 已全自动关闭系统代理，网络恢复直连！\n", flush=True)

    def _extract_profile_from_json(self, data: any) -> dict:
        """从长龙小程序返回的 JSON 中递归深度扫描提取会员档案（支持嵌套 JSON 字符串反序列化）"""
        res = {}
        stack = [data]
        
        while stack:
            cur = stack.pop()
            
            # 如果是 JSON 字符串，尝试反序列化
            if isinstance(cur, str):
                cur_str = cur.strip()
                if (cur_str.startswith("{") and cur_str.endswith("}")) or (cur_str.startswith("[") and cur_str.endswith("]")):
                    try:
                        parsed = json.loads(cur_str)
                        stack.append(parsed)
                    except Exception:
                        pass
                continue
                
            if isinstance(cur, dict):
                for k, v in cur.items():
                    low_k = k.lower()
                    
                    # 真实姓名 (提取中文名)
                    if low_k in ("chinesename", "username", "realname", "custname", "name", "fullname") and isinstance(v, str) and v:
                        clean_v = v.strip()
                        if len(clean_v) >= 2 and len(clean_v) <= 12 and not any(x in clean_v for x in ["系统", "服务", "长龙", "用户", "客票", "null", "undefined"]):
                            res["user_name"] = clean_v
                    
                    # 会员级别 (如: "乘云会员 (菁英卡)")
                    if low_k in ("currentleveldes", "membergradename", "gradename", "cardtypename", "levelname") and isinstance(v, str) and v:
                        clean_l = v.strip()
                        if clean_l and not clean_l.isdigit():
                            res["member_level"] = clean_l if "会员" in clean_l else f"乘云会员 ({clean_l})"

                    # 券包数量 (如: 7)
                    if low_k in ("couponcount", "couponnum", "coupons", "couponqty"):
                        try: res["coupons_count"] = int(v)
                        except Exception: pass

                    # 卡包数量 (如: 1)
                    if low_k in ("cardcount", "cardnum", "cards", "cardqty"):
                        try: res["cards_count"] = int(v)
                        except Exception: pass

                    # 积分 (如: 0)
                    if low_k in ("integral", "currentintegral", "point", "points", "availableintegral"):
                        try: res["points"] = int(float(v))
                        except Exception: pass

                    # 实名认证
                    if low_k in ("ifreal", "isreal", "iscertified", "authflg", "isrealname", "isauth", "authstatus", "realnameverified"):
                        res["is_verified"] = 1 if (v == 1 or v is True or str(v).lower() in ("true", "1", "y")) else 0

                    # 手机号
                    if low_k in ("mobile", "phone", "phonenumber") and isinstance(v, str) and len(v) == 11 and v.isdigit():
                        res["mobile"] = v

                    # 身份证号
                    if low_k in ("foid", "certnumber", "realfoid") and isinstance(v, str) and len(v) >= 15:
                        res["cert_number"] = v

                    # 畅飞卡信息
                    if low_k in ("ppoplusproductname", "cardname") and isinstance(v, str) and v:
                        res["card_name"] = v
                    if low_k in ("scgtid", "ppgtid", "seccardgranttid") and v:
                        res["sec_card_grant_tid"] = str(v)
                    if low_k in ("encrypteduserid",) and isinstance(v, str) and len(v) > 20:
                        res["encrypted_user_id"] = v

                    if isinstance(v, (dict, list, str)):
                        stack.append(v)
            elif isinstance(cur, list):
                for item in cur:
                    if isinstance(item, (dict, list, str)):
                        stack.append(item)
        return res

    def _sync_to_db_and_file(self):
        """将当前收集到的凭据通过原子 IPC 文件提交给主程序，由主进程写入 SQLite 并销毁临时文件"""
        try:
            temp_path = IPC_FILE.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            temp_path.replace(IPC_FILE)
            print("[IPC] 凭据数据已成功提交主程序管道！", flush=True)
        except Exception as e:
            print(f"[!] 写入 IPC 文件异常: {e}", flush=True)

    def _sync_full_profile(self, headers: dict):
        """核心智能机制：捕获到 Token 时，立即请求长龙官方接口获取真实姓名与等级，齐全后一次性落库"""
        with self.sync_trigger_lock:
            if self.has_triggered_sync:
                return
            self.has_triggered_sync = True

        def worker():
            try:
                print("[*] 正在向长龙官方接口请求会员身份...", flush=True)
                if fetch_full_user_profile:
                    full_prof = fetch_full_user_profile(headers)
                    if not self.data.get("profile"):
                        self.data["profile"] = {}
                    self.data["profile"].update(full_prof)
                    
                    # 资料齐全后一次性写入 credentials.json 与 SQLite
                    self._sync_to_db_and_file()
                    
                    user_name = full_prof.get("user_name") or "长龙会员"
                    self.captured = True
                    now_str = datetime.now().strftime("%H:%M:%S")
                    print("\n" + "=" * 65, flush=True)
                    print(f"[SUCCESS] [{now_str}] 智能抓取成功！已获取长龙会员档案！", flush=True)
                    print(f"  👤 会员姓名: {user_name} ({'已实名' if full_prof.get('is_verified') else '未实名'})")
                    print(f"  🏷️ 会员级别: {full_prof.get('member_level', '乘云会员')}")
                    print(f"[IPC] 会员档案已成功移交主程序落库！")
                    print("=====================================================", flush=True)
                    print("[DONE] 抓取圆满完成！正在平稳恢复系统代理为直连...\n", flush=True)
                    self._delayed_shutdown(0.5)
            except Exception as ex:
                print(f"[!] 智能全量同步提示: {ex}", flush=True)
                self._sync_to_db_and_file()
                self._delayed_shutdown(0.5)

        threading.Thread(target=worker, daemon=True).start()

    def _delayed_shutdown(self, delay: float = 0.5):
        """延迟退出，确保当前长龙微信小程序的数据报文正常收发，不发生断网错误"""
        def do_quit():
            import time
            time.sleep(delay)
            ctx.master.shutdown()
        threading.Thread(target=do_quit, daemon=True).start()

    def request(self, flow: http.HTTPFlow) -> None:
        if self.captured:
            return

        if "loongair.cn" not in flow.request.pretty_url:
            return

        body_text = flow.request.get_text()
        method_name = ""
        params = {}

        if body_text and "paras=" in body_text:
            try:
                raw_paras = body_text.split("paras=", 1)[1]
                decoded_paras = urllib.parse.unquote(raw_paras)
                parsed_body = json.loads(decoded_paras)
                method_name = parsed_body.get("MethodName", "")
                params_str = parsed_body.get("Parameters", "{}")
                params = json.loads(params_str) if isinstance(params_str, str) else params_str
            except Exception:
                pass

        auth_token = flow.request.headers.get("Authorization") or flow.request.headers.get("authorization")
        if not auth_token:
            return

        # 提取并保存最新 Header
        extracted_headers = {}
        for k, v in flow.request.headers.items():
            if k.lower() in KEEP_HEADERS:
                extracted_headers[k] = v

        self.data["headers"].update(extracted_headers)
        self.data["update_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if "seccardsearchflights" in method_name.lower():
            self.data["search_template"] = params
            self.data["template"] = params
        elif "calendar" in method_name.lower():
            self.data["calendar_template"] = params
            if not self.data.get("template"):
                self.data["template"] = params
        elif params and not self.data.get("template"):
            self.data["template"] = params

        print(f"[*] 拦截到长龙请求: {method_name or flow.request.path[:35]} (已锁定有效 Authorization: {auth_token[:12]}...)", flush=True)

        # 核心保障：拦截到有效 Token 第一时间瞬时落库 SQLite 锁定基本盘，确保首页打开即可秒级嗅探成功！
        self._sync_to_db_and_file()

        # 立即在后台异步拉取会员姓名、等级与卡授权并二次补全落库
        self._sync_full_profile(self.data["headers"])

    def response(self, flow: http.HTTPFlow) -> None:
        if self.captured:
            return

        if "loongair.cn" not in flow.request.pretty_url:
            return

        try:
            content_type = flow.response.headers.get("content-type", "")
            if "json" in content_type:
                resp_text = flow.response.get_text()
                if not resp_text:
                    return

                # 解析响应 JSON
                data = json.loads(resp_text)
                extracted = self._extract_profile_from_json(data)

                if not self.data.get("profile"):
                    self.data["profile"] = {}

                updated = False
                for k, v in extracted.items():
                    if v is not None and v != "":
                        self.data["profile"][k] = v
                        updated = True

                if updated:
                    self._sync_to_db_and_file()

                user_name = self.data.get("profile", {}).get("user_name")
                if user_name and user_name != "长龙会员":
                    self.captured = True
                    now_str = datetime.now().strftime("%H:%M:%S")
                    prof = self.data["profile"]

                    print("\n" + "=" * 65, flush=True)
                    print(f"[SUCCESS] [{now_str}] 成功捕获长龙会员完整档案！", flush=True)
                    print(f"  👤 会员姓名: {prof.get('user_name')} ({'已实名' if prof.get('is_verified') else '未实名'})")
                    print(f"  🏷️ 会员级别: {prof.get('member_level', '乘云会员')}")
                    print(f"  🎟️ 账户资产: 卡包 {prof.get('cards_count', 0)} 张 | 券包 {prof.get('coupons_count', 0)} 张 | 积分 {prof.get('points', 0)}")
                    print(f"[IPC] 凭据与资料已成功移交主程序落库！")
                    print("=====================================================", flush=True)
                    print("[DONE] 抓取完成！正在平稳恢复系统代理为直连...\n", flush=True)

                    self._delayed_shutdown(1.0)
        except Exception:
            pass

addons = [LoongAirCapture()]
