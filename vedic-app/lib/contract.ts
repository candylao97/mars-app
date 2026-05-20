/**
 * 前后端 JSON 契约。
 *
 * Python FastAPI 端会有一份镜像的 Pydantic 模型。任何一边改了字段,另一边必须同步改。
 *
 * 字段中的中文(行星名 / 星座名)直接对齐 vedic_proto.py 与 vedic_interpret.py 里的命名,
 * 这样把 ChartResult 直接喂给 vedic_interpret.build_user_prompt 时不需要再做一层转换。
 */

// ---------- 枚举 ----------

export const ZODIAC_SIGNS = [
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
] as const;
export type ZodiacSign = (typeof ZODIAC_SIGNS)[number];

export const PLANET_NAMES = [
  "太阳",
  "月亮",
  "火星",
  "水星",
  "木星",
  "金星",
  "土星",
  "Rahu",
  "Ketu",
] as const;
export type PlanetName = (typeof PLANET_NAMES)[number];

// ---------- 请求 ----------

/**
 * 出生信息输入。
 * 时区一律用 IANA 名 (Asia/Shanghai / Asia/Hong_Kong / Australia/Melbourne 等),
 * 服务器端用 zoneinfo 解析历史夏令时再换 UTC,绝不接收 UTC 偏移整数。
 */
export interface BirthInput {
  /** 出生当地时间,naive ISO,例如 "1997-08-13T09:55:00"。不带时区后缀。 */
  birth_local: string;
  /** IANA 时区名,例如 "Asia/Shanghai"。 */
  tz: string;
  /** 出生地纬度 (decimal degrees,北纬正)。 */
  lat: number;
  /** 出生地经度 (decimal degrees,东经正)。 */
  lon: number;
  /** 用户称呼,仅用于解读中称呼;可省。 */
  name?: string;
  /** 解读用的"今天"(yyyy-mm-dd)。省略时由服务器填 UTC 当天。 */
  today?: string;
}

// ---------- 排盘结果 ----------

export interface Ascendant {
  /** 上升所在星座(中文)。 */
  sign: ZodiacSign;
  /** 0..11,与 ZODIAC_SIGNS 索引一致;方便前端做盘式图。 */
  sign_index: number;
  /** sidereal 黄经 0..360。 */
  longitude: number;
  /** 出生星宿英文名(对齐 vedic_proto.NAKSHATRAS 第一列)。 */
  nakshatra: string;
  /** 1..4。 */
  pada: number;
}

export interface Planet {
  /** 落座(中文)。 */
  sign: ZodiacSign;
  /** 0..11。 */
  sign_index: number;
  /** 整宫制宫位 1..12,基于上升所在星座为第 1 宫。 */
  house: number;
  /** sidereal 黄经 0..360。 */
  longitude: number;
  /** 出生星宿英文名。 */
  nakshatra: string;
  /** 1..4。 */
  pada: number;
  /** 是否逆行(由 pyswisseph 给的速度判断;Rahu/Ketu 不报告逆行)。 */
  retrograde: boolean;
  /** 行星尊贵态。null 表示既不入旺也不落陷;mūlatrikoṇa/own sign MVP 不输出。 */
  dignity: "exalted" | "debilitated" | null;
  /**
   * 给解读的中文备注串,vedic_interpret.build_user_prompt 直接用作 (...) 里的内容。
   * 由 dignity + retrograde 拼成,例如 "落陷"、"逆行"、"落陷+逆行"。
   * 没有则为 null。
   */
  note: string | null;
}

export interface DashaSegment {
  /** 大运主星(中文,与 build_user_prompt 用法一致)。 */
  planet: PlanetName;
  /** ISO 日期字符串。若是出生那一段,等于出生 UTC 的日期。 */
  start: string;
  /** ISO 日期字符串。 */
  end: string;
  /**
   * 给 prompt 用的年份。第一段为字面量 "出生",其他为四位整数。
   * 这样 build_user_prompt 的 "{p}大运:{s} 至 {e} 年" 渲染出来与定稿示例一致。
   */
  start_year: number | "出生";
  end_year: number;
}

export interface CurrentDasha {
  mahadasha: PlanetName;
  maha_start: string;
  maha_end: string;
  /** 给 prompt 用的展示串,例如 "2024 → 2044"。 */
  maha_period: string;
  antardasha: PlanetName;
  antar_start: string;
  antar_end: string;
  /** 简短上下文,例如 "金星本身在第1宫但落陷"。可为空。 */
  note: string | null;
}

export interface ChartMeta {
  /** 回显输入(naive 本地 ISO)。 */
  birth_local: string;
  /** 换算后的 UTC,ISO 字符串。 */
  birth_utc: string;
  tz: string;
  lat: number;
  lon: number;
  /** 解读用的"今天"(yyyy-mm-dd),回显或服务器填的。 */
  today: string;
  /** 算法常量回显,锁死,不允许变。 */
  ayanamsa: "Lahiri";
  house_system: "WholeSign";
  node_type: "mean";
}

export interface ChartResult {
  meta: ChartMeta;
  ascendant: Ascendant;
  /** 九大行星,key 为中文名,与 PLANET_NAMES 对齐。 */
  planets: Record<PlanetName, Planet>;
  /** 从出生开始的完整 9 段大运。 */
  dasha_timeline: DashaSegment[];
  current_dasha: CurrentDasha;
}

// ---------- 解读响应 ----------

export interface InterpretRequest {
  /** 完整 ChartResult。/interpret 不再重新算盘,直接使用前端传回的同一份数据。 */
  chart: ChartResult;
  /** 显式覆盖 today;省略则用 chart.meta.today。 */
  today?: string;
}

export interface InterpretResponse {
  /** 模型返回的完整中文解读。 */
  text: string;
  /** Anthropic 用量回显,可选。 */
  usage?: {
    input_tokens: number;
    output_tokens: number;
    /** prompt cache 写入字节数;首次调用 / 缓存过期后会有。 */
    cache_creation_input_tokens?: number;
    /** prompt cache 命中字节数;后续 5 分钟内同 SYSTEM_PROMPT 会有。 */
    cache_read_input_tokens?: number;
  };
}

// ---------- Geocoding ----------

export interface GeocodeRequest {
  q: string;
  limit?: number;
}

export interface GeocodeHit {
  display_name: string;
  lat: number;
  lon: number;
  /** IANA 时区名。 */
  tz: string;
}

export interface GeocodeResponse {
  results: GeocodeHit[];
}

// ---------- 错误 ----------

export interface ApiError {
  error: string;
  detail?: string;
}
