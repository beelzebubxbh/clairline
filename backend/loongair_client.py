#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
长龙航空官方接口精简客户端 (LoongAir Client)
在获取到长龙 Authorization 后，主动轻量请求核心接口：
1. sales_user_userDetailInfo：获取姓名、实名状态、手机号、证件号
2. cardToC_getUnionCardList：获取畅飞卡授权 ID (scgTid) 与产品名称
(已根据用户需求彻底省略积分、卡包数、券包数等无关接口，极速完成)
"""

import json
import urllib.parse
from typing import Dict, Any, Optional
import requests

LOONGAIR_GATEWAY_URL = "https://www.loongair.cn/webhandler.ashx"

def _call_api(method: str, params: dict, headers: dict, timeout: float = 5.0) -> Optional[dict]:
    """统一调用长龙 webhandler.ashx 接口"""
    token = headers.get("authorization") or headers.get("Authorization") or ""
    cookie = headers.get("cookie") or headers.get("Cookie") or f"SESSION={token}"
    
    req_headers = {
        "User-Agent": headers.get("user-agent") or headers.get("User-Agent") or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) MicroMessenger/7.0.20",
        "Authorization": token,
        "Cookie": cookie,
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Referer": headers.get("referer") or headers.get("Referer") or "https://servicewechat.com/wx0a991d42d653886e/605/page-frame.html",
        "xweb_xhr": "1"
    }
    
    payload = {
        "AppID": "ClientService",
        "MethodName": method,
        "Parameters": json.dumps(params, ensure_ascii=False)
    }
    body = "paras=" + urllib.parse.quote(json.dumps(payload, ensure_ascii=False))
    
    try:
        resp = requests.post(
            LOONGAIR_GATEWAY_URL,
            headers=req_headers,
            data=body,
            timeout=timeout,
            proxies={"http": None, "https": None}
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"[LoongAirClient] 请求 {method} 提示: {e}")
    return None

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
        if (raw_res.startswith("{") and raw_res.endswith("}")) or (raw_res.startswith("[") and raw_res.endswith("]")):
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
    card_res = _call_api("cardToC_getUnionCardList", {"cardTypes": 0, "cardStatus": [0], "SaleChannel": 76, "saleChannel": 76, "language": "zh-cn"}, headers)
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
