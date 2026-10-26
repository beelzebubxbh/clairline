#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Windows 系统代理检测与安全重置工具
仅使用 Python 标准库 (winreg, ctypes)，无任何第三方包依赖。
"""

import ctypes
import winreg

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
