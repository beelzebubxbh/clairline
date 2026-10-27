#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
长龙航空 · 畅飞卡接口核心客户端模块
封装对 https://www.loongair.cn/webhandler.ashx 的调用
包含：余量查询、45天日历查询、官方可达航线反查
"""
from __future__ import annotations
import gzip, json, urllib.request, urllib.error
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, unquote
import zipfile

API = "https://www.loongair.cn/webhandler.ashx"
BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BACKEND_DIR.parent

# 凭据存放位置（macOS 版）：用户目录，600 权限，永不进仓库
USER_CRED_PATH = Path.home() / ".clairline" / "credentials.json"


class AuthExpired(RuntimeError):
    """登录态失效，需要重新抓取 Token。单独成类以便上层返回可识别的状态码。"""

CITY_IATA = {
 '阿勒泰':'AAT','阿拉尔':'ACF','阿克苏':'AKU','巴中':'BZX','广州':'CAN','郑州':'CGO',
 '长春':'CGQ','重庆':'CKG','长沙':'CSX','成都':'CTU','大连':'DLC','东营':'DOY',
 '张家界':'DYG','达州':'DZH','恩施':'ENH','海口':'HAK','邯郸':'HDG','呼和浩特':'HET',
 '杭州':'HGH','海拉尔':'HLD','衡阳':'HNY','哈尔滨':'HRB','菏泽':'HZA','银川':'INC',
 '西双版纳':'JHG','泉州':'JJN','嘉兴':'JNH','鸡西':'JXA','喀什':'KHG','昆明':'KMG',
 '赣州':'KOW','克拉玛依':'KRY','贵阳':'KWE','兰州':'LHW','丽江':'LJG','芒市':'LUM',
 '临沂':'LYI','泸州':'LZO','宁波':'NGB','北京':'PEK','上海':'PVG','沈阳':'SHE',
 '荆州':'SHS','三亚':'SYX','深圳':'SZX','青岛':'TAO','通化':'TNH','图木舒克':'TWC',
 '太原':'TYN','乌鲁木齐':'URC','潍坊':'WEF','威海':'WEH','茅台':'WMT','温州':'WNZ',
 '武汉':'WUH','无锡':'WUX','襄阳':'XFN','西安':'XIY','西宁':'XNN','徐州':'XUZ',
 '烟台':'YNT','珠海':'ZUH','遵义':'ZYI','包头':'BAV','南京':'NKG','南宁':'NNG',
 '常州':'CZX','柳州':'LZH','济南':'TNA','福州':'FOC','赤峰':'CIF',
}
IATA_CITY = {v: k for k, v in CITY_IATA.items()}

def _split(raw: bytes):
    p = raw.split(b"\r\n\r\n", 1)
    return p[0].decode("utf-8", "replace"), (p[1] if len(p) > 1 else b"")

def _dechunk(b: bytes) -> bytes:
    out = bytearray(); i = 0
    while True:
        j = b.find(b"\r\n", i)
        if j < 0: break
        try: size = int(b[i:j].split(b";")[0].strip(), 16)
        except Exception: break
        if size == 0: break
        out += b[j+2:j+2+size]; i = j+2+size+2
    return bytes(out)

def _resp_json_from(raw: bytes):
    head, b = _split(raw)
    if "chunked" in head.lower(): b = _dechunk(b)
    if b[:2] == b"\x1f\x8b": b = gzip.decompress(b)
    return json.loads(b.decode("utf-8", "replace"))

class SecCardClient:
    def __init__(self, saz_path: Path | None = None):
        self.explicit_saz_path = saz_path
        self.saz_path = saz_path
        self.last_mtime = 0
        self.headers: dict = {}
        self.template: dict = {}
        self.demo: dict = {}
        self.check_and_reload(force=True)

    def detect_saz_path(self) -> Path | None:
        if self.explicit_saz_path and self.explicit_saz_path.exists():
            return self.explicit_saz_path
        candidates = [
            BACKEND_DIR / "data" / "cl.saz",
            BACKEND_DIR / "data" / "changlong.saz",
            PROJECT_DIR / "cl.saz",
            PROJECT_DIR / "changlong.saz",
            Path.home() / "Desktop" / "cl.saz",
            Path.home() / "Desktop" / "changlong.saz"
        ]
        for c in candidates:
            if c.exists():
                return c
        return None

    def detect_credentials_source(self) -> tuple[str, Path] | None:
        """优先检测 credentials.json（mitmproxy 自动嗅探生成），其次检测 cl.saz"""
        try:
            import db
            db_data_dir = getattr(db, "DATA_DIR", None)
        except Exception:
            db_data_dir = None

        candidates = [USER_CRED_PATH]
        if db_data_dir:
            candidates.append(db_data_dir / "credentials.json")
        candidates.append(BACKEND_DIR / "data" / "credentials.json")
        candidates.append(PROJECT_DIR / "credentials.json")

        for c in candidates:
            if c.exists():
                return ("json", c)

        saz = self.detect_saz_path()
        if saz:
            return ("saz", saz)
        return None

    def check_and_reload(self, force: bool = False):
        """优先从 SQLite 数据库直接载入会员凭证与畅飞卡模板，秒级响应，彻底摆脱 json 文件依赖"""
        try:
            import db
            prof = db.get_user_profile()
            if prof and prof.get("token"):
                # macOS 版改动：不再按“自然日 00:00”强制作废凭据。
                # 原逻辑假设 Token 每天过期，但实际寿命由服务端决定，
                # 强制作废会丢弃明明还能用的凭据。改为“用到报错再刷新”。
                if True:
                    headers = prof.get("headers") or {}
                    if not headers:
                        headers = {
                            "Authorization": prof["token"],
                            "Cookie": prof.get("cookie") or f"SESSION={prof['token']}",
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) MicroMessenger/7.0.20",
                            "xweb_xhr": "1"
                        }
                    keep = ("Authorization", "NESign", "Cookie", "X-App-Version", "User-Agent", "Referer", "xweb_xhr", "Accept", "Accept-Encoding", "Accept-Language")
                    lower_map = {k.lower(): v for k, v in headers.items()}
                    self.headers = {}
                    for k in keep:
                        if k in headers:
                            self.headers[k] = headers[k]
                        elif k.lower() in lower_map:
                            self.headers[k] = lower_map[k.lower()]

                    template = prof.get("template") or {}
                    if prof.get("sec_card_grant_tid"):
                        template["secCardGrantTid"] = prof["sec_card_grant_tid"]
                    if prof.get("encrypted_user_id"):
                        template["encryptedUserId"] = prof["encrypted_user_id"]
                    if prof.get("cert_number"):
                        template["certNumber"] = prof["cert_number"]
                    if prof.get("mobile"):
                        template["mobile"] = prof["mobile"]
                    self.template = template
                    return
        except Exception:
            pass

        source = self.detect_credentials_source()
        if not source:
            return
        stype, spath = source
        self.saz_path = spath
        try:
            mtime = spath.stat().st_mtime
            if force or mtime != self.last_mtime or not self.headers:
                if stype == "json":
                    self.load_from_json(spath)
                else:
                    self.load_credentials()
                self.last_mtime = mtime
        except Exception:
            pass

    def load_from_json(self, json_path: Path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # macOS 版改动：移除了原版“跨自然日自动清空凭据”的逻辑。
            # 凭据是否有效交给服务端判断，失效时 call_api 会抛 AuthExpired。
            headers = data.get("headers", {})
            params = data.get("search_template") or data.get("template", {})
            if headers:
                keep = ("Authorization", "NESign", "Cookie", "X-App-Version", "User-Agent", "Referer", "xweb_xhr", "Accept", "Accept-Encoding", "Accept-Language")
                lower_map = {k.lower(): v for k, v in headers.items()}
                self.headers = {}
                for k in keep:
                    if k in headers:
                        self.headers[k] = headers[k]
                    elif k.lower() in lower_map:
                        self.headers[k] = lower_map[k.lower()]
                
                prof = data.get("profile", {})
                if not prof:
                    try:
                        import db
                        prof = db.get_user_profile() or {}
                    except Exception:
                        prof = {}

                # 核心机制：自动从会员档案中绑定 secCardGrantTid 与身份字段
                for k_param, k_prof in [
                    ("secCardGrantTid", "sec_card_grant_tid"),
                    ("encryptedUserId", "encrypted_user_id"),
                    ("certNumber", "cert_number"),
                    ("mobile", "mobile")
                ]:
                    if not params.get(k_param) and prof.get(k_prof):
                        params[k_param] = prof[k_prof]

                # macOS 版凭据文件里 certNumber 单独存放（不进模板）
                if data.get("cert_number") and not params.get("certNumber"):
                    params["certNumber"] = data["cert_number"]

                # 若缺少 encryptedUserId（如仅浏览了日历），从历史 saz 模板继承永久身份字段
                if not params.get("encryptedUserId") or not params.get("secCardGrantTid"):
                    saz_cand = self.detect_saz_path()
                    if saz_cand and saz_cand.exists():
                        try:
                            z = zipfile.ZipFile(saz_cand)
                            for n in z.namelist():
                                if n.endswith("_c.txt") and "secCardSearchFlights" in z.read(n).decode("utf-8", "ignore"):
                                    raw = z.read(n)
                                    head, body = _split(raw)
                                    btxt = body.decode("utf-8", "replace")
                                    pj = json.loads(unquote(btxt[len("paras="):]))
                                    saz_p = json.loads(pj["Parameters"])
                                    for k in ("certNumber", "encryptedUserId", "secCardGrantTid", "disabilityIDType", "bookingScenario"):
                                        if k in saz_p and k not in params:
                                            params[k] = saz_p[k]
                                    break
                        except Exception:
                            pass
                self.template = params
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔑 成功装载最新登录凭据 (来自 credentials.json，抓取于: {data.get('update_time', '未知')})")
        except Exception as e:
            print(f"⚠️ 解析 credentials.json 失败: {e}")

    def load_credentials(self):
        if not self.saz_path or not self.saz_path.exists():
            print("⚠️ 未找到 cl.saz 或 changlong.saz 文件，请将抓包文件放入 backend/data/ 目录下")
            return
        z = zipfile.ZipFile(self.saz_path)
        names = sorted(n for n in z.namelist() if n.endswith("_c.txt"))
        headers = params = None
        for n in names:
            raw = z.read(n)
            head, body = _split(raw)
            if "webhandler" not in head.split("\r\n")[0]: continue
            btxt = body.decode("utf-8", "replace")
            if not btxt.startswith("paras="): continue
            try: pj = json.loads(unquote(btxt[len("paras="):]))
            except Exception: continue
            method = pj.get("MethodName", "")
            sname = n.replace("_c.txt", "_s.txt")
            if method == "secCardSearchFlights":
                cur_headers = {}
                for ln in head.split("\r\n")[1:]:
                    if ":" in ln:
                        k, v = ln.split(":", 1); cur_headers[k.strip()] = v.strip()
                # 优先提取含有有效 Authorization 的最新会话 (支持多次覆盖)
                if cur_headers.get("Authorization"):
                    headers = cur_headers
                    params = json.loads(pj["Parameters"])
                if sname in z.namelist(): self.demo["flights"] = _resp_json_from(z.read(sname))
            if method == "getSecCardRedeemedCalendar" and sname in z.namelist():
                try: self.demo["calendar"] = _resp_json_from(z.read(sname))
                except Exception: pass
        if headers and params:
            # 关键：必须保留 Accept-Encoding，长龙 WAF 靠此识别合法请求，并在响应时 gzip 解压
            keep = ("Authorization", "NESign", "Cookie", "X-App-Version", "User-Agent", "Referer", "xweb_xhr", "Accept", "Accept-Encoding", "Accept-Language")
            self.headers = {k: headers[k] for k in keep if k in headers}
            self.template = params
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔑 成功装载最新登录凭据 (来自 {self.saz_path.name})")

    def _try_refresh(self) -> bool:
        """用 refreshToken 无感续期。成功返回 True。"""
        try:
            import mac_auth
            if mac_auth.is_marked_expired():
                return False  # 已知失效，不必再试
        except Exception:
            pass
        try:
            from loongair_client import refresh_access_token
            res = refresh_access_token()
            if res.get("ok"):
                self.check_and_reload(force=True)
                return bool(self.headers)
            print(f"[refresh] 续期未成功: {res.get('error')}")
        except Exception as e:
            print(f"[refresh] 续期异常: {e}")
        return False

    def call_api(self, method: str, params: dict, retry_on_auth_err: bool = True):
        # 调用前热重载检查
        self.check_and_reload()

        # 已判定失效就直接报错，不要再往官方接口打请求
        # （原实现每失败一次都会触发 2 次无用的续期调用，连续点击会放大故障）
        try:
            import mac_auth
            if mac_auth.is_marked_expired():
                raise AuthExpired("登录态已失效：如果刚在微信小程序里打开过长龙，网页端的会话会被顶掉。请点右上角重新登录")
        except AuthExpired:
            raise
        except Exception:
            pass

        if not self.headers:
            # 关键：先尝试用 refreshToken 自动续期。
            # 上游版本在这里直接报错，导致「跨自然日清空凭据」时续期永远用不上。
            if retry_on_auth_err and self._try_refresh():
                return self.call_api(method, params, retry_on_auth_err=False)
            raise AuthExpired("未登录：请点击右上角用手机号 + 短信验证码登录")
        body_obj = {
            "AppID": "ClientService",
            "MethodName": method,
            "Parameters": json.dumps(params, ensure_ascii=False)
        }
        data = ("paras=" + quote(json.dumps(body_obj, ensure_ascii=False))).encode("utf-8")
        h = dict(self.headers)
        h["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"

        # 长龙 WAF 硬性校验：缺少 Accept-Encoding 会直接返回 403。
        # 这是实测结论，不是猜测 —— 同一套头加上它就从 403 变 200。
        ae = (h.get("Accept-Encoding") or "").lower()
        if not ae:
            h["Accept-Encoding"] = "gzip, deflate"
        elif "br" in ae:
            # 标准库没有 brotli，去掉 br 让服务端用 gzip 就好
            h["Accept-Encoding"] = "gzip, deflate"

        req = urllib.request.Request(API, data=data, headers=h, method="POST")
        try:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(req, timeout=20) as r:
                raw_bytes = r.read()
                enc = (r.headers.get("Content-Encoding") or "").lower()
                if raw_bytes[:2] == b"\x1f\x8b" or "gzip" in enc:
                    raw_bytes = gzip.decompress(raw_bytes)
                elif "deflate" in enc:
                    import zlib
                    raw_bytes = zlib.decompress(raw_bytes)
                payload = json.loads(raw_bytes.decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                if retry_on_auth_err:
                    if self._try_refresh():
                        return self.call_api(method, params, retry_on_auth_err=False)
                    self.check_and_reload(force=True)
                    return self.call_api(method, params, retry_on_auth_err=False)
                raise AuthExpired(
                    f"登录态已失效（HTTP {e.code}）：请点击右上角用手机验证码重新登录"
                )
            raise RuntimeError(f"长龙接口 HTTP 错误: {e.code}")
        except Exception as e:
            raise RuntimeError(f"网络请求失败: {e}")

        if payload.get("ErrorCode") == 100001:
            # 未登录 / Token 过期
            if retry_on_auth_err:
                if self._try_refresh():
                    return self.call_api(method, params, retry_on_auth_err=False)
                self.check_and_reload(force=True)
                return self.call_api(method, params, retry_on_auth_err=False)
            raise AuthExpired("登录态已失效（100001）：可能刚在微信小程序里登录过，会话被顶掉了。请点右上角重新登录")

        if payload.get("ErrorCode") != 0:
            raise RuntimeError(f"长龙接口错误 ({payload.get('ErrorCode')}): {payload.get('message')}")
        res_str = payload.get("Result", "{}")
        return json.loads(res_str) if isinstance(res_str, str) else res_str

    def load_routes_index(self, frm_code: str, to_code: str) -> list[dict]:
        """从 SQLite 数据库表 flight_routes 读取真实航班班次列表"""
        fc, tc = IATA_CITY.get(frm_code, frm_code), IATA_CITY.get(to_code, to_code)
        try:
            import db
            conn = db.get_connection()
            cur = conn.cursor()
            cur.execute("""
                SELECT flight_no, dep_time, arr_time, aircraft, stopover 
                FROM flight_routes 
                WHERE from_city = ? AND to_city = ?
            """, (fc, tc))
            rows = [dict(r) for r in cur.fetchall()]
            conn.close()
            return rows
        except Exception:
            return []

    def search_flights(self, frm: str, to: str, date_str: str) -> list[dict]:
        """查询某航线某日航班与真实余量，具备高精度智能航班号反查算法"""
        frm_code = CITY_IATA.get(frm, frm)
        to_code = CITY_IATA.get(to, to)
        p = dict(self.template)
        p["departureAirportCode"] = frm_code
        p["arriveAirportCode"] = to_code
        p["departureTime"] = f"{date_str}T00:00:00"
        
        res = self.call_api("secCardSearchFlights", p)
        route_rows = self.load_routes_index(frm_code, to_code)
        
        def parse_minutes(t_str):
            try:
                parts = t_str.split(":")
                return int(parts[0]) * 60 + int(parts[1])
            except Exception:
                return 0

        flight_items = []
        for fi in res.get("flightInfos", []):
            dep = fi["departureTime"][11:16]
            arr = fi["arriveTime"][11:16]
            is_via = bool(fi.get("stopOver"))
            aircraft_official = fi.get("aircraftType", "A320")
            dep_min = parse_minutes(dep)

            # 智能反查真实航班号 (GJxxxx)
            f_no = None
            matched_aircraft = aircraft_official
            matched_stopover = "经停" if is_via else "直飞"

            # 1. 第一级：起降时刻完全一致精确匹配
            for r in route_rows:
                if r["dep_time"] == dep and r["arr_time"][:5] == arr:
                    f_no = r["flight_no"]
                    matched_aircraft = r.get("aircraft") or aircraft_official
                    matched_stopover = r.get("stopover") or matched_stopover
                    break

            # 2. 第二级：同一航线起飞时间完全一致精确匹配
            if not f_no:
                for r in route_rows:
                    if r["dep_time"] == dep:
                        f_no = r["flight_no"]
                        matched_aircraft = r.get("aircraft") or aircraft_official
                        matched_stopover = r.get("stopover") or matched_stopover
                        break

            # 3. 第三级：起飞时间允许 ±45 分钟微调（换季时段微调）模糊匹配
            if not f_no:
                best_r = None
                min_diff = 9999
                for r in route_rows:
                    diff = abs(dep_min - parse_minutes(r["dep_time"]))
                    if diff <= 45 and diff < min_diff:
                        min_diff = diff
                        best_r = r
                if best_r:
                    f_no = best_r["flight_no"]
                    matched_aircraft = best_r.get("aircraft") or aircraft_official
                    matched_stopover = best_r.get("stopover") or matched_stopover

            # 4. 万一真有未收录的未知临时加班机，显示长龙规范代码
            if not f_no:
                f_no = f"GJ{dep.replace(':', '')}"

            for c in fi.get("cabinInfos") or []:
                flight_items.append({
                    "flightNo": f_no,
                    "depTime": dep,
                    "arrTime": arr,
                    "aircraft": matched_aircraft,
                    "stopover": matched_stopover,
                    "redeemPrice": c.get("ticketPrice", 0),
                    "secCardLeft": c.get("secCardBaseLeftCount", 0),
                    "normalLeft": c.get("leftCount", 0),
                    "cabinCode": c.get("cabinCode", "M")
                })
        return flight_items

    def get_calendar(self, frm: str, to: str) -> dict:
        """查询整条航线近 60 天官方兑换日历 (1=有可兑, 0=已兑完, -1=未开放, -2=不适用, -3=已截止, -4=无航班)"""
        frm_code = CITY_IATA.get(frm, frm)
        to_code = CITY_IATA.get(to, to)
        p = {
            "scgTid": str(self.template.get("secCardGrantTid", "")),
            "departureCode": frm_code,
            "arriveCode": to_code,
            "SaleChannel": 76,
            "saleChannel": 76,
            "language": "zh-cn"
        }
        res = self.call_api("getSecCardRedeemedCalendar", p)
        raw_map = res.get("calenderMap", {})

        # 严格只保留【查询当天 + 60 天】窗口，丢弃之后 300 多天的未开放占位符
        today = datetime.now()
        if today.year < 2026: today = datetime(2026, 10, 22)
        today_str = today.strftime("%Y-%m-%d")
        from datetime import timedelta
        max_date_str = (today + timedelta(days=60)).strftime("%Y-%m-%d")
        return {d: s for d, s in raw_map.items() if today_str <= d <= max_date_str}

    def get_official_destinations(self, frm: str) -> list[str]:
        """从长龙官方直接拉取某出发地允许兑换的官方目的地城市列表"""
        frm_code = CITY_IATA.get(frm, frm)
        p = {
            "scgTid": str(self.template.get("secCardGrantTid", "")),
            "fromCode": frm_code,
            "SaleChannel": 76,
            "saleChannel": 76,
            "language": "zh-cn"
        }
        res = self.call_api("/coupon/client/getSecCardArriveAirport", p)
        dom = res.get("domAirports", {})
        cities = set()
        for letter, airports in dom.items():
            for a in airports:
                c = a.get("cityName", "")
                if "成都" in c: c = "成都"
                elif "北京" in c: c = "北京"
                elif "遵义" in c: c = "遵义"
                cities.add(c)
        return sorted(cities)
