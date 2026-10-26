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
IPC_FILE = DATA_DIR / ".capture_ipc.json"

def get_addon_path() -> Path:
    """智能定位 capture_addon.py 脚本路径（兼容源码运行与 PyInstaller 单文件解包环境）"""
    candidates = []
    if getattr(sys, "frozen", False):
        mei = Path(sys._MEIPASS).resolve()
        candidates.extend([
            mei / "backend" / "capture_addon.py",
            mei / "capture_addon.py",
        ])
    candidates.extend([
        Path(__file__).resolve().parent / "capture_addon.py",
        Path(__file__).resolve().parent / "backend" / "capture_addon.py",
        Path.cwd() / "backend" / "capture_addon.py",
        Path.cwd() / "capture_addon.py"
    ])
    for p in candidates:
        if p.is_file():
            return p.resolve()
    return candidates[0]

def get_mitm_cmd(addon_path: Path) -> list:
    """智能查找 mitmdump 可执行文件路径（100% 优先使用安装包自身内置的独立抓包引擎）"""
    # 1. 单文件解压模式下：100% 强制只使用软件包内置解压的 mitmdump，绝不依赖任何外部/本地开发机路径
    if getattr(sys, "frozen", False):
        mei = Path(sys._MEIPASS).resolve()
        for cand in [mei / "backend" / "mitmdump.exe", mei / "mitmdump.exe"]:
            if cand.is_file():
                return [str(cand.resolve()), "--listen-port", "8080", "-s", str(addon_path)]

    # 2. 源码开发模式：优先检查系统 PATH
    import shutil
    w = shutil.which("mitmdump")
    if w:
        return [w, "--listen-port", "8080", "-s", str(addon_path)]

    # 3. 源码回退
    return [sys.executable, "-m", "mitmproxy.tools.dump", "--listen-port", "8080", "-s", str(addon_path)]

ADDON_PATH = get_addon_path()

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def mask_mobile(m: str) -> str:
    if not m or len(m) < 7: return m or ""
    return f"{m[:3]}****{m[-4:]}"

def mask_id(c: str) -> str:
    if not c or len(c) < 8: return c or ""
    return f"{c[:6]}********{c[-4:]}"

def get_bundled_cert_path() -> Path | None:
    """获取随软件打包内置的 CA 根证书路径（保障新用户无任何旧环境时直接可用）"""
    candidates = []
    if getattr(sys, "frozen", False):
        mei = Path(sys._MEIPASS).resolve()
        candidates.extend([
            mei / "backend" / "mitmproxy-ca-cert.cer",
            mei / "mitmproxy-ca-cert.cer",
        ])
    candidates.extend([
        Path(__file__).resolve().parent / "mitmproxy-ca-cert.cer",
        Path.cwd() / "backend" / "mitmproxy-ca-cert.cer"
    ])
    for p in candidates:
        if p.is_file():
            return p.resolve()
    return None

def check_cert_installed() -> bool:
    """检查 mitmproxy CA 根证书是否已在 Windows 用户受信任根证书库中"""
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
        cert_path = Path.home() / ".mitmproxy" / "mitmproxy-ca-cert.cer"
        return cert_path.exists()

def install_root_cert() -> dict:
    """调用系统 certutil 一键导入根证书至 CurrentUser\\Root（对纯新用户自动采用内置证书并落盘）"""
    target_dir = Path.home() / ".mitmproxy"
    target_dir.mkdir(parents=True, exist_ok=True)
    cert_path = target_dir / "mitmproxy-ca-cert.cer"

    # 如果纯新用户系统 ~/.mitmproxy/ 下尚未生成证书，自动从打包内置的证书中释放并写入
    if not cert_path.exists():
        bundled = get_bundled_cert_path()
        if bundled and bundled.is_file():
            try:
                import shutil
                shutil.copy2(str(bundled), str(cert_path))
            except Exception:
                pass

    if not cert_path.exists():
        return {"ok": False, "error": "未检测到根证书文件，请先点击启动一次嗅探"}

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
    """一键重置当前登录凭据（清空 SQLite 中的 user_profile），模拟纯净新用户"""
    try:
        if CRED_FILE.exists():
            try:
                CRED_FILE.unlink(missing_ok=True)
            except Exception:
                pass
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
            "headers": {},
            "template": {},
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

    def _consume_ipc_if_any(self) -> bool:
        """主进程安全消费嗅探器输出的临时 IPC 管道数据，由主进程写入 SQLite，消费后即刻销毁临时文件"""
        if not IPC_FILE.exists():
            return False
        with self.lock:
            try:
                if not IPC_FILE.exists():
                    return False
                c = IPC_FILE.read_text(encoding="utf-8").strip()
                if not c:
                    return False
                data = json.loads(c)
                headers = data.get("headers", {})
                auth = headers.get("authorization") or headers.get("Authorization") or ""
                tpl = data.get("template", {})
                prof = data.get("profile", {})
                update_time = data.get("update_time") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                if auth and len(auth) > 15:
                    # 主程序具备完整的网络和 Python 库，请求长龙官方接口补充会员姓名与卡信息
                    try:
                        from loongair_client import fetch_full_user_profile
                        fetched = fetch_full_user_profile(headers)
                        if fetched:
                            prof.update(fetched)
                    except Exception:
                        pass

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
                        "coupons_count": prof.get("coupons_count", 0),
                        "cards_count": prof.get("cards_count", 0),
                        "points": prof.get("points", 0),
                        "is_verified": prof.get("is_verified", 0),
                        "headers": headers,
                        "template": tpl,
                        "updated_at": update_time
                    }
                    # 100% 由主进程写入 SQLite changlong.db
                    db.save_user_profile(profile)

                    try:
                        from seccard_client import SecCardClient
                        SecCardClient().check_and_reload()
                    except Exception as e:
                        print(f"⚠️ 热重载 SecCardClient 异常: {e}")

                    self.status = "success"
                    self.last_capture_time = update_time
                    user_name = profile.get("user_name", "长龙会员")
                    self.message = f"成功捕获会员凭据！(会员: {user_name}, 捕获时间: {update_time})"
                    return True
            except Exception as e:
                print(f"⚠️ 消费 IPC 管道异常: {e}")
            finally:
                try:
                    IPC_FILE.unlink(missing_ok=True)
                except Exception:
                    pass
        return False

    def get_auth_status(self) -> dict:
        """检查 SQLite 数据库中是否具备有效会员凭据（单一真实数据源）"""
        # 实时尝试消费外部嗅探器提交的 IPC 管道数据
        self._consume_ipc_if_any()

        profile = db.get_user_profile() or {}
        is_logged_in = bool(profile.get("token"))
        update_time = profile.get("updated_at", "")
        auth = profile.get("token", "")

        # 核心机制：每天北京时间 00:00 自动将凭据标记为过期清空
        today_date = datetime.now().strftime("%Y-%m-%d")
        if update_time and update_time[:10] != today_date:
            print(f"[*] 提示：检测到长龙凭证更新日期为 {update_time[:10]}，已跨越北京时间 00:00 自然日周期（微信登录态已失效），自动清空过期凭据。")
            reset_user_auth()
            profile = {}
            is_logged_in = False
            update_time = ""
            auth = ""

        # 兼容旧版本过渡：若 SQLite 为空但本地有旧的 credentials.json，做最后一次单向导入后立即删除 json 文件
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
                                "headers": headers,
                                "template": tpl,
                                "is_verified": prof.get("is_verified", 0),
                                "updated_at": update_time
                            }
                            db.save_user_profile(profile)
                # 迁移完毕，立即删除 credentials.json
                CRED_FILE.unlink(missing_ok=True)
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

            # 启动前强力杀除可能残留的旧 mitm 进程，确保 8080 端口彻底空闲可用
            try:
                subprocess.run("taskkill /F /IM mitmdump.exe /T", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                subprocess.run("taskkill /F /IM mitmweb.exe /T", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                time.sleep(0.3)
            except Exception:
                pass

            # 寻找插件脚本与 mitmdump 可执行文件
            addon_path = get_addon_path()
            if not addon_path.is_file():
                self.status = "error"
                self.message = f"未找到抓包插件脚本: {addon_path}"
                return {
                    "ok": False,
                    "status": "error",
                    "error": self.message
                }

            mitm_cmd = get_mitm_cmd(addon_path)
            print(f"[*] 启动嗅探指令: {' '.join(mitm_cmd)}")

            # Windows 下通过 CREATE_NO_WINDOW 实现彻底无黑框无弹窗静默运行
            creationflags = 0x08000000 if sys.platform == "win32" else 0

            if getattr(sys, "frozen", False):
                exe_dir = Path(sys.executable).resolve().parent
            else:
                exe_dir = Path(__file__).resolve().parent.parent
            log_dir = exe_dir / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            mitm_log = log_dir / "clairline_mitm.log"

            try:
                log_fp = open(mitm_log, "w", encoding="utf-8", errors="replace")
                env = os.environ.copy()
                env["CLAIRLINE_IPC_FILE"] = str(IPC_FILE.resolve())
                env["CLAIRLINE_DATA_DIR"] = str(DATA_DIR.resolve())
                env["CLAIRLINE_DB_PATH"] = str(getattr(db, "DB_PATH", DATA_DIR / "changlong.db").resolve())

                self.process = subprocess.Popen(
                    mitm_cmd,
                    creationflags=creationflags,
                    stdout=log_fp,
                    stderr=log_fp,
                    env=env
                )

                # 显式激活 Windows 系统代理为开启状态 (127.0.0.1:8080)
                try:
                    from proxy_util import set_system_proxy
                    set_system_proxy(True, "127.0.0.1:8080")
                except Exception as ex:
                    print(f"[!] 开启系统代理提示: {ex}")

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
                try:
                    from proxy_util import set_system_proxy
                    set_system_proxy(False)
                except Exception:
                    pass
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

        ret = proc.wait()

        # 核心兜底：进程退出瞬间，优先消费子进程提交的 IPC 管道凭据落库
        self._consume_ipc_if_any()

        with self.lock:
            if self.status == "success":
                self.process = None
                self._restore_system_proxy()
                return

            # 校验 SQLite 数据库中是否已成功持久化捕获的会员凭据
            prof = db.get_user_profile() or {}
            auth = prof.get("token") or ""
            update_time = prof.get("updated_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            if auth and len(auth) > 15:
                self.status = "success"
                self.last_capture_time = update_time
                user_name = prof.get("user_name", "长龙会员")
                self.message = f"成功捕获会员凭据！(会员: {user_name}, 捕获时间: {update_time})"

                # 清理任何磁盘残留的旧 credentials.json，防止多头存储困惑
                if CRED_FILE.exists():
                    try:
                        CRED_FILE.unlink(missing_ok=True)
                    except Exception:
                        pass

                # 热重载本地 client
                try:
                    from seccard_client import SecCardClient
                    SecCardClient().check_and_reload()
                except Exception as e:
                    print(f"⚠️ 热重载 SecCardClient 异常: {e}")
            else:
                self.status = "error"
                self.message = "未捕获到有效授权 Token，请确认在微信小程序中打开了【我的】页面"

            self.process = None
            self._restore_system_proxy()
            return

        if self.status == "capturing":
            if ret != 0:
                self.status = "error"
                self.message = f"嗅探服务异常退出 (退出码 {ret})，详情请查看 logs/clairline_mitm.log"
            else:
                self.status = "idle"
                self.message = "嗅探服务已退出"

            self.process = None
            self._restore_system_proxy()

# 单例导出
capture_mgr = CaptureManager()
