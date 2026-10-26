#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
往返组合搜索

与「单航线单日查票」不同，这里回答的是：
    我从 A 出发，周末出去玩，去程 D1、回程 D2，
    哪些目的地的去程和回程【同时】还有畅飞卡座位？

数据源：
    本地 flight_calendar 表（每条航线的每日可兑状态，巡检/查票时落库）。
    往返判定 = 去程 is_available=1 AND 回程 is_available=1，一次 SQL 双向 JOIN 即可。
    所以「广撒网」模式（只给出发地、枚举全部目的地）也是毫秒级，不打外网。

精确到航班：
    日历只告诉你「那天有票」，不告诉你几点飞、还剩几张。
    需要这些细节时再调 secCardSearchFlights —— 但该接口只能查提前 3~30 天，
    超出窗口的日期会明确标记出来，不会假装查过。
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import db
from seccard_client import AuthExpired

# 去程/回程日期最多接受多少个（防止一次请求把库扫爆）
MAX_PAIRS = 40
DEFAULT_LIMIT = 60


def _parse_date(s: str):
    try:
        return datetime.strptime(s.strip(), "%Y-%m-%d").date()
    except Exception:
        return None


def _hhmm(s: str):
    """把 '18:00' 解析成分钟数；空值返回 None"""
    if not s:
        return None
    try:
        h, m = s.split(":")
        return int(h) * 60 + int(m)
    except Exception:
        return None


def _in_window(dep_time: str, after, before) -> bool:
    """dep_time 形如 '18:05'；窗口为空则不过滤"""
    if after is None and before is None:
        return True
    t = _hhmm(dep_time or "")
    if t is None:
        return True
    if after is not None and t < after:
        return False
    if before is not None and t > before:
        return False
    return True


def bookable_window():
    """接口允许的预约窗口：提前 3~30 天"""
    today = date.today()
    return today + timedelta(days=3), today + timedelta(days=30)


def city_network() -> dict:
    """
    返回本地的直飞网络（供前端做下拉框）：
        origins: 出发城市列表
        routes:  {出发城市: [可直达城市...]}
        counts:  {出发城市: 直达城市数量}
    """
    conn = db.get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT from_city, to_city FROM flight_routes ORDER BY from_city, to_city")
        routes: dict[str, list[str]] = {}
        for row in cur.fetchall():
            routes.setdefault(row["from_city"], []).append(row["to_city"])
    finally:
        conn.close()

    origins = sorted(routes.keys(), key=lambda c: (-len(routes[c]), c))
    return {
        "origins": origins,
        "routes": routes,
        "counts": {c: len(v) for c, v in routes.items()},
    }


def search(origin: str, dest: str = "", pairs: list | None = None,
           out_after: str = "", out_before: str = "",
           ret_after: str = "", ret_before: str = "",
           limit: int = DEFAULT_LIMIT, detail: bool = False,
           detail_limit: int = 6, min_seats: int = 1,
           client=None) -> dict:
    """
    origin  出发城市（中文或三字码）
    dest    目的城市，留空 = 枚举全部可达城市
    pairs   [{"out": "2026-11-07", "ret": "2026-11-09"}, ...]
    """
    origin = db.normalize_city(origin)
    if not origin:
        return {"ok": False, "error": "出发地无效"}

    dest = db.normalize_city(dest) if dest else ""

    # 1. 规整日期组合
    clean_pairs = []
    for p in (pairs or [])[:MAX_PAIRS]:
        o, r = _parse_date(p.get("out", "")), _parse_date(p.get("ret", ""))
        if not o or not r or r <= o:
            continue
        clean_pairs.append((o, r))
    if not clean_pairs:
        return {"ok": False, "error": "请至少提供一组有效的去程/回程日期"}

    out_dates = sorted({o.isoformat() for o, _ in clean_pairs})
    ret_dates = sorted({r.isoformat() for _, r in clean_pairs})
    # 合法的「去程 → 回程」配对集合（不是任意组合都算，必须来自同一组请求）
    allowed = {(o.isoformat(), r.isoformat()) for o, r in clean_pairs}

    # 2. 一次 JOIN 拿到所有「去程有票 且 回程有票」的候选
    conn = db.get_connection()
    try:
        cur = conn.cursor()
        q_marks = ",".join("?" * len(out_dates))
        r_marks = ",".join("?" * len(ret_dates))
        sql = f"""
            SELECT c1.to_city AS dest, c1.flight_date AS out_date, c2.flight_date AS ret_date
            FROM flight_calendar c1
            JOIN flight_calendar c2
              ON c2.from_city = c1.to_city
             AND c2.to_city  = c1.from_city
            WHERE c1.from_city = ?
              AND c1.is_available = 1
              AND c2.is_available = 1
              AND c1.flight_date IN ({q_marks})
              AND c2.flight_date IN ({r_marks})
        """
        params = [origin] + out_dates + ret_dates
        if dest:
            sql += " AND c1.to_city = ?"
            params.append(dest)
        cur.execute(sql, params)
        rows = [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()

    # 3. 只保留请求里出现过的配对，并按目的地聚合（同一目的地保留最早的一组日期）
    best: dict[str, dict] = {}
    for row in rows:
        pair = (row["out_date"], row["ret_date"])
        if pair not in allowed:
            continue
        d = row["dest"]
        cur_best = best.get(d)
        if cur_best is None or pair < (cur_best["out_date"], cur_best["ret_date"]):
            best[d] = {"dest": d, "out_date": row["out_date"], "ret_date": row["ret_date"]}

    results = []
    for d, item in best.items():
        o = _parse_date(item["out_date"])
        r = _parse_date(item["ret_date"])
        results.append({
            "to": d,
            "toIata": db.normalize_iata(d),
            "out": {"date": item["out_date"], "flights": []},
            "ret": {"date": item["ret_date"], "flights": []},
            "nights": (r - o).days if (o and r) else None,
        })

    # 日期越近越靠前
    results.sort(key=lambda x: (x["out"]["date"], x["to"]))
    total_cached = len(results)

    # 4. 可选：拉取具体航班（耗时、且受 3~30 天窗口限制）
    meta = {"detail": False, "detail_note": "", "detail_requested": detail}
    if detail and results:
        if client is None:
            meta["detail_note"] = "服务端未就绪，本次只返回日历级结果"
        else:
            meta = attach_flights(
                client, origin, results[:max(1, detail_limit)],
                out_after, out_before, ret_after, ret_before, min_seats,
            )
            # 指定了时间窗口时，筛掉没有符合时段航班的组合
            has_window = any([out_after, out_before, ret_after, ret_before])
            if has_window or min_seats > 1:
                results = [r for r in results if r["out"]["flights"] and r["ret"]["flights"]]

    trimmed = results[:max(1, limit)]

    return {
        "ok": True,
        "from": origin,
        "fromIata": db.normalize_iata(origin),
        "dest": dest or None,
        "query": {
            "pairs": [{"out": o.isoformat(), "ret": r.isoformat()} for o, r in sorted(clean_pairs)],
            "out_window": {"after": out_after, "before": out_before},
            "ret_window": {"after": ret_after, "before": ret_before},
        },
        "count": len(trimmed),
        "totalCached": total_cached,
        "results": trimmed,
        "truncated": total_cached > len(trimmed),
        **meta,
    }


def attach_flights(client, origin, results, out_after, out_before,
                   ret_after, ret_before, min_seats) -> dict:
    """实际实现：由 server.py 传入已初始化的 SecCardClient"""
    lo, hi = bookable_window()
    oa, ob = _hhmm(out_after), _hhmm(out_before)
    ra, rb = _hhmm(ret_after), _hhmm(ret_before)

    done = 0
    skipped_out_of_window = 0
    failed = 0

    for item in results:
        dest = item["to"]
        for leg, (frm, to) in (("out", (origin, dest)), ("ret", (dest, origin))):
            d = _parse_date(item[leg]["date"])
            if not d or d < lo or d > hi:
                skipped_out_of_window += 1
                item[leg]["flights"] = []
                item[leg]["note"] = "超出 3~30 天查询窗口，只能确认日历有票、看不到具体航班"
                continue
            # 方向：out 是 A→B，ret 是 B→A
            f_from = db.normalize_iata(frm)
            f_to = db.normalize_iata(to)
            try:
                flights = client.search_flights(f_from, f_to, item[leg]["date"]) or []
                done += 1
            except AuthExpired:
                raise
            except Exception as e:
                failed += 1
                item[leg]["note"] = f"查询失败：{str(e)[:60]}"
                flights = []

            if leg == "out":
                keep = [f for f in flights
                        if _in_window(f.get("depTime", ""), oa, ob)
                        and int(f.get("secCardLeft", 0) or 0) >= min_seats]
            else:
                keep = [f for f in flights
                        if _in_window(f.get("depTime", ""), ra, rb)
                        and int(f.get("secCardLeft", 0) or 0) >= min_seats]
            item[leg]["flights"] = keep

        # 最低总价（两程可兑价格之和）
        try:
            op = min([float(f.get("redeemPrice", 0) or 0) for f in item["out"]["flights"]], default=0)
            rp = min([float(f.get("redeemPrice", 0) or 0) for f in item["ret"]["flights"]], default=0)
            if op and rp:
                item["totalPrice"] = round(op + rp, 2)
        except Exception:
            pass

    note = ""
    if skipped_out_of_window:
        note = (f"{skipped_out_of_window} 个日期超出 3~30 天查询窗口，"
                f"这部分只确认了日历有票、没有具体航班时刻。")
    if failed:
        note += f" {failed} 次航班查询失败。"
    return {
        "detail": True,
        "detail_note": note,
        "detail_queries": done,
    }