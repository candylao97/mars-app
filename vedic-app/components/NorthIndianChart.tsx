/**
 * North Indian D1 chart.
 *
 * 几何:
 *   - 外正方形
 *   - 两条对角线(corner→corner)
 *   - 内菱形(连四条边中点)
 *   合计把内部切成 12 个区:4 个内菱形被 X 切成 4 个小菱形 + 4 个外角各被一条对角线切成 2,共 8 个外三角。
 *
 * 房位编号(House 1 永远是顶上那个小菱形 = 上升所在宫;从 House 1 往左上 → 逆时针编号到 12):
 *
 *           +-----------------+
 *           | \   12 | 1  / 11|
 *           |  \    /|\    /  |
 *           |   \  / | \  /   |
 *           | 2  \/  |  \/  10|
 *           |    /\  |  /\    |
 *           |   /  \ | /  \   |
 *           |  / 3  \|/  9  \ |
 *           | /     /\\      \|
 *           +-------+/4\------+
 *           | \     /\ |\     /|
 *           |  \   /  \|/  \ / |
 *           |  ..(同上对称)..   |
 *           +-----------------+
 *
 * (实际几何就是上下左右对称的)
 */

import type {
  ChartResult,
  PlanetName,
  ZodiacSign,
} from "@/lib/contract";

export type PlanetGlyph = {
  abbrev: string; // 行星缩写:日月火水木金土罗计
  isRetrograde?: boolean;
  isDebilitated?: boolean;
  isExalted?: boolean;
};

export type HouseData = {
  signLabel?: string; // 该宫所在星座中文,如 "处女"。可选。
  planets?: PlanetGlyph[];
};

/** 行星 → 单字中文缩写。罗/计是中文星命学对 Rahu/Ketu 的正统译法(罗睺/计都)。 */
const PLANET_GLYPHS: Record<PlanetName, string> = {
  太阳: "日",
  月亮: "月",
  火星: "火",
  水星: "水",
  木星: "木",
  金星: "金",
  土星: "土",
  Rahu: "罗",
  Ketu: "计",
};

const ZODIAC_SIGNS: ZodiacSign[] = [
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
];

/**
 * 把后端的 ChartResult 折成 chart 组件要的 houses 字典。
 * 整宫制:上升星座所在那一宫为第 1 宫,按黄道顺序往后排。
 */
export function chartToHouses(
  chart: ChartResult,
): Partial<Record<number, HouseData>> {
  const ascIdx = chart.ascendant.sign_index;
  const houses: Partial<Record<number, HouseData>> = {};
  for (let h = 1; h <= 12; h++) {
    const signIdx = (ascIdx + h - 1) % 12;
    houses[h] = { signLabel: ZODIAC_SIGNS[signIdx], planets: [] };
  }
  (Object.keys(chart.planets) as PlanetName[]).forEach((name) => {
    const p = chart.planets[name];
    const slot = houses[p.house];
    if (!slot) return;
    slot.planets!.push({
      abbrev: PLANET_GLYPHS[name],
      isRetrograde: p.retrograde,
      isDebilitated: p.dignity === "debilitated",
      isExalted: p.dignity === "exalted",
    });
  });
  return houses;
}

interface Props {
  /** house 1..12 → 该宫数据。骨架预览时不传。 */
  houses?: Partial<Record<number, HouseData>>;
  /** 渲染尺寸(像素)。默认 320。 */
  size?: number;
  /** 骨架预览模式:在每宫角落画半透明的房位号。 */
  showHouseNumbers?: boolean;
}

// SVG viewBox = 100 × 100 单位
const S = 100;

// 每宫的视觉中心锚点(用来摆星座 + 行星缩写)
const ANCHORS: Record<number, { x: number; y: number }> = {
  1: { x: 50, y: 25 }, // 顶小菱形
  2: { x: 25, y: 9 }, // 左上外三角(贴顶边)
  3: { x: 9, y: 25 }, // 左上外三角(贴左边)
  4: { x: 25, y: 50 }, // 左小菱形
  5: { x: 9, y: 75 }, // 左下外三角(贴左边)
  6: { x: 25, y: 91 }, // 左下外三角(贴底边)
  7: { x: 50, y: 75 }, // 底小菱形
  8: { x: 75, y: 91 }, // 右下外三角(贴底边)
  9: { x: 91, y: 75 }, // 右下外三角(贴右边)
  10: { x: 75, y: 50 }, // 右小菱形
  11: { x: 91, y: 25 }, // 右上外三角(贴右边)
  12: { x: 75, y: 9 }, // 右上外三角(贴顶边)
};

// 骨架预览时,房位号摆在锚点稍微偏上,星座/行星才能摆主位
const NUMBER_OFFSET: Record<number, { dx: number; dy: number }> = {
  1: { dx: 0, dy: -10 },
  2: { dx: 0, dy: -5 },
  3: { dx: -5, dy: 0 },
  4: { dx: -10, dy: 0 },
  5: { dx: -5, dy: 0 },
  6: { dx: 0, dy: 5 },
  7: { dx: 0, dy: 10 },
  8: { dx: 0, dy: 5 },
  9: { dx: 5, dy: 0 },
  10: { dx: 10, dy: 0 },
  11: { dx: 5, dy: 0 },
  12: { dx: 0, dy: -5 },
};

const STROKE_LIGHT = "currentColor";

export function NorthIndianChart({
  houses,
  size = 320,
  showHouseNumbers = false,
}: Props) {
  return (
    <svg
      viewBox={`0 0 ${S} ${S}`}
      width={size}
      height={size}
      className="text-foreground"
      style={{ maxWidth: "100%", height: "auto" }}
      aria-label="North Indian birth chart"
      role="img"
    >
      {/* 卡片底 */}
      <rect
        x={0}
        y={0}
        width={S}
        height={S}
        fill="var(--card)"
        stroke={STROKE_LIGHT}
        strokeWidth={0.6}
      />
      {/* 两条对角线 */}
      <line
        x1={0}
        y1={0}
        x2={S}
        y2={S}
        stroke={STROKE_LIGHT}
        strokeWidth={0.4}
      />
      <line
        x1={S}
        y1={0}
        x2={0}
        y2={S}
        stroke={STROKE_LIGHT}
        strokeWidth={0.4}
      />
      {/* 内菱形 */}
      <polygon
        points={`${S / 2},0 ${S},${S / 2} ${S / 2},${S} 0,${S / 2}`}
        fill="none"
        stroke={STROKE_LIGHT}
        strokeWidth={0.4}
      />

      {/* 房位号(骨架) */}
      {showHouseNumbers &&
        Object.entries(ANCHORS).map(([h, p]) => {
          const off = NUMBER_OFFSET[+h];
          return (
            <text
              key={h}
              x={p.x + off.dx}
              y={p.y + off.dy}
              textAnchor="middle"
              dominantBaseline="central"
              fontSize={3.2}
              fill="currentColor"
              opacity={0.35}
              fontWeight={500}
            >
              {h}
            </text>
          );
        })}

      {/* 每宫数据(星座 + 行星) */}
      {houses &&
        (Object.keys(houses) as unknown as Array<keyof typeof houses>).map(
          (k) => {
            const h = Number(k);
            const data = houses[h];
            if (!data) return null;
            const anchor = ANCHORS[h];
            return <HouseContent key={h} anchor={anchor} data={data} />;
          },
        )}

      {/* 上升标记:House 1 顶角小三角(用 accent) */}
      {houses && (
        <polygon
          points={`${S / 2 - 2},2 ${S / 2 + 2},2 ${S / 2},5`}
          fill="var(--accent)"
        />
      )}
    </svg>
  );
}

function HouseContent({
  anchor,
  data,
}: {
  anchor: { x: number; y: number };
  data: HouseData;
}) {
  const planets = data.planets ?? [];
  const hasSign = Boolean(data.signLabel);

  return (
    <g>
      {/* 星座(小,muted) */}
      {hasSign && (
        <text
          x={anchor.x}
          y={anchor.y - (planets.length ? 4 : 0)}
          textAnchor="middle"
          dominantBaseline="central"
          fontSize={3}
          fill="currentColor"
          opacity={0.5}
        >
          {data.signLabel}
        </text>
      )}
      {/* 行星缩写,垂直叠加 */}
      {planets.map((p, i) => {
        const color = p.isExalted
          ? "var(--accent)"
          : p.isDebilitated
            ? "var(--debility)"
            : "currentColor";
        return (
          <text
            key={i}
            x={anchor.x}
            y={anchor.y + (hasSign ? 0 : -((planets.length - 1) * 2)) + i * 4}
            textAnchor="middle"
            dominantBaseline="central"
            fontSize={3.6}
            fontWeight={500}
            fill={color}
          >
            {p.abbrev}
            {p.isRetrograde ? "ʳ" : ""}
            {p.isDebilitated ? "↓" : ""}
            {p.isExalted ? "↑" : ""}
          </text>
        );
      })}
    </g>
  );
}
