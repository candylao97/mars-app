"""
排盘回归测试。

固定输入(用户已用 AstroSage 交叉验证过):
  本地时间   1997-08-13 09:55
  IANA tz   Asia/Shanghai
  坐标      22.5431°N, 114.0579°E
  reference today 2026-05-20

预期(任何代码改动都不得破坏):
  上升 = 处女
  月亮 = 天蝎,星宿 = Anuradha
  2026-05-20 当前 mahadasha = 金星

测试同时打印完整盘,方便人工对照 AstroSage。
"""

import json

import pytest

from app.chart_service import build_chart


BIRTH_LOCAL = "1997-08-13T09:55:00"
TZ = "Asia/Shanghai"
LAT = 22.5431
LON = 114.0579
TODAY = "2026-05-20"


@pytest.fixture(scope="module")
def chart():
    return build_chart(BIRTH_LOCAL, TZ, LAT, LON, TODAY)


def test_ascendant_is_virgo(chart):
    assert chart.ascendant.sign == "处女", (
        f"上升星座错了:期待 处女,实际 {chart.ascendant.sign} "
        f"({chart.ascendant.longitude}°)"
    )


def test_moon_sign_is_scorpio(chart):
    moon = chart.planets["月亮"]
    assert moon.sign == "天蝎", (
        f"月亮星座错了:期待 天蝎,实际 {moon.sign} ({moon.longitude}°)"
    )


def test_moon_nakshatra_is_anuradha(chart):
    moon = chart.planets["月亮"]
    assert moon.nakshatra == "Anuradha", (
        f"月亮 nakshatra 错了:期待 Anuradha,实际 {moon.nakshatra}"
    )


def test_current_mahadasha_is_venus_on_2026_05_20(chart):
    assert chart.current_dasha.mahadasha == "金星", (
        f"2026-05-20 大运错了:期待 金星,实际 {chart.current_dasha.mahadasha}"
    )


def test_meta_constants_are_locked(chart):
    """三个致命设置必须固定。任何人改算法,这一条会先炸出来。"""
    assert chart.meta.ayanamsa == "Lahiri"
    assert chart.meta.house_system == "WholeSign"
    assert chart.meta.node_type == "mean"


def test_dump_full_chart(chart, capsys):
    """打印完整盘,方便人工对照 AstroSage 细节(全部行星宫位 + 完整大运时间线)。"""
    print("\n" + "=" * 70)
    print("REGRESSION CHART DUMP")
    print(f"  birth_local : {BIRTH_LOCAL}  {TZ}")
    print(f"  birth_utc   : {chart.meta.birth_utc}")
    print(f"  coords      : {LAT}, {LON}")
    print(f"  today       : {TODAY}")
    print("=" * 70)
    print(
        f"\n上升:{chart.ascendant.sign}座 {chart.ascendant.longitude}° "
        f"(星宿 {chart.ascendant.nakshatra} pada {chart.ascendant.pada})"
    )

    print("\n行星 (sidereal/Lahiri, Whole sign):")
    print(f"  {'行星':6}{'星座':6}{'宫':>4} {'黄经':>10}  {'星宿':<22}{'pada':>5}  备注")
    for name in [
        "太阳",
        "月亮",
        "火星",
        "水星",
        "木星",
        "金星",
        "土星",
        "Rahu",
        "Ketu",
    ]:
        p = chart.planets[name]
        note = p.note or ""
        print(
            f"  {name:6}{p.sign:6}{p.house:>4} {p.longitude:>9.4f}°  "
            f"{p.nakshatra:<22}{p.pada:>5}  {note}"
        )

    print("\nVimshottari mahadasha 时间线:")
    for seg in chart.dasha_timeline:
        print(
            f"  {seg.planet:6} {seg.start_year!s:>6} → {seg.end_year}  "
            f"({seg.start} → {seg.end})"
        )

    print("\n当前大运:")
    cd = chart.current_dasha
    print(f"  Mahadasha   : {cd.mahadasha}  {cd.maha_period}  ({cd.maha_start} → {cd.maha_end})")
    print(f"  Antardasha  : {cd.antardasha}  ({cd.antar_start} → {cd.antar_end})")
    print(f"  Note        : {cd.note}")
    print("=" * 70 + "\n")

    # 同时把 ChartResult 完整序列化到 stdout,供查问题用
    print("FULL JSON:")
    print(json.dumps(chart.model_dump(), ensure_ascii=False, indent=2))

    captured = capsys.readouterr()
    # 让 pytest 直接 echo 出来,不被吞
    import sys

    sys.stdout.write(captured.out)
