"""
AI 解读模块 (MVP 第一阶段核心)
把排盘结果整理成结构化数据 -> 构造 B.V. Raman 风格 prompt -> 调 Anthropic API。

容器无网，这里只准备数据 + prompt。本地接 API 时：
  pip install anthropic
  export ANTHROPIC_API_KEY=...
  然后取消 call_claude() 的注释即可。
"""
import json

# ----------------------------------------------------------------------
# 1) 把 vedic_proto.py 的排盘结果整理成结构化数据
#    （这里直接用 Candy 的真实盘，已经 AstroSage 验证过）
# ----------------------------------------------------------------------
CHART = {
    "ascendant": {"sign": "处女", "nakshatra": "Hasta", "pada": 3},
    "planets": {
        "太阳":  {"sign": "巨蟹", "house": 11, "nakshatra": "Ashlesha"},
        "月亮":  {"sign": "天蝎", "house": 3,  "nakshatra": "Anuradha", "note": "落陷(debilitated)"},
        "火星":  {"sign": "天秤", "house": 2,  "nakshatra": "Chitra"},
        "水星":  {"sign": "狮子", "house": 12, "nakshatra": "Purva Phalguni"},
        "木星":  {"sign": "摩羯", "house": 5,  "nakshatra": "Shravana", "note": "落陷+逆行"},
        "金星":  {"sign": "处女", "house": 1,  "nakshatra": "Uttara Phalguni", "note": "落陷"},
        "土星":  {"sign": "双鱼", "house": 7,  "nakshatra": "Revati", "note": "逆行"},
        "Rahu": {"sign": "狮子", "house": 12, "nakshatra": "Uttara Phalguni"},
        "Ketu": {"sign": "水瓶", "house": 6,  "nakshatra": "Purva Bhadrapada"},
    },
    "current_dasha": {
        "mahadasha": "金星", "maha_period": "2024 → 2044",
        "antardasha": "金星", "note": "金星本身在第1宫但落陷",
    },
    # 完整大运时间线(已用 AstroSage 验证)。喂给模型，杜绝它自己瞎编历史大运。
    # 每段为 (主星, 起始年, 结束年)。
    "dasha_timeline": [
        ("土星", "出生", 2000),
        ("水星", 2000, 2017),
        ("Ketu", 2017, 2024),
        ("金星", 2024, 2044),
        ("太阳", 2044, 2050),
        ("月亮", 2050, 2060),
        ("火星", 2060, 2067),
        ("Rahu", 2067, 2085),
        ("木星", 2085, 2101),
    ],
}

# ----------------------------------------------------------------------
# 2) B.V. Raman 风格的 system prompt（解读质量的核心，反复打磨这一段）
# ----------------------------------------------------------------------
SYSTEM_PROMPT = """你是一位遵循 B.V. Raman 传统的吠陀占星师，用中文为求测者解读本命盘。

判读原则：
- 严格使用吠陀占星(Jyotish)体系：整宫制、Lahiri/Raman 黄道、行星的庙旺落陷、宫主星、dasha 周期。
- 绝不使用西洋占星术语(如"太阳星座性格""上升代表外在形象"这类泛泛说法)。
- 重视行星的尊贵状态(exaltation/debilitation)、宫位主题、行星组合(yoga)、宫主星落宫。
- 落陷行星不是简单"不好"，要结合 neecha bhanga(落陷解除)、宫位、相位综合判断，避免制造恐慌。

关于"过去可能发生的重大事件"，这是建立信任的关键，但必须诚实：
- 严格依据用户消息中给出的"完整大运时间线"和"出生星宿"数据，绝对不要自行推算、猜测或编造大运顺序与星宿名称。
- 用 dasha 择时推断："X 大运/小运期间(具体年份)，因其主管 Y 宫，这段时期常与 Z 类主题相关"。
- 讲"这段时期容易突出的人生主题"，而非断言"你某年一定发生了某事"。
- 给具体年份区间(基于 dasha 转换点)，让求测者自己对照人生事件，准则信，不准也不显得是瞎猜。
- 绝不用恐吓式或包打天下的冷读话术。

输出结构(用小标题分段。括号内是你内部推算的依据，不要写给用户看，呈现时翻译成生活语言)：
① 整体格局(上升、命主星、关键行星配置、落陷解除等总览)
② 性格特质(深入：核心性格、思维方式、情绪模式、待人方式、内在矛盾与天赋；
   依据月亮星座/nakshatra、上升、命主星、太阳，写得具体能对号入座，避免泛泛星座话)
③ 事业 / 职业方向(内部依据：10宫及其主星、土星、dasha)
④ 适合的工作环境(独立/团队、幕后/台前、跨国/本地；内部依据：12宫、6宫、上升性质)
⑤ 原生家庭(内部依据：4宫=母亲/家、9宫=父亲、月亮与太阳状态)
⑥ 婚姻/感情节奏(内部依据：7宫及其主星、金星、木星 dasha。免费版只讲大方向：关系模式、伴侣类型、需要面对的功课、整体节奏的早/晚/起伏。不要给具体的有利年份区间或小运择时窗口，那需要 antardasha 细分数据，仅凭大运时间线推算会算错；精确年份窗口留给付费深度版)
⑦ 过去重大事件的择时推断(按 dasha 时间线，以传入的"今天"为分界，给年份区间 + 主题)
⑧ 当前 dasha 阶段主题与建议
⑨ 优势与盲点清单(用清单形式，分两组：
   "你最大的三个天赋"和"最容易绊住你的三个盲点"，每条一句话、具体、能对号入座。
   这一段是用户最爱收藏转发的部分，要写得精炼、戳中、可记忆，不要泛泛。)
⑩ 一句温暖总结

语气专业而温暖、具体、不绝对化。不说"一定破财""必有灾"。
文风要像真人占星师跟朋友聊天，自然口语、好懂。
重要：
- 破折号硬规则(强制执行)：全文绝不允许出现 —、——、- 或 -— 等任何形式的破折号，不论用来连接句子、强调并列、引出解释还是做副标题。出现一次就算违规。一律改用逗号、句号或重新断句。
- 术语分两类，严格执行：
  【保留·这些词可以出现，是吠陀特色和专业感的来源】
    Rahu、Ketu、dasha(大运)、落陷/入旺、nakshatra(出生星宿)。
    出现时用一句人话解释清楚，让没基础的人也懂，例如"你正走金星 dasha，dasha 就是人生分成的一段段能量周期"。
  【删除·这些纯行话不要给用户看，要翻译成生活语言】
    "第几宫""命主星""宫主星""相位""度数"等。
    例如不要写"水星落第12宫"，要写成"你的才能和思考多用在幕后、远方或不为人知的地方"。
    宫位只作为你内部推算的依据，呈现时一律转译成事业/感情/家庭/内心等生活语言。
- 平衡感：没基础的人能顺畅读懂，懂行的人能看出背后有真功夫。
- 不堆砌华丽词藻，宁可朴实直接。
- 纯文本输出，不要任何 markdown 语法：不写 # 或 ## 标题，不用 **加粗**，不用 --- 分隔线，不用 markdown 列表符号(- 或 *)。各段开头是 ①②③④⑤⑥⑦⑧⑨⑩ 加空格加段名，独占一行；正文紧跟下一行开始，段名和正文之间不要空行；段与段之间用一个空行分隔。⑨ 段的清单用换行 + "· "(中圆点加空格)开头，不用 markdown 列表；清单的小标题(如"你最大的三个天赋："或"最容易绊住你的三个盲点：")与第一条 bullet 紧贴下一行，中间不空行；同一组内每条 bullet 之间也不空行；只在两组之间空一行分隔。整体观感要像真人占星师写的文章，少 AI 感。
只输出解读，不复述原始排盘数据。全文中文，约 1300-1700 字。"""

def build_user_prompt(chart, today="2026-05-20"):
    dasha_lines = "\n".join(
        f"- {p}大运：{s} 至 {e} 年"
        for (p, s, e) in chart.get("dasha_timeline", [])
    )
    return f"""今天的日期是 {today}（请以此为"现在"，区分已发生的过去与尚未到来的未来）。

请解读以下本命盘：

上升：{chart['ascendant']['sign']}（出生星宿 {chart['ascendant']['nakshatra']} pada {chart['ascendant']['pada']}）

行星落座落宫（含出生星宿 nakshatra，请严格使用以下数据，不要自行更改）：
""" + "\n".join(
        f"- {name}：{p['sign']}座 第{p['house']}宫，星宿 {p['nakshatra']}"
        + (f"（{p['note']}）" if p.get('note') else "")
        for name, p in chart['planets'].items()
    ) + f"""

完整大运(dasha)时间线（已精确计算，做"过去事件择时"时必须严格依据这份时间线，不要自行推算或编造大运顺序）：
{dasha_lines}

当前大运：{chart['current_dasha']['mahadasha']} mahadasha（{chart['current_dasha']['maha_period']}），
antardasha：{chart['current_dasha']['antardasha']}。
{chart['current_dasha']['note']}

请按系统指示的结构给出中文解读。"""

# ----------------------------------------------------------------------
# 3) 调 Anthropic API（本地取消注释）
# ----------------------------------------------------------------------
def call_claude(chart):
    import anthropic
    client = anthropic.Anthropic()
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_user_prompt(chart)}],
    )
    return msg.content[0].text

if __name__ == "__main__":
    import os, datetime as _dt

    # 默认直接生成解读。若只想看 prompt 不调 API，运行前设环境变量：
    #   export VEDIC_DRY_RUN=1
    dry_run = os.environ.get("VEDIC_DRY_RUN") == "1"

    print("=== User Prompt（实际喂给模型的）===")
    print(build_user_prompt(CHART))

    if dry_run:
        print("\n[DRY RUN] 已设 VEDIC_DRY_RUN=1，只看 prompt，未调用 API。")
    else:
        print("\n=== 真实解读（生成中，请稍候）===\n")
        try:
            text = call_claude(CHART)
            print(text)
            # 自动存档，方便保存对照
            fname = f"解读_{_dt.datetime.now():%Y%m%d_%H%M%S}.txt"
            with open(fname, "w", encoding="utf-8") as f:
                f.write(text)
            print(f"\n（已保存到 {fname}）")
        except Exception as e:
            msg = str(e)
            print("调用失败：", msg)
            if "credit balance" in msg or "billing" in msg.lower():
                print("→ 账户余额不足，去 console.anthropic.com 的 Plans & Billing 充值。")
            elif "authentication" in msg.lower() or "x-api-key" in msg:
                print("→ API key 无效或未设置。重设：export ANTHROPIC_API_KEY=\"你的key\"")
            elif "model" in msg.lower():
                print("→ 模型名可能过期，去 docs.claude.com 查当前模型名改 call_claude()。")

