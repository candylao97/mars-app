"""
吠陀占星排盘原型 (MVP 校验用)
- 行星位置 / 上升：需要 pyswisseph (本地: pip install pyswisseph)
- nakshatra / dasha：纯逻辑，无依赖，可独立验证

用法：
  python vedic_proto.py
默认用一组示例出生数据，请改成你或 Guoshun 的真实数据，
然后把输出的 上升 / 月亮星座 / 当前 dasha 跟 AstroSage 对一下。
"""

from datetime import datetime, timedelta

# ----------------------------------------------------------------------
# 常量
# ----------------------------------------------------------------------
SIGNS = ["白羊","金牛","双子","巨蟹","狮子","处女",
         "天秤","天蝎","射手","摩羯","水瓶","双鱼"]

# 27 nakshatra 及其主星（Vimshottari 起算依据）
NAKSHATRAS = [
    ("Ashwini","Ketu"),("Bharani","Venus"),("Krittika","Sun"),
    ("Rohini","Moon"),("Mrigashira","Mars"),("Ardra","Rahu"),
    ("Punarvasu","Jupiter"),("Pushya","Saturn"),("Ashlesha","Mercury"),
    ("Magha","Ketu"),("Purva Phalguni","Venus"),("Uttara Phalguni","Sun"),
    ("Hasta","Moon"),("Chitra","Mars"),("Swati","Rahu"),
    ("Vishakha","Jupiter"),("Anuradha","Saturn"),("Jyeshtha","Mercury"),
    ("Mula","Ketu"),("Purva Ashadha","Venus"),("Uttara Ashadha","Sun"),
    ("Shravana","Moon"),("Dhanishta","Mars"),("Shatabhisha","Rahu"),
    ("Purva Bhadrapada","Jupiter"),("Uttara Bhadrapada","Saturn"),("Revati","Mercury"),
]

# Vimshottari 大运年数（合计 120 年）
DASHA_YEARS = {
    "Ketu":7,"Venus":20,"Sun":6,"Moon":10,"Mars":7,
    "Rahu":18,"Jupiter":16,"Saturn":19,"Mercury":17,
}
# dasha 主星顺序（固定循环）
DASHA_ORDER = ["Ketu","Venus","Sun","Moon","Mars","Rahu","Jupiter","Saturn","Mercury"]

NAK_SPAN = 360.0 / 27.0   # 每个 nakshatra = 13°20' = 13.3333°
YEAR_DAYS = 365.25        # dasha 计算用的年长（吠陀传统用 365.25）

# ----------------------------------------------------------------------
# 纯逻辑部分：nakshatra + Vimshottari dasha（无需 ephemeris，可验证）
# ----------------------------------------------------------------------
def moon_nakshatra(moon_lon):
    """月亮 sidereal 黄经 -> (nak名, 主星, 该nak内已走比例)"""
    idx = int(moon_lon // NAK_SPAN)
    frac = (moon_lon % NAK_SPAN) / NAK_SPAN     # 0~1，已走过的比例
    name, lord = NAKSHATRAS[idx]
    return name, lord, frac

def vimshottari_timeline(moon_lon, birth_dt):
    """
    返回从出生起的 mahadasha 时间线 [(主星, 起, 止), ...]
    关键：第一个 dasha 只剩 (1-frac) 的比例，不是完整年数。
    """
    name, lord, frac = moon_nakshatra(moon_lon)
    start_idx = DASHA_ORDER.index(lord)

    timeline = []
    cursor = birth_dt
    for i in range(9):  # 一个完整 120 年循环
        planet = DASHA_ORDER[(start_idx + i) % 9]
        full_years = DASHA_YEARS[planet]
        # 第一个 dasha 扣掉出生时已经走过的部分
        years = full_years * (1 - frac) if i == 0 else full_years
        end = cursor + timedelta(days=years * YEAR_DAYS)
        timeline.append((planet, cursor, end))
        cursor = end
    return timeline, name

def antardasha_timeline(maha_planet, maha_start, maha_end):
    """某个 mahadasha 内的 antardasha (第二层) 细分"""
    total_days = (maha_end - maha_start).days
    start_idx = DASHA_ORDER.index(maha_planet)
    out = []
    cursor = maha_start
    for i in range(9):
        sub = DASHA_ORDER[(start_idx + i) % 9]
        # antardasha 时长 = 主运时长 * (子星年数 / 120)
        days = total_days * (DASHA_YEARS[sub] / 120.0)
        end = cursor + timedelta(days=days)
        out.append((sub, cursor, end))
        cursor = end
    return out

def current_dasha(moon_lon, birth_dt, on_date=None):
    """算出 on_date 当天所处的 mahadasha + antardasha"""
    on_date = on_date or datetime.utcnow()
    timeline, nak = vimshottari_timeline(moon_lon, birth_dt)
    for planet, s, e in timeline:
        if s <= on_date < e:
            subs = antardasha_timeline(planet, s, e)
            for sub, ss, se in subs:
                if ss <= on_date < se:
                    return {
                        "nakshatra": nak,
                        "mahadasha": planet, "maha_start": s, "maha_end": e,
                        "antardasha": sub, "antar_start": ss, "antar_end": se,
                    }
    return {"nakshatra": nak, "note": "超出120年循环"}

# ----------------------------------------------------------------------
# ephemeris 部分：行星 / 上升（需要 pyswisseph，本地跑）
# ----------------------------------------------------------------------
def compute_chart(birth_utc, lat, lon):
    """需要 pyswisseph。返回上升 + 各行星 sidereal 黄经。"""
    import swisseph as swe
    swe.set_sid_mode(swe.SIDM_LAHIRI)            # ← 关键1：sidereal + Lahiri
    flag = swe.FLG_SIDEREAL | swe.FLG_SPEED

    jd = swe.julday(birth_utc.year, birth_utc.month, birth_utc.day,
                    birth_utc.hour + birth_utc.minute/60 + birth_utc.second/3600)

    planets = {
        "Sun":swe.SUN,"Moon":swe.MOON,"Mars":swe.MARS,"Mercury":swe.MERCURY,
        "Jupiter":swe.JUPITER,"Venus":swe.VENUS,"Saturn":swe.SATURN,
        "Rahu":swe.MEAN_NODE,                    # ← mean node
    }
    pos = {}
    for name, pid in planets.items():
        lonn = swe.calc_ut(jd, pid, flag)[0][0]
        pos[name] = lonn % 360
    pos["Ketu"] = (pos["Rahu"] + 180) % 360       # ← Ketu = Rahu + 180

    # 上升：sidereal + 整宫制（吠陀传统）
    asc = swe.houses_ex(jd, lat, lon, b'W', flag)[1][0]  # 'W' = Whole sign
    return asc % 360, pos

def sign_of(lon): return SIGNS[int(lon // 30)]
def house_of(lon, asc):
    """整宫制：上升所在星座为第1宫"""
    return ((int(lon//30) - int(asc//30)) % 12) + 1

# ----------------------------------------------------------------------
# 演示 / 自检
# ----------------------------------------------------------------------
if __name__ == "__main__":
    print("="*60)
    print("第一部分：dasha 引擎自检（纯逻辑，无需联网）")
    print("="*60)
    # 用一个示例月亮黄经验证 dasha 逻辑（这部分不依赖 ephemeris）
    # 假设月亮在 sidereal 123.45° -> 落在某 nakshatra
    test_moon = 123.45
    birth = datetime(1995, 6, 15, 14, 30)   # 示例出生时间(UTC)
    nak, lord, frac = moon_nakshatra(test_moon)
    print(f"月亮黄经 {test_moon}° -> nakshatra: {nak} (主星 {lord}), 已走 {frac:.1%}")

    tl, _ = vimshottari_timeline(test_moon, birth)
    print("\n出生起 mahadasha 时间线：")
    for p, s, e in tl:
        print(f"  {p:8s} {s.date()} → {e.date()}  ({(e-s).days/365.25:.1f}年)")

    cur = current_dasha(test_moon, birth, datetime(2026,5,20))
    print(f"\n2026-05-20 当前运势：")
    print(f"  Mahadasha : {cur['mahadasha']}  ({cur['maha_start'].date()} → {cur['maha_end'].date()})")
    print(f"  Antardasha: {cur['antardasha']} ({cur['antar_start'].date()} → {cur['antar_end'].date()})")

    print("\n" + "="*60)
    print("第二部分：完整排盘（需要本地 pip install pyswisseph）")
    print("="*60)
    try:
        from zoneinfo import ZoneInfo   # Python 3.9+ 标准库
        # === 改成你/Guoshun 的真实数据来校验 ===
        # 只填【当地时间】+【时区名】，历史夏令时(如中国1986-1991)由 zoneinfo 自动处理。
        tz = ZoneInfo("Asia/Shanghai")               # 出生地时区名
        #   香港=Asia/Hong_Kong  墨尔本=Australia/Melbourne  深圳/北京=Asia/Shanghai
        birth_local = datetime(1995, 6, 15, 14, 30, tzinfo=tz)  # 出生当地时间
        lat, lon    = 22.3193, 114.1694              # 出生地经纬度(这里是香港)

        # 自动换算成 UTC（zoneinfo 已含历史夏令时规则，无需手动加减）
        birth_utc = birth_local.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
        print(f"当地时间 {birth_local}  ->  UTC {birth_utc}")
        asc, pos = compute_chart(birth_utc, lat, lon)
        print(f"上升：{sign_of(asc)} ({asc:.2f}°)")
        print(f"{'行星':8s}{'星座':6s}{'宫':4s}{'黄经':>8s}")
        for name in ["Sun","Moon","Mars","Mercury","Jupiter","Venus","Saturn","Rahu","Ketu"]:
            l = pos[name]
            print(f"{name:8s}{sign_of(l):6s}{house_of(l,asc):<4d}{l:8.2f}")
        m = pos["Moon"]
        cur = current_dasha(m, birth_utc, datetime(2026,5,20))
        print(f"\n当前 dasha: {cur['mahadasha']}/{cur['antardasha']}")
        print("→ 把 上升/月亮星座/当前dasha 跟 AstroSage 对一下，一致即计算正确")
    except ImportError:
        print("(未安装 pyswisseph，跳过。本地运行: pip install pyswisseph)")
