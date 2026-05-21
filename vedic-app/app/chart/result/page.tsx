"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import {
  NorthIndianChart,
  chartToHouses,
} from "@/components/NorthIndianChart";
import type { BirthInput, ChartResult, PlanetName } from "@/lib/contract";

const STORAGE_KEY = "vedic.lastChart";
const INTERPRET_KEY = "vedic.lastInterpretation";

type InterpretState =
  | { status: "idle" }
  | { status: "streaming"; text: string }
  | { status: "ok"; text: string }
  | { status: "error"; error: string };

interface Stored {
  chart: ChartResult;
  input: BirthInput & { place_display?: string };
}

const PLANET_ROWS: PlanetName[] = [
  "太阳",
  "月亮",
  "火星",
  "水星",
  "木星",
  "金星",
  "土星",
  "Rahu",
  "Ketu",
];

/** 行星名展示用映射:Rahu/Ketu 走中文星命的正统译法,与七曜中文名同为双字。 */
const PLANET_DISPLAY: Record<PlanetName, string> = {
  太阳: "太阳",
  月亮: "月亮",
  火星: "火星",
  水星: "水星",
  木星: "木星",
  金星: "金星",
  土星: "土星",
  Rahu: "罗睺",
  Ketu: "计都",
};

export default function ResultPage() {
  const [data, setData] = useState<Stored | null>(null);
  const [hydrated, setHydrated] = useState(false);
  const [interpret, setInterpret] = useState<InterpretState>({ status: "idle" });

  useEffect(() => {
    try {
      const raw = sessionStorage.getItem(STORAGE_KEY);
      if (raw) setData(JSON.parse(raw));
    } catch {
      // ignore
    }
    setHydrated(true);
  }, []);

  // 自动拉取解读(流式):字一边到一边渲染。同会话内同盘缓存最终文本,刷新不重烧 token。
  useEffect(() => {
    if (!data) return;
    const cacheKey = `${INTERPRET_KEY}:${data.chart.meta.birth_utc}:${data.chart.meta.lat}:${data.chart.meta.lon}`;
    const cached = sessionStorage.getItem(cacheKey);
    if (cached) {
      setInterpret({ status: "ok", text: cached });
      return;
    }
    setInterpret({ status: "streaming", text: "" });
    const todayIso = new Date().toISOString().slice(0, 10);
    const controller = new AbortController();
    let cancelled = false;

    (async () => {
      try {
        const resp = await fetch("/api/interpret", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ chart: data.chart, today: todayIso }),
          signal: controller.signal,
        });
        if (!resp.ok || !resp.body) {
          const detail = await resp.text();
          throw new Error(`${resp.status}: ${detail || "no body"}`);
        }
        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let acc = "";
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          if (cancelled) return;
          acc += decoder.decode(value, { stream: true });
          setInterpret({ status: "streaming", text: acc });
        }
        // 收尾:有可能 decoder 里还有 buffered bytes
        acc += decoder.decode();
        if (cancelled) return;
        // 后端报错会以 "[解读生成失败:...]" 拼在流尾;识别一下转 error 状态
        if (acc.includes("[解读生成失败")) {
          setInterpret({ status: "error", error: acc });
          return;
        }
        sessionStorage.setItem(cacheKey, acc);
        setInterpret({ status: "ok", text: acc });
      } catch (e) {
        if ((e as Error).name === "AbortError" || cancelled) return;
        setInterpret({ status: "error", error: (e as Error).message });
      }
    })();

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [data]);

  if (!hydrated) return null;

  if (!data) {
    return (
      <main className="flex flex-1 items-center justify-center px-6 py-16">
        <div className="text-center">
          <p className="text-muted-strong">还没有排盘记录。</p>
          <Link
            href="/chart"
            className="mt-4 inline-block text-accent hover:underline"
          >
            去填出生信息 →
          </Link>
        </div>
      </main>
    );
  }

  const { chart, input } = data;
  const moon = chart.planets["月亮"];
  const houses = chartToHouses(chart);

  return (
    <main className="flex flex-1 flex-col">
      <header className="px-6 pt-8 sm:px-10">
        <Link
          href="/chart"
          className="text-sm tracking-widest text-muted uppercase hover:text-foreground"
        >
          ← 重新排盘
        </Link>
      </header>

      <section className="flex-1 px-6 py-8 sm:px-10 sm:py-12">
        <div className="mx-auto w-full max-w-2xl space-y-12">
          {/* —————— 标题 / 出生信息 —————— */}
          <header>
            <h1 className="text-2xl font-medium tracking-tight sm:text-3xl">
              {input.name ? `${input.name} 的本命盘` : "你的本命盘"}
            </h1>
            <p className="mt-2 text-sm text-muted">
              {formatBirthLocal(input.birth_local)} ·{" "}
              {input.place_display || `${input.lat}, ${input.lon}`}
            </p>
          </header>

          {/* —————— Hero 卡片 —————— */}
          <section className="space-y-3">
            <HeroCard
              kicker="上升"
              title={`${chart.ascendant.sign}座`}
              lines={[
                `出生星宿 ${chart.ascendant.nakshatra} · pada ${chart.ascendant.pada}`,
                "上升决定你给人的第一印象,和这一生的整体走向。",
              ]}
            />
            <HeroCard
              kicker="月亮"
              title={`${moon.sign}座`}
              accent={moon.dignity === "debilitated" ? "落陷" : moon.dignity === "exalted" ? "入旺" : undefined}
              accentTone={moon.dignity === "exalted" ? "warm" : "cool"}
              lines={[
                `出生星宿 ${moon.nakshatra} · pada ${moon.pada}`,
                "在吠陀占星里,月亮代表你的内心、情绪、思考方式,比太阳更核心。",
              ]}
            />
            <HeroCard
              kicker={`当前大运 · ${chart.current_dasha.maha_period}`}
              title={`${chart.current_dasha.mahadasha} 大运`}
              lines={[
                `小运:${chart.current_dasha.antardasha} 至 ${chart.current_dasha.antar_end}`,
                "Dasha 是吠陀占星把人生切成的一段段能量周期,你现在处在这一段。",
              ]}
            />
          </section>

          {/* —————— AI 解读 —————— */}
          <section>
            <h2 className="mb-3 text-sm font-medium tracking-widest text-muted uppercase">
              AI 解读
            </h2>
            <InterpretationBlock state={interpret} chart={data.chart} />
          </section>

          {/* —————— 吠陀星盘(次要位置) —————— */}
          <section>
            <h2 className="mb-1 text-sm font-medium tracking-widest text-muted uppercase">
              你的吠陀星盘
            </h2>
            <p className="mb-4 text-xs text-muted">
              这是吠陀占星师看的盘式图;读不懂没关系,主要信息已经在上面了。
            </p>
            <div className="flex justify-center rounded-md border border-border bg-card px-4 py-6">
              <NorthIndianChart houses={houses} size={300} />
            </div>
            <p className="mt-3 text-xs text-muted">
              图例:七曜(日月火水木金土)加罗睺、计都。
              <span className="ml-1 text-accent">↑ 入旺</span>
              <span className="ml-2" style={{ color: "var(--debility)" }}>
                ↓ 落陷
              </span>
              <span className="ml-2">ʳ 逆行</span>
            </p>
          </section>

          {/* —————— 完整行星表 —————— */}
          <section>
            <h2 className="mb-3 text-sm font-medium tracking-widest text-muted uppercase">
              九大行星
            </h2>
            <div className="overflow-hidden rounded-md border border-border bg-card">
              <table className="w-full text-sm">
                <thead className="bg-stone-50 text-xs text-muted">
                  <tr>
                    <th className="px-3 py-2 text-left">行星</th>
                    <th className="px-3 py-2 text-left">星座</th>
                    <th className="px-3 py-2 text-left">宫</th>
                    <th className="px-3 py-2 text-left">星宿</th>
                    <th className="px-3 py-2 text-left">状态</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {PLANET_ROWS.map((name) => {
                    const p = chart.planets[name];
                    const statusColor =
                      p.dignity === "debilitated"
                        ? "text-[color:var(--debility)]"
                        : p.dignity === "exalted"
                          ? "text-accent"
                          : "text-muted";
                    return (
                      <tr key={name}>
                        <td className="px-3 py-2 font-medium">
                          {PLANET_DISPLAY[name]}
                        </td>
                        <td className="px-3 py-2">{p.sign}</td>
                        <td className="px-3 py-2">{p.house}</td>
                        <td className="px-3 py-2 text-muted-strong">
                          {p.nakshatra}
                        </td>
                        <td className={`px-3 py-2 ${statusColor}`}>
                          {p.note || ""}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>

          {/* —————— 大运时间线(只展示 25 年以内结束的) —————— */}
          {(() => {
            const horizonYear = new Date().getFullYear() + 25;
            const visible = chart.dasha_timeline.filter(
              (seg) => seg.end_year <= horizonYear,
            );
            const hiddenCount =
              chart.dasha_timeline.length - visible.length;
            return (
              <section>
                <h2 className="mb-3 text-sm font-medium tracking-widest text-muted uppercase">
                  大运时间线
                </h2>
                <ol className="overflow-hidden rounded-md border border-border bg-card">
                  {visible.map((seg, i) => {
                    const isCurrent =
                      seg.planet === chart.current_dasha.mahadasha &&
                      seg.start === chart.current_dasha.maha_start;
                    return (
                      <li
                        key={i}
                        className={`flex justify-between gap-4 px-4 py-2.5 text-sm ${
                          i > 0 ? "border-t border-border" : ""
                        } ${
                          isCurrent
                            ? "bg-accent-soft font-medium text-foreground"
                            : "text-muted-strong"
                        }`}
                      >
                        <span>{PLANET_DISPLAY[seg.planet]}</span>
                        <span className="text-muted">
                          {seg.start_year} → {seg.end_year}
                        </span>
                      </li>
                    );
                  })}
                </ol>
                {hiddenCount > 0 && (
                  <p className="mt-2 text-xs text-muted">
                    更远的 {hiddenCount} 段大运暂不显示
                  </p>
                )}
              </section>
            );
          })()}

          {/* —————— 支持(随喜结缘) —————— */}
          <section className="flex justify-center">
            <div className="inline-flex flex-col items-center rounded-2xl border border-border bg-card px-6 py-7 shadow-[0_1px_2px_rgba(0,0,0,0.02)]">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src="/wechat-pay.jpg"
                alt="微信收款码"
                loading="lazy"
                className="w-44 sm:w-52 rounded-lg"
              />
              <p className="mt-4 text-base text-foreground">
                手搓不易 随喜结缘 <span className="text-accent">❤︎</span>
              </p>
              <p className="mt-1 text-xs text-muted">
                愿这份解读对你有所启发
              </p>
            </div>
          </section>

          <footer className="pt-8 text-center text-xs text-muted">
            仅供自我探索,非命运论断
          </footer>
        </div>
      </section>
    </main>
  );
}

function InterpretationBlock({
  state,
  chart,
}: {
  state: InterpretState;
  chart: ChartResult;
}) {
  if (state.status === "idle") return null;

  if (state.status === "error") {
    const friendly = humanizeInterpretError(state.error);
    return (
      <div className="rounded-md border border-red-300 bg-red-50 px-5 py-4 text-sm">
        <p className="font-medium text-red-700">解读生成失败</p>
        <p className="mt-1 text-red-700/90 whitespace-pre-wrap">{friendly}</p>
        <RetryButton chart={chart} />
      </div>
    );
  }

  const isStreaming = state.status === "streaming";
  // 兜底:模型偶尔在段头/小标题/bullets 间多一个空行;统一收紧
  const text = state.text
    // 1. ①②③ 等大段段头 → 正文紧贴
    .replace(/^([①②③④⑤⑥⑦⑧⑨⑩][^\n]+)\n+/gm, "$1\n")
    // 2. 任何 bullet (· ) 前面的空行都收紧成单换行
    //    覆盖:小标题→第一条 / 同组内两条之间 / 模型出现的任何 ·-前空行
    .replace(/\n\n+(?=·\s)/g, "\n");

  // 流式还没收到第一个 token:显示脉动占位
  if (isStreaming && text.length === 0) {
    return (
      <div className="rounded-md border border-border bg-card px-5 py-8">
        <div className="flex items-center gap-3 text-sm text-muted-strong">
          <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-accent" />
          正在按你的本命盘生成中文解读…
        </div>
        <p className="mt-3 text-xs text-muted">
          文字会一边生成一边出现,十段全部出齐通常 60-90 秒。
        </p>
      </div>
    );
  }

  // 流式或终态:都用 article 渲染累积文本;流式时在末尾画一个闪动光标
  return (
    <article className="rounded-md border border-border bg-card px-5 py-6 text-[15px] leading-relaxed text-foreground whitespace-pre-wrap">
      {text}
      {isStreaming && (
        <span
          className="ml-0.5 inline-block h-[1em] w-[2px] -mb-[2px] animate-pulse bg-accent align-text-bottom"
          aria-hidden
        />
      )}
    </article>
  );
}

function humanizeInterpretError(raw: string): string {
  if (raw.includes("503") && raw.includes("ANTHROPIC_API_KEY")) {
    return "后端还没配置 Anthropic API key。在 vedic-api/.env 里填 ANTHROPIC_API_KEY=sk-ant-... 后重启 FastAPI。";
  }
  if (raw.includes("429")) {
    return "Anthropic API 限速了,稍后再试。";
  }
  if (raw.includes("auth")) {
    return "API key 无效,请到 console.anthropic.com 检查。";
  }
  return raw;
}

function RetryButton({ chart }: { chart: ChartResult }) {
  void chart;
  return (
    <button
      type="button"
      onClick={() => window.location.reload()}
      className="mt-3 text-xs text-red-700 underline"
    >
      重试
    </button>
  );
}

/** "1997-08-13T09:55:00" → "1997/08/13 09:55"(中式日期顺序) */
function formatBirthLocal(iso: string): string {
  const m = iso.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/);
  if (!m) return iso;
  const [, y, mo, d, hh, mm] = m;
  return `${y}/${mo}/${d} ${hh}:${mm}`;
}

function HeroCard({
  kicker,
  title,
  accent,
  accentTone,
  lines,
}: {
  kicker: string;
  title: string;
  accent?: string;
  accentTone?: "warm" | "cool";
  lines: string[];
}) {
  return (
    <div className="rounded-md border border-border bg-card px-5 py-4">
      <div className="text-xs tracking-widest text-muted uppercase">
        {kicker}
      </div>
      <div className="mt-1 flex items-baseline gap-3">
        <div className="text-2xl font-medium tracking-tight">{title}</div>
        {accent && (
          <div
            className={
              accentTone === "warm"
                ? "text-sm text-accent"
                : "text-sm text-[color:var(--debility)]"
            }
          >
            {accent}
          </div>
        )}
      </div>
      <div className="mt-2 space-y-1 text-sm text-muted-strong">
        {lines.map((line, i) => (
          <p key={i} className={i === lines.length - 1 ? "text-muted" : ""}>
            {line}
          </p>
        ))}
      </div>
    </div>
  );
}
