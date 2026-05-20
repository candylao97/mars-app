"""
Pydantic 模型 —— 与 vedic-app/lib/contract.ts 字段一一对应。

任何一边改了字段,另一边必须同步;字段名/类型/枚举值必须完全一致。
"""

from __future__ import annotations

from typing import Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field

# ---------------- 枚举(与 ZODIAC_SIGNS / PLANET_NAMES 对齐) ----------------

ZodiacSign = Literal[
    "白羊",
    "金牛",
    "双子",
    "巨蟹",
    "狮子",
    "处女",
    "天秤",
    "天蝎",
    "射手",
    "摩羯",
    "水瓶",
    "双鱼",
]

PlanetName = Literal[
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

Dignity = Literal["exalted", "debilitated"]


# ---------------- 请求 ----------------


class BirthInput(BaseModel):
    """出生信息。时区一律 IANA 名,不接受 UTC 偏移整数。"""

    birth_local: str = Field(
        ...,
        description="naive 本地时间 ISO,例如 1997-08-13T09:55:00",
    )
    tz: str = Field(..., description="IANA 时区名,例如 Asia/Shanghai")
    lat: float
    lon: float
    name: Optional[str] = None
    today: Optional[str] = Field(
        default=None, description="yyyy-mm-dd;省略时由服务器填 UTC 当天"
    )


# ---------------- ChartResult 子结构 ----------------


class Ascendant(BaseModel):
    sign: ZodiacSign
    sign_index: int = Field(..., ge=0, le=11)
    longitude: float = Field(..., ge=0, lt=360)
    nakshatra: str
    pada: int = Field(..., ge=1, le=4)


class Planet(BaseModel):
    sign: ZodiacSign
    sign_index: int = Field(..., ge=0, le=11)
    house: int = Field(..., ge=1, le=12)
    longitude: float = Field(..., ge=0, lt=360)
    nakshatra: str
    pada: int = Field(..., ge=1, le=4)
    retrograde: bool
    dignity: Optional[Dignity] = None
    note: Optional[str] = None


class DashaSegment(BaseModel):
    planet: PlanetName
    start: str  # ISO date
    end: str  # ISO date
    start_year: Union[int, Literal["出生"]]
    end_year: int


class CurrentDasha(BaseModel):
    mahadasha: PlanetName
    maha_start: str
    maha_end: str
    maha_period: str
    antardasha: PlanetName
    antar_start: str
    antar_end: str
    note: Optional[str] = None


class ChartMeta(BaseModel):
    birth_local: str
    birth_utc: str
    tz: str
    lat: float
    lon: float
    today: str
    ayanamsa: Literal["Lahiri"] = "Lahiri"
    house_system: Literal["WholeSign"] = "WholeSign"
    node_type: Literal["mean"] = "mean"


class ChartResult(BaseModel):
    meta: ChartMeta
    ascendant: Ascendant
    planets: Dict[PlanetName, Planet]
    dasha_timeline: List[DashaSegment]
    current_dasha: CurrentDasha


# ---------------- 解读 ----------------


class InterpretRequest(BaseModel):
    chart: ChartResult
    today: Optional[str] = None


class InterpretUsage(BaseModel):
    input_tokens: int
    output_tokens: int
    # prompt cache 命中情况;两者都为 0 表示这次调用没用到缓存
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0


class InterpretResponse(BaseModel):
    text: str
    usage: Optional[InterpretUsage] = None


class InterpretPreviewResponse(BaseModel):
    """/interpret/preview 的返回:展示真正会喂给模型的 prompt,不调 Anthropic。
    主要用来在接通 Claude 之前,人眼核对 user_prompt 里的 nakshatra / dasha 是否真实数据。"""

    today: str
    system_prompt: str
    user_prompt: str
    # 给人眼快速扫一遍的关键字段冗余打印
    moon_sign: str
    moon_nakshatra: str
    current_mahadasha: str
    current_maha_period: str
    dasha_segment_count: int


# ---------------- Geocoding ----------------


class GeocodeRequest(BaseModel):
    q: str = Field(..., min_length=1, max_length=200)
    limit: int = Field(default=5, ge=1, le=10)


class GeocodeHit(BaseModel):
    display_name: str
    lat: float
    lon: float
    tz: str  # IANA name


class GeocodeResponse(BaseModel):
    results: List[GeocodeHit]
