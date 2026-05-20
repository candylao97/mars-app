"""
排盘服务层 —— 包装 vedic_proto.py 的黄金参考实现,产出 ChartResult。

不修改 vedic_proto 的任何算法,只:
1. 把出生本地时间 + IANA 时区 → naive UTC datetime(由 zoneinfo 处理历史夏令时)
2. 调 compute_chart 拿上升 + 行星位置(锁死 Lahiri / sidereal / Whole sign / mean node / Ketu = Rahu+180)
3. 调 vimshottari_timeline / current_dasha 拿大运
4. 在外层加 metadata:整宫制宫位、nakshatra、pada、dignity(静态查表)、retrograde(独立 swe.calc_ut 取速度)
5. 整理成与 vedic_interpret.CHART 对齐的形状,可零转换喂 prompt
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Dict, List, Tuple
from zoneinfo import ZoneInfo

import swisseph as swe

from . import vedic_proto as vp
from .models import (
    Ascendant,
    ChartMeta,
    ChartResult,
    CurrentDasha,
    DashaSegment,
    Planet,
    PlanetName,
    ZodiacSign,
)

# ---------------- 静态查表 ----------------

# 行星 ID(对应 swe.SUN 等)。Rahu 用 mean node;Ketu 由 Rahu+180 派生,不查 ephemeris。
SWE_PLANET_IDS = {
    "太阳": swe.SUN,
    "月亮": swe.MOON,
    "火星": swe.MARS,
    "水星": swe.MERCURY,
    "木星": swe.JUPITER,
    "金星": swe.VENUS,
    "土星": swe.SATURN,
    "Rahu": swe.MEAN_NODE,
}

# 中文行星名 → vedic_proto 内部用的英文键(用于查 dasha 时间线 / nakshatra 主星)
PLANET_CN_TO_EN = {
    "太阳": "Sun",
    "月亮": "Moon",
    "火星": "Mars",
    "水星": "Mercury",
    "木星": "Jupiter",
    "金星": "Venus",
    "土星": "Saturn",
    "Rahu": "Rahu",
    "Ketu": "Ketu",
}
PLANET_EN_TO_CN = {v: k for k, v in PLANET_CN_TO_EN.items()}

# 输出顺序固定,与 contract.ts PLANET_NAMES 对齐
PLANET_ORDER: List[PlanetName] = [
    "太阳",
    "月亮",
    "火星",
    "水星",
    "木星",
    "金星",
    "土星",
    "Rahu",
    "Ketu",
]

# 经典吠陀尊贵态(用中文星座名)。Rahu/Ketu 因学派分歧,MVP 不报告。
DIGNITY_TABLE: Dict[str, Dict[str, ZodiacSign]] = {
    "太阳": {"exalted": "白羊", "debilitated": "天秤"},
    "月亮": {"exalted": "金牛", "debilitated": "天蝎"},
    "火星": {"exalted": "摩羯", "debilitated": "巨蟹"},
    "水星": {"exalted": "处女", "debilitated": "双鱼"},
    "木星": {"exalted": "巨蟹", "debilitated": "摩羯"},
    "金星": {"exalted": "双鱼", "debilitated": "处女"},
    "土星": {"exalted": "天秤", "debilitated": "白羊"},
}

# 真正可能逆行的行星(太阳/月亮永不逆;Rahu/Ketu mean-node 始终反向,不当作"逆行"标注)
RETROGRADE_CANDIDATES = {"火星", "水星", "木星", "金星", "土星"}


# ---------------- 工具函数 ----------------


def _sign_index(longitude: float) -> int:
    return int(longitude // 30) % 12


def _sign_of(longitude: float) -> ZodiacSign:
    return vp.SIGNS[_sign_index(longitude)]  # type: ignore[return-value]


def _house_of(longitude: float, asc_longitude: float) -> int:
    """整宫制:上升所在星座为第 1 宫。"""
    return ((_sign_index(longitude) - _sign_index(asc_longitude)) % 12) + 1


def _nakshatra_and_pada(longitude: float) -> Tuple[str, int]:
    """任意 sidereal 黄经 → (nakshatra 英文名, pada 1..4)。"""
    idx = int(longitude // vp.NAK_SPAN) % 27
    pada_span = vp.NAK_SPAN / 4.0
    pada = int((longitude % vp.NAK_SPAN) / pada_span) + 1
    if pada > 4:
        pada = 4  # 防御浮点边界
    name, _lord = vp.NAKSHATRAS[idx]
    return name, pada


def _dignity_of(planet_cn: str, sign: ZodiacSign):
    table = DIGNITY_TABLE.get(planet_cn)
    if not table:
        return None
    if sign == table["exalted"]:
        return "exalted"
    if sign == table["debilitated"]:
        return "debilitated"
    return None


def _note_of(dignity, retrograde: bool):
    parts = []
    if dignity == "debilitated":
        parts.append("落陷")
    elif dignity == "exalted":
        parts.append("入旺")
    if retrograde:
        parts.append("逆行")
    if not parts:
        return None
    return "+".join(parts)


def _resolve_birth_utc(birth_local: str, tz_name: str) -> datetime:
    """naive 本地 ISO + IANA tz → naive UTC datetime(由 zoneinfo 处理历史夏令时)。"""
    naive_local = datetime.fromisoformat(birth_local)
    if naive_local.tzinfo is not None:
        raise ValueError("birth_local 必须是 naive ISO(不带时区后缀),时区单独由 tz 字段给出")
    zoned = naive_local.replace(tzinfo=ZoneInfo(tz_name))
    return zoned.astimezone(timezone.utc).replace(tzinfo=None)


def _resolve_today(today: str | None) -> str:
    if today:
        # 验证一下
        date.fromisoformat(today)
        return today
    return datetime.now(timezone.utc).date().isoformat()


def _retrograde_speeds(jd: float) -> Dict[str, float]:
    """单独取每颗行星的 sidereal 黄经速度,用于判断逆行。
    独立调用 swe.calc_ut,不修改 vedic_proto。"""
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    flag = swe.FLG_SIDEREAL | swe.FLG_SPEED
    speeds = {}
    for cn, pid in SWE_PLANET_IDS.items():
        result = swe.calc_ut(jd, pid, flag)
        # result[0] = (lon, lat, dist, lon_speed, lat_speed, dist_speed)
        speeds[cn] = result[0][3]
    return speeds


# ---------------- 主入口 ----------------


def build_chart(
    birth_local: str,
    tz_name: str,
    lat: float,
    lon: float,
    today: str | None = None,
) -> ChartResult:
    birth_utc = _resolve_birth_utc(birth_local, tz_name)
    today_str = _resolve_today(today)

    # 1. 上升 + 行星位置(原版函数,不动)
    asc_lon, positions = vp.compute_chart(birth_utc, lat, lon)

    # 2. 取速度判断逆行(独立调用,不污染 vedic_proto)
    jd = swe.julday(
        birth_utc.year,
        birth_utc.month,
        birth_utc.day,
        birth_utc.hour + birth_utc.minute / 60 + birth_utc.second / 3600,
    )
    speeds = _retrograde_speeds(jd)

    # 3. Ascendant
    asc_nak, asc_pada = _nakshatra_and_pada(asc_lon)
    ascendant = Ascendant(
        sign=_sign_of(asc_lon),
        sign_index=_sign_index(asc_lon),
        longitude=round(asc_lon, 4),
        nakshatra=asc_nak,
        pada=asc_pada,
    )

    # 4. Planets
    planets: Dict[PlanetName, Planet] = {}
    for cn in PLANET_ORDER:
        en = PLANET_CN_TO_EN[cn]
        plon = positions[en]
        sign = _sign_of(plon)
        nak, pada = _nakshatra_and_pada(plon)
        if cn in RETROGRADE_CANDIDATES:
            retrograde = speeds[cn] < 0
        else:
            retrograde = False
        dignity = _dignity_of(cn, sign)
        note = _note_of(dignity, retrograde)
        planets[cn] = Planet(
            sign=sign,
            sign_index=_sign_index(plon),
            house=_house_of(plon, asc_lon),
            longitude=round(plon, 4),
            nakshatra=nak,
            pada=pada,
            retrograde=retrograde,
            dignity=dignity,
            note=note,
        )

    # 5. Dasha timeline
    moon_lon = positions["Moon"]
    timeline_raw, _moon_nak = vp.vimshottari_timeline(moon_lon, birth_utc)
    dasha_timeline: List[DashaSegment] = []
    for i, (planet_en, s_dt, e_dt) in enumerate(timeline_raw):
        cn = PLANET_EN_TO_CN[planet_en]
        start_year: int | str = "出生" if i == 0 else s_dt.year
        dasha_timeline.append(
            DashaSegment(
                planet=cn,
                start=s_dt.date().isoformat(),
                end=e_dt.date().isoformat(),
                start_year=start_year,  # type: ignore[arg-type]
                end_year=e_dt.year,
            )
        )

    # 6. Current dasha
    today_dt = datetime.fromisoformat(today_str)
    cur = vp.current_dasha(moon_lon, birth_utc, today_dt)
    if "mahadasha" not in cur:
        raise RuntimeError(
            f"vimshottari 周期外:{cur.get('note', 'unknown')}"
        )
    maha_cn = PLANET_EN_TO_CN[cur["mahadasha"]]
    antar_cn = PLANET_EN_TO_CN[cur["antardasha"]]
    maha_start: datetime = cur["maha_start"]
    maha_end: datetime = cur["maha_end"]
    antar_start: datetime = cur["antar_start"]
    antar_end: datetime = cur["antar_end"]

    # 自动 note:描述 antardasha 主星本身在盘里的位置
    ad_planet = planets.get(antar_cn)
    if ad_planet:
        tail_parts = []
        if ad_planet.dignity == "debilitated":
            tail_parts.append("落陷")
        elif ad_planet.dignity == "exalted":
            tail_parts.append("入旺")
        if ad_planet.retrograde:
            tail_parts.append("逆行")
        tail = (",且" + "、".join(tail_parts)) if tail_parts else ""
        note = (
            f"{antar_cn}本身落{ad_planet.sign}座第{ad_planet.house}宫{tail}"
        )
    else:
        note = None

    current = CurrentDasha(
        mahadasha=maha_cn,
        maha_start=maha_start.date().isoformat(),
        maha_end=maha_end.date().isoformat(),
        maha_period=f"{maha_start.year} → {maha_end.year}",
        antardasha=antar_cn,
        antar_start=antar_start.date().isoformat(),
        antar_end=antar_end.date().isoformat(),
        note=note,
    )

    meta = ChartMeta(
        birth_local=birth_local,
        birth_utc=birth_utc.isoformat(),
        tz=tz_name,
        lat=lat,
        lon=lon,
        today=today_str,
    )

    return ChartResult(
        meta=meta,
        ascendant=ascendant,
        planets=planets,
        dasha_timeline=dasha_timeline,
        current_dasha=current,
    )
