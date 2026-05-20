"""
解读服务层。

设计纪律(参照交付包的明确要求):
  - 逐字引用 vedic_interpret 的 SYSTEM_PROMPT 与 build_user_prompt,不复制、不改写。
  - ChartResult 转回 vedic_interpret.CHART 期望的 dict 形状,再喂给 build_user_prompt,
    保证模型拿到的是真实 nakshatra + 真实 dasha 时间线,杜绝自行推算。
  - 调 Anthropic 的环节由 main.py 控制;本模块只负责把 prompt 拼对。
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

from .models import ChartResult
from .vedic_interpret import SYSTEM_PROMPT, build_user_prompt  # 逐字引用,不复制

# 重新导出,方便 main.py 引用同一份(并显式表明这里没改写)
__all__ = ["SYSTEM_PROMPT", "build_prompts", "chart_to_dict"]


def chart_to_dict(chart: ChartResult) -> Dict[str, Any]:
    """
    把 ChartResult(Pydantic)折成 vedic_interpret.CHART 同款 dict。
    任何字段名 / 含义都对齐 vedic_interpret.py 定稿示例,不引入新约定。

    关键:
      - planets 字典 key 是中文行星名(太阳/月亮/.../Rahu/Ketu),
        与 vedic_interpret.build_user_prompt 渲染时的 `f"- {name}:..."` 行一致。
      - dasha_timeline 是 (planet_cn, start_year, end_year) 三元组列表,
        第一段的 start_year 是字面量 "出生",其余为四位整数。
    """
    return {
        "ascendant": {
            "sign": chart.ascendant.sign,
            "nakshatra": chart.ascendant.nakshatra,
            "pada": chart.ascendant.pada,
        },
        "planets": {
            name: {
                "sign": p.sign,
                "house": p.house,
                "nakshatra": p.nakshatra,
                # vedic_interpret.build_user_prompt 用 p.get('note') 判断要不要加括号。
                # 我们只在有非空 note 时下放该字段。
                **({"note": p.note} if p.note else {}),
            }
            for name, p in chart.planets.items()
        },
        "current_dasha": {
            "mahadasha": chart.current_dasha.mahadasha,
            "maha_period": chart.current_dasha.maha_period,
            "antardasha": chart.current_dasha.antardasha,
            # build_user_prompt 直接把 note 追在 antardasha 行之后,
            # 空 note 会渲染出一个空行;给个空串保底。
            "note": chart.current_dasha.note or "",
        },
        "dasha_timeline": [
            (seg.planet, seg.start_year, seg.end_year)
            for seg in chart.dasha_timeline
        ],
    }


def build_prompts(
    chart: ChartResult,
    today: str | None = None,
) -> Tuple[str, str, str]:
    """
    返回 (system_prompt, user_prompt, resolved_today)。
    system_prompt 直接来自 vedic_interpret(逐字保留);user_prompt 由 build_user_prompt 拼。
    """
    resolved_today = today or chart.meta.today
    chart_dict = chart_to_dict(chart)
    user_prompt = build_user_prompt(chart_dict, today=resolved_today)
    return SYSTEM_PROMPT, user_prompt, resolved_today
