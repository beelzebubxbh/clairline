#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
长龙航空官方接口客户端（手机短信直登版）

包含两块能力：
1. 登录：发送短信验证码 → 提交验证码换 Token → refreshToken 无感续期
2. 档案：拿到 Token 后拉取会员姓名、实名状态、畅飞卡授权 ID

设计说明：
- 只用标准库（urllib），不引入 requests。本项目除它之外零第三方依赖。
- 登录接口同样受长龙 WAF 的 Accept-Encoding 校验，缺了会 403，这里统一补齐。
"""
from __future__ import annotations

import gzip
import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

LOONGAIR_GATEWAY_URL = "https://www.loongair.cn/webhandler.ashx"
MINI_REFERER = "https://servicewechat.com/wx0a991d42d653886e/605/page-frame.html"

# 与微信小程序真机一致的 UA（Mac 版微信）
MINI_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781"
    "(0x6700143B) NetType/WIFI MiniProgramEnv/Mac MacWechat/WMPF MacWechat/3.8.7"
    "(0x13080712) UnifiedPCMacWechat(0xf2641b50) XWEB/20008"
)

CRED_PATH = Path.home() / ".clairline" / "credentials.json"

# 登录态失效需要重新登录时抛这个，便于上层返回 401
class LoginRequired(RuntimeError):
    pass


def _base_headers(auth_token: str = "") -> Dict[str, str]:
    h = {
        "User-Agent": MINI_UA,
        "Referer": MINI_REFERER,
        "X-App-Version": "2.4.77",
        "NESign": "[object Null]",
        "xweb_xhr": "1",
        "Accept": "*/*",
        # 缺这个头会被 WAF 判 403 —— 实测结论，不是猜测
        "Accept-Encoding": "gzip, deflate",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    }
    if auth_token:
        h["Authorization"] = auth_token
        h["Cookie"] = f"SESSION={auth_token}"
    return h


def _post(method: str, params: dict, headers: Dict[str, str],
          timeout: float = 20.0) -> Optional[dict]:
    """统一调用长龙 webhandler.ashx"""
    payload = {
        "AppID": "ClientService",
        "MethodName": method,
        "Parameters": json.dumps(params, ensure_ascii=False),
    }
    body = ("paras=" + urllib.parse.quote(json.dumps(payload, ensure_ascii=False))).encode("utf-8")

    h = dict(headers)
    h.setdefault("Accept-Encoding", "gzip, deflate")

    req = urllib.request.Request(LOONGAIR_GATEWAY_URL, data=body, headers=h, method="POST")
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(req, timeout=timeout) as r:
            raw = r.read()
            enc = (r.headers.get("Content-Encoding") or "").lower()
            if raw[:2] == b"\x1f\x8b" or "gzip" in enc:
                raw = gzip.decompress(raw)
            return json.loads(raw.decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        print(f"[LoongAir] {method} HTTP {e.code}")
    except Exception as e:
        print(f"[LoongAir] {method} 请求异常: {e}")
    return None


def _call_api(method: str, params: dict, headers: Dict[str, str],
              timeout: float = 8.0) -> Optional[dict]:
    return _post(method, params, headers, timeout)


def _safe_parse_result(res: Optional[dict]) -> Any:
    """安全解析长龙返回的 Result 字段 (转义 JSON 字符串)"""
    if not res or not isinstance(res, dict):
        return None
    raw_res = res.get("Result")
    if raw_res is None:
        return None
    if isinstance(raw_res, (dict, list)):
        return raw_res
    if isinstance(raw_res, str):
        raw_res = raw_res.strip()
        if (raw_res.startswith("{") and raw_res.endswith("}")) or \
           (raw_res.startswith("[") and raw_res.endswith("]")):
            try:
                return json.loads(raw_res)
            except Exception:
                pass
        return raw_res
    return raw_res


def fetch_full_user_profile(headers: Dict[str, str]) -> Dict[str, Any]:
    """
    轻量快速获取会员核心档案与畅飞卡信息 (极速精简版)
    """
    profile: Dict[str, Any] = {
        "user_name": "长龙会员",
        "mobile": "",
        "member_level": "乘云会员",
        "cert_number": "",
        "card_name": "长龙畅飞卡",
        "encrypted_user_id": "",
        "sec_card_grant_tid": "",
        "is_verified": 0
    }

    default_params = {"SaleChannel": 76, "saleChannel": 76, "language": "zh-cn"}

    # 1. 核心接口：查询用户基本信息与实名认证状态
    detail_res = _call_api("sales_user_userDetailInfo", default_params, headers)
    detail_data = _safe_parse_result(detail_res)
    if isinstance(detail_data, dict):
        name = detail_data.get("Name") or detail_data.get("aliasName")
        if name:
            profile["user_name"] = str(name).strip()

        mobile = detail_data.get("Mobile")
        if mobile:
            profile["mobile"] = str(mobile).strip()

        foid = detail_data.get("Foid")
        if foid:
            profile["cert_number"] = str(foid).strip()
        elif detail_data.get("IDInfoList") and isinstance(detail_data["IDInfoList"], list) and len(detail_data["IDInfoList"]) > 0:
            profile["cert_number"] = detail_data["IDInfoList"][0].get("foid", "")

        enc_id = detail_data.get("encryptedUserId")
        if enc_id:
            profile["encrypted_user_id"] = str(enc_id).strip()

        if detail_data.get("ifReal") is True or detail_data.get("IsCertified") == 1 or detail_data.get("authFlg") is True:
            profile["is_verified"] = 1

        lvl = str(detail_data.get("Level", "1"))
        level_map = {"1": "乘云会员 (菁英卡)", "2": "银卡会员", "3": "金卡会员", "4": "白金卡会员"}
        profile["member_level"] = level_map.get(lvl, "乘云会员")

    # 2. 核心接口：查询畅飞卡授权 ID 与卡信息
    card_res = _call_api("cardToC_getUnionCardList",
                         {"cardTypes": 0, "cardStatus": [0], "SaleChannel": 76,
                          "saleChannel": 76, "language": "zh-cn"}, headers)
    card_data = _safe_parse_result(card_res)
    if isinstance(card_data, dict):
        cards = card_data.get("cardInfoList", [])
        if isinstance(cards, list) and len(cards) > 0:
            plus_info = cards[0].get("plusCard", {})
            if plus_info:
                p_name = plus_info.get("ppoPlusProductName")
                if p_name:
                    profile["card_name"] = str(p_name).strip()
                scg = plus_info.get("scgTid") or plus_info.get("ppgTid")
                if scg:
                    profile["sec_card_grant_tid"] = str(scg)
                if plus_info.get("psgName") and profile["user_name"] == "长龙会员":
                    profile["user_name"] = str(plus_info["psgName"]).strip()

    return profile


# ---------------------------------------------------------------------------
# 登录相关
# ---------------------------------------------------------------------------

def send_sms_code(mobile: str, check_param: str) -> dict:
    """
    请求官方下发短信验证码。

    check_param 来自网易易盾滑块验证通过后的 validate 字符串。
    长龙侧要求带 CN31_ 区域前缀，没带的话这里自动补。
    """
    mobile = (mobile or "").strip()
    if len(mobile) != 11 or not mobile.isdigit():
        return {"ok": False, "error": "请输入正确的 11 位手机号"}
    if not check_param:
        return {"ok": False, "error": "请先完成安全验证（滑块）"}

    if not check_param.startswith("CN"):
        check_param = f"CN31_{check_param}"

    params = {
        "checkParam": check_param,
        "verifyCodeType": 9,
        "mobile": mobile,
        "userLoginLog": {
            "channel": "WECHAT_MINI_PROGRAM",
            "deviceInfo": "microsoft,windows10",
            "clientInfo": "小程序",
            "appVersion": "2.4.77",
        },
        "SaleChannel": 76,
        "saleChannel": 76,
        "language": "zh-cn",
    }

    res = _post("/user/clientNoLogin/channel/getVerifyCode", params, _base_headers())
    if not res:
        return {"ok": False, "error": "短信接口无响应，请稍后重试"}

    if res.get("ErrorCode") == 0:
        result = _safe_parse_result(res) or {}
        verify_id = result.get("verifyId", "") if isinstance(result, dict) else ""
        return {"ok": True, "message": "验证码已发送", "verifyId": verify_id}

    return {
        "ok": False,
        "error": f"{res.get('message') or '发送失败'} (代码 {res.get('ErrorCode')})",
        "code": res.get("ErrorCode"),
    }


def login_with_code(mobile: str, code: str, verify_id: str = "") -> dict:
    """提交短信验证码完成登录，落库并返回会员信息"""
    mobile = (mobile or "").strip()
    code = (code or "").strip()
    if not mobile or not code:
        return {"ok": False, "error": "手机号与验证码不能为空"}

    params = {
        "channelType": 4,
        "mobile": mobile,
        "code": code,
        "verifyId": verify_id or "",
        "userLoginLog": {
            "channel": "WECHAT_MINI_PROGRAM",
            "deviceInfo": "microsoft,windows10",
            "clientInfo": "小程序",
            "appVersion": "2.4.77",
        },
        "SaleChannel": 76,
        "saleChannel": 76,
        "language": "zh-cn",
    }

    res = _post("/user/clientNoLogin/channel/mobileCodeLogin", params, _base_headers())
    if not res:
        return {"ok": False, "error": "登录接口无响应，请稍后重试"}

    if res.get("ErrorCode") != 0:
        return {
            "ok": False,
            "error": f"{res.get('message') or '登录失败'} (代码 {res.get('ErrorCode')})",
            "code": res.get("ErrorCode"),
        }

    result = _safe_parse_result(res) or {}
    token = result.get("loongairToken", "")
    refresh = result.get("refreshToken", "")
    if not token:
        return {"ok": False, "error": "官方返回登录成功，但缺少 Token"}

    headers = _base_headers(token)
    profile = fetch_full_user_profile(headers)

    persist_profile(
        token=token,
        refresh_token=refresh,
        mobile=mobile,
        profile=profile,
        encrypted_user_id=result.get("encryptedUserId", ""),
    )

    masked = f"{mobile[:3]}****{mobile[-4:]}" if len(mobile) == 11 else mobile
    return {
        "ok": True,
        "message": f"欢迎回来，{profile.get('user_name') or '长龙会员'}",
        "user_name": profile.get("user_name") or "长龙会员",
        "member_level": profile.get("member_level") or "乘云会员",
        "mobile": masked,
        "has_card": bool(profile.get("sec_card_grant_tid")),
    }


def refresh_access_token() -> dict:
    """
    用本地 refreshToken 无感换新 loongairToken。

    注意：本项目不再按「自然日」强制作废凭据，
    所以这个函数是真正的兜底，而不是摆设。
    """
    import db
    prof = db.get_user_profile() or {}
    rt = prof.get("refresh_token") or _read_cred_file().get("refresh_token") or ""
    if not rt:
        return {"ok": False, "error": "缺少 refreshToken，无法自动续期"}

    params = {
        "refreshToken": rt,
        "token": prof.get("token") or "",
        "userId": prof.get("user_id") or "",
        "encryptedUserId": prof.get("encrypted_user_id") or "",
        "userLoginLog": {
            "channel": "WECHAT_MINI_PROGRAM",
            "deviceInfo": "microsoft,windows10",
            "clientInfo": "小程序",
            "appVersion": "2.4.77",
        },
        "SaleChannel": 76,
        "saleChannel": 76,
        "language": "zh-cn",
    }

    # 说明：官方并未公开续期方法名。以下两个路径是社区流传的写法，
    # 实测网关均返回 Not Found（内部路由不存在），所以续期大概率不会成功。
    # 保留这段是为了「万一将来官方放开」以及避免静默异常，失败时由上层提示重新登录。
    res = None
    for method in ("/user/clientNoLogin/channel/refreshToken",
                   "/user/client/channel/refreshToken"):
        res = _post(method, params, _base_headers())
        if res and res.get("ErrorCode") == 0:
            break
    if not res or res.get("ErrorCode") != 0:
        return {"ok": False, "error": (res or {}).get("message") or "官方未开放续期接口"}

    result = _safe_parse_result(res) or {}
    token = result.get("loongairToken") or result.get("token") or ""
    if not token:
        return {"ok": False, "error": "续期返回中没有新 Token"}

    headers = _base_headers(token)
    profile = fetch_full_user_profile(headers)
    persist_profile(
        token=token,
        refresh_token=result.get("refreshToken") or rt,
        mobile=profile.get("mobile") or prof.get("mobile") or "",
        profile=profile,
        encrypted_user_id=result.get("encryptedUserId") or prof.get("encrypted_user_id") or "",
    )
    return {"ok": True, "message": "已自动续期"}


# ---------------------------------------------------------------------------
# 持久化
# ---------------------------------------------------------------------------

def _read_cred_file() -> dict:
    try:
        if CRED_PATH.exists():
            return json.loads(CRED_PATH.read_text(encoding="utf-8")) or {}
    except Exception:
        pass
    return {}


def _build_template(profile: dict) -> dict:
    return {
        "departureAirportCode": "",
        "arriveAirportCode": "",
        "departureTime": "",
        "disabilityIDType": 1,
        "ifNonCompany": False,
        "tripType": 1,
        "encryptedUserId": profile.get("encrypted_user_id", ""),
        "directionType": "",
        "bookingScenario": 1,
        "secCardGrantTid": str(profile.get("sec_card_grant_tid", "")),
        "certNumber": profile.get("cert_number", ""),
        "SaleChannel": 76,
        "saleChannel": 76,
        "language": "zh-cn",
    }


def persist_profile(token: str, refresh_token: str, mobile: str,
                    profile: dict, encrypted_user_id: str = "") -> None:
    """同时写入 SQLite 与 ~/.clairline/credentials.json，保证两条读取路径一致"""
    headers = _base_headers(token)
    template = _build_template(profile)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    data = {
        "headers": headers,
        "template": template,
        "cert_number": profile.get("cert_number", ""),
        "refresh_token": refresh_token,
        "captured_at": now_str,
        "user_name": profile.get("user_name") or "长龙会员",
        "member_level": profile.get("member_level") or "乘云会员",
        "mobile": mobile or profile.get("mobile", ""),
        "card_name": profile.get("card_name") or "长龙畅飞卡",
        "is_verified": profile.get("is_verified", 0),
        "source": "sms-login",
    }
    CRED_PATH.parent.mkdir(parents=True, exist_ok=True)
    CRED_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        CRED_PATH.chmod(0o600)
    except Exception:
        pass

    try:
        import db
        db.save_user_profile({
            "user_name": data["user_name"],
            "mobile": data["mobile"],
            "member_level": data["member_level"],
            "cert_number": data["cert_number"],
            "token": token,
            "cookie": f"SESSION={token}",
            "card_name": data["card_name"],
            "encrypted_user_id": profile.get("encrypted_user_id", "") or encrypted_user_id,
            "sec_card_grant_tid": template["secCardGrantTid"],
            "refresh_token": refresh_token,
            "headers": headers,
            "template": template,
            "updated_at": now_str,
        })
    except Exception as e:
        print(f"[LoongAir] 写入数据库失败: {e}")

    try:
        import mac_auth
        mac_auth.clear_expired()
    except Exception:
        pass

    try:
        from seccard_client import SecCardClient
        SecCardClient().check_and_reload(force=True)
    except Exception:
        pass