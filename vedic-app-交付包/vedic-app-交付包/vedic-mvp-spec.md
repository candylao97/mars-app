# 吠陀占星排盘 MVP — 产品技术规格

> 给 Claude Code 的实现说明。目标：做出一个能输入出生信息、生成本命盘、并由 AI 给出「本命盘 + 当前 dasha 周期」中文解读的 Web 应用。先验证解读质量，不追求功能全。

---

## 0. 一句话目标

用户输入出生年月日时 + 出生地点 → 系统计算吠陀本命盘（D1 拉希盘）与当前 Vimshottari mahadasha/antardasha → AI 生成结构化中文解读 → 页面展示盘式图 + 解读文本。

---

## 1. 技术栈（已定，请勿替换）

- **框架**：Next.js（App Router，TypeScript）
- **前端样式**：Tailwind CSS，简洁极简风（浅色背景、克制留白、单一强调色）
- **行星计算**：Python 后端，使用 `pyswisseph`（Swiss Ephemeris 的 Python 绑定）
  - 计算逻辑放在独立的 Python 服务 / serverless function，Next.js 通过内部 API 调用
  - 如果部署环境难以跑 Python，退路是 Node 的 `swisseph` npm 包，但**首选 Python**
- **AI 解读**：调用 Anthropic Messages API（claude，模型用最新可用版本），不在前端暴露 API key，走后端代理
- **数据库**：第一版可以不接数据库（输入即算即弃）。如果要做"保存我的盘"，用 SQLite/Postgres，但**标记为可选，先不做**
- **地理编码**：出生地点 → 经纬度，用一个免费 geocoding API（如 Nominatim/OpenStreetMap），并需要时区
- **时区**：出生时间必须按出生地的历史时区转成 UTC 再计算（关键，见 §5 精度坑）

---

## 2. 用户流程（MVP 只做这一条主线）

1. 落地页：一句话价值主张 + "开始排盘"按钮
2. 输入表单：
   - 姓名（可选，仅用于解读称呼）
   - 出生日期（年月日）
   - 出生时间（时分，需提示用户尽量精确，并标注"不确定时间会影响上升星座准确度"）
   - 出生地点（文本输入 + 自动补全，转经纬度 + 时区）
3. 提交 → loading → 结果页
4. 结果页：
   - 上半部分：盘式图（SVG）+ 关键信息表（上升、各行星落宫落星座、当前 dasha）
   - 下半部分：AI 中文解读（结构化分段）

---

## 3. 计算模块规格（核心，务必正确）

### 3.1 输入归一化
- 出生地点 → (lat, lon, timezone)
- 出生本地时间 + timezone → UTC datetime
- UTC datetime → Julian Day（pyswisseph `swe.julday`）

### 3.2 Ayanamsa（岁差，吠陀占星的灵魂参数）
- 使用 **Lahiri ayanamsa**（`swe.SIDM_LAHIRI`），这是印度官方与 B.V. Raman 体系外最通用的标准
- **重要**：必须设置 sidereal mode（`swe.set_sid_mode`），否则算出来是西洋占星的回归黄道，整个盘是错的
- 在规格备注里留一个 TODO：未来可让用户在 Lahiri / Raman ayanamsa 间切换（Raman 体系用的是 Raman ayanamsa，与 Lahiri 差约 0.5°）

### 3.3 需要计算的行星
- 太阳、月亮、水星、金星、火星、木星、土星
- Rahu（北交点）与 Ketu（南交点）——用平均交点或真交点，**默认用 mean node**，并标注
- 不需要天王/海王/冥王（传统吠陀不用）

### 3.4 上升（Lagna / Ascendant）
- 用 `swe.houses_ex` 配 sidereal flag 计算上升点
- 宫位制：**Whole Sign（整宫制）**——吠陀传统用整宫制，即上升所在星座为第 1 宫，整个星座算一宫。**不要用 Placidus**

### 3.5 落宫落星座
- 每颗行星的 sidereal 黄经 → 落在哪个星座（30° 一个）→ 按整宫制落在第几宫
- 每颗行星 → 落在哪个 nakshatra（27 个，每个 13°20'）及第几 pada（每 nakshatra 4 pada）

### 3.6 Vimshottari Dasha
- 基于**月亮所在 nakshatra**起算
- 27 nakshatra 对应 9 个行星主星，120 年大循环
- 各 mahadasha 年数：Ketu 7 / 金星 20 / 太阳 6 / 月亮 10 / 火星 7 / Rahu 18 / 木星 16 / 土星 19 / 水星 17
- 需算出：出生时所处 dasha、以及**当前日期所处的 mahadasha + antardasha**（第二层）
- 输出当前 dasha 的起止日期

---

## 4. AI 解读模块规格

### 4.1 输入给 AI 的结构化数据
把计算结果整理成 JSON 传给模型，至少包含：
- 上升星座
- 每颗行星：星座、宫位、nakshatra
- 当前 mahadasha 行星 + antardasha 行星 + 起止时间

### 4.2 Prompt 设计原则
- **System prompt 写明体系**：以 B.V. Raman 风格的吠陀占星判读为基础，避免西洋占星术语，避免泛泛的"星座性格"鸡汤
- 解读分段输出（用 JSON 或明确小标题），建议结构：
  1. 整体格局（上升 + 月亮 + 主要行星配置）
  2. 性格与天赋
  3. 当前 dasha 阶段主题（这是付费感的来源，要具体到"这段时期适合/注意什么"）
  4. 一句温和的总结
- **语气**：中文，专业但温暖，不绝对化、不制造恐慌（"土星 dasha 一定破财"这种不要）
- 让模型只输出解读，不要复述原始数据

### 4.3 调用方式
- 后端 API route 调 Anthropic API，前端不接触 key
- 流式输出可选（体验更好，但非必须）

---

## 5. 精度坑（务必让 Claude Code 注意，否则盘是错的）

1. **必须设 sidereal mode + Lahiri ayanamsa**，否则算成西洋盘
2. **必须用整宫制**，不要 Placidus
3. **出生时间→UTC 必须按出生地历史时区**，不能直接用 UTC 偏移硬编码（夏令时、历史时区变更会出错）
4. **经纬度精度**会影响上升，地理编码要尽量准
5. Rahu/Ketu 永远相差 180°，Ketu = Rahu + 180°
6. dasha 计算依赖月亮 nakshatra 内的精确位置（已走过的比例决定第一个 dasha 的剩余年数），别只取整

---

## 6. 验收标准（MVP 算完成的定义）

- [ ] 输入一组已知出生信息，算出的上升星座、月亮星座、当前 mahadasha 与权威吠陀软件（如 Jagannatha Hora / AstroSage）结果一致
- [ ] 盘式图能正确显示 12 宫 + 行星落点（North 或 South Indian 式皆可，先做一种）
- [ ] AI 解读能输出结构化中文，覆盖本命格局 + 当前 dasha 主题
- [ ] 全流程从输入到出解读 < 10 秒
- [ ] 移动端浏览器正常显示（小红书用户主要在手机上）

---

## 7. 明确不做（MVP 范围外，避免 scope 膨胀）

- 不做用户账号/登录
- 不做 D9 等分盘（D1 拉希盘足够验证）
- 不做当日 transit / 流年
- 不做合盘、择日
- 不做支付
- 不做社区/晒盘
- 不做小程序（先 Web）

> 以上是第二、三阶段的内容，验证完核心解读质量再加。

---

## 8. 给 Claude Code 的起步建议

1. 先搭 Next.js + Tailwind 骨架
2. 先把 Python 计算模块跑通（可先用命令行测一组出生数据，对照 AstroSage 校验）
3. 计算正确后再接前端表单和结果页
4. 最后接 AI 解读
5. 每一步用一组固定的测试出生数据回归，确保盘不算错
