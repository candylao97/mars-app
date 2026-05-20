"""
地点 → (lat, lon, IANA tz) 解析。

Nominatim 拿候选地点列表(经纬度 + 显示名),timezonefinder 反查每个候选的 IANA 时区名。

Nominatim 使用条款:
- 必须带描述性 User-Agent
- 限速 ≤ 1 req/s(前端 debounce + 后端轻量调用即可满足)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

import httpx
from timezonefinder import TimezoneFinder
from zhconv import convert as zh_convert

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "vedic-mvp/0.1 (contact: candylao97@gmail.com)"

# TimezoneFinder 初始化偏重,只做一次
_tf = TimezoneFinder()


def _clean_display_name(raw: str) -> str:
    """
    Nominatim 在 Accept-Language: zh 下会把同名地点用 ';' 并列繁简两份,
    且部分字段是繁体(墨爾本 / 臺北市 / 紐約)。统一处理:
      1. 每个逗号段里只取 ';' 前的第一种写法(通常是简体或唯一名称)
      2. 全文 zh-hans 化,把残留繁体收掉
    例子:
      "纽约;紐約, 纽约州;紐約州, 美国;美國" → "纽约, 纽约州, 美国"
      "墨爾本, 维多利亚州, 澳大利亚;澳洲" → "墨尔本, 维多利亚州, 澳大利亚"
      "Melbourne Airport, Golf Drive, ..., 墨爾本, 维多利亚州, 3045, 澳大利亚;澳洲"
        → "Melbourne Airport, Golf Drive, ..., 墨尔本, 维多利亚州, 3045, 澳大利亚"
    """
    if not raw:
        return raw
    segments = [seg.strip() for seg in raw.split(",")]

    def pick_first(seg: str) -> str:
        # 同段内有时是 ";" 并列(纽约;紐約),有时是 "/" 并列(东京都/Tokyo)
        for sep in (";", "/"):
            if sep in seg:
                seg = seg.split(sep, 1)[0].strip()
        return seg

    picked = [pick_first(seg) for seg in segments]
    cleaned = ", ".join(s for s in picked if s)
    return zh_convert(cleaned, "zh-hans")


@dataclass
class GeocodeHit:
    display_name: str
    lat: float
    lon: float
    tz: str

    def to_dict(self):
        return {
            "display_name": self.display_name,
            "lat": self.lat,
            "lon": self.lon,
            "tz": self.tz,
        }


async def search(query: str, limit: int = 5) -> List[GeocodeHit]:
    """文本 → 至多 limit 条候选。每条带 IANA tz 名(无法解析的直接丢弃)。"""
    q = query.strip()
    if not q:
        return []

    params = {
        "q": q,
        "format": "json",
        "limit": str(limit),
        "addressdetails": "0",
    }
    headers = {
        "User-Agent": USER_AGENT,
        # 优先返回中文名,fallback 英文
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.5",
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(NOMINATIM_URL, params=params, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    hits: List[GeocodeHit] = []
    for row in data:
        try:
            lat = float(row["lat"])
            lon = float(row["lon"])
        except (KeyError, ValueError, TypeError):
            continue
        tz = _tf.timezone_at(lat=lat, lng=lon)
        if not tz:
            continue
        hits.append(
            GeocodeHit(
                display_name=_clean_display_name(row.get("display_name", "")),
                lat=lat,
                lon=lon,
                tz=tz,
            )
        )
    return hits
