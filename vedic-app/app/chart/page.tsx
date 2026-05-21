"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import type {
  BirthInput,
  ChartResult,
  GeocodeHit,
  GeocodeResponse,
} from "@/lib/contract";

const STORAGE_KEY = "vedic.lastChart";

export default function ChartFormPage() {
  const router = useRouter();

  const [name, setName] = useState("");
  const [birthYear, setBirthYear] = useState("");
  const [birthMonth, setBirthMonth] = useState("");
  const [birthDay, setBirthDay] = useState("");
  const [birthHour, setBirthHour] = useState(""); // 0-23
  const [birthMinute, setBirthMinute] = useState(""); // 0-59
  const [timeUncertain, setTimeUncertain] = useState(false);

  const [placeQuery, setPlaceQuery] = useState("");
  const [hits, setHits] = useState<GeocodeHit[]>([]);
  const [selectedPlace, setSelectedPlace] = useState<GeocodeHit | null>(null);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const abortRef = useRef<AbortController | null>(null);

  // 防抖搜索
  useEffect(() => {
    const q = placeQuery.trim();
    if (!q || selectedPlace) {
      setHits([]);
      setSearching(false);
      return;
    }
    setSearching(true);
    setSearchError(null);
    const handle = setTimeout(async () => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      try {
        const resp = await fetch("/api/geocode", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ q }),
          signal: controller.signal,
        });
        if (!resp.ok) {
          const detail = await resp.text();
          throw new Error(`geocode 失败 (${resp.status}): ${detail}`);
        }
        const data: GeocodeResponse = await resp.json();
        setHits(data.results);
      } catch (e) {
        if ((e as Error).name === "AbortError") return;
        setHits([]);
        setSearchError((e as Error).message);
      } finally {
        setSearching(false);
      }
    }, 350);
    return () => clearTimeout(handle);
  }, [placeQuery, selectedPlace]);

  const birthTime = useMemo(() => {
    const h = Number(birthHour);
    const m = Number(birthMinute);
    if (birthHour === "" || birthMinute === "") return "";
    if (!Number.isFinite(h) || !Number.isFinite(m)) return "";
    if (h < 0 || h > 23) return "";
    if (m < 0 || m > 59) return "";
    return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
  }, [birthHour, birthMinute]);

  const birthDate = useMemo(() => {
    const y = Number(birthYear);
    const m = Number(birthMonth);
    const d = Number(birthDay);
    if (!y || !m || !d) return "";
    if (y < 1900 || y > 2100) return "";
    if (m < 1 || m > 12) return "";
    if (d < 1 || d > 31) return "";
    const iso = `${String(y).padStart(4, "0")}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
    // 校验组合有效(过滤 2 月 30 这种)
    const probe = new Date(`${iso}T00:00:00Z`);
    if (
      probe.getUTCFullYear() !== y ||
      probe.getUTCMonth() + 1 !== m ||
      probe.getUTCDate() !== d
    )
      return "";
    return iso;
  }, [birthYear, birthMonth, birthDay]);

  const canSubmit = useMemo(() => {
    return Boolean(
      birthDate && birthTime && selectedPlace && !submitting,
    );
  }, [birthDate, birthTime, selectedPlace, submitting]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedPlace || !birthDate || !birthTime) return;

    setSubmitting(true);
    setSubmitError(null);

    const payload: BirthInput = {
      birth_local: `${birthDate}T${birthTime}:00`,
      tz: selectedPlace.tz,
      lat: selectedPlace.lat,
      lon: selectedPlace.lon,
      name: name.trim() || undefined,
    };

    try {
      const resp = await fetch("/api/chart", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!resp.ok) {
        const detail = await resp.text();
        throw new Error(`排盘失败 (${resp.status}): ${detail}`);
      }
      const chart: ChartResult = await resp.json();
      sessionStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          chart,
          input: { ...payload, place_display: selectedPlace.display_name },
        }),
      );
      router.push("/chart/result");
    } catch (e) {
      setSubmitError((e as Error).message);
      setSubmitting(false);
    }
  }

  return (
    <main className="flex flex-1 flex-col">
      <header className="px-6 pt-8 sm:px-10">
        <Link
          href="/"
          className="text-sm tracking-widest text-muted uppercase hover:text-foreground"
        >
          ← Jyotish · 吠陀占星
        </Link>
      </header>

      <section className="flex-1 px-6 py-10 sm:px-10 sm:py-16">
        <div className="mx-auto w-full max-w-xl">
          <h1 className="text-2xl font-medium tracking-tight sm:text-3xl">
            告诉我你出生那一刻
          </h1>
          <p className="mt-3 text-sm text-muted-strong leading-relaxed">
            出生时间影响上升与当前大运;尽量准。
            如果只记得"早上九点多",填 9 时 30 分并在心里标注待校正。
          </p>

          <form onSubmit={handleSubmit} className="mt-10 space-y-7">
            <Field label="姓名(可选)">
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="只用于解读里的称呼"
                className={inputClass}
                autoComplete="off"
              />
            </Field>

            <Field label="出生日期" required>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  inputMode="numeric"
                  pattern="[0-9]*"
                  value={birthYear}
                  onChange={(e) =>
                    setBirthYear(e.target.value.replace(/\D/g, "").slice(0, 4))
                  }
                  placeholder="如 1990"
                  className={`${dateInputClass} flex-[1.5]`}
                  required
                />
                <span className="text-sm text-muted">年</span>
                <input
                  type="text"
                  inputMode="numeric"
                  pattern="[0-9]*"
                  value={birthMonth}
                  onChange={(e) =>
                    setBirthMonth(e.target.value.replace(/\D/g, "").slice(0, 2))
                  }
                  placeholder="如 5"
                  className={`${dateInputClass} flex-1`}
                  required
                />
                <span className="text-sm text-muted">月</span>
                <input
                  type="text"
                  inputMode="numeric"
                  pattern="[0-9]*"
                  value={birthDay}
                  onChange={(e) =>
                    setBirthDay(e.target.value.replace(/\D/g, "").slice(0, 2))
                  }
                  placeholder="如 15"
                  className={`${dateInputClass} flex-1`}
                  required
                />
                <span className="text-sm text-muted">日</span>
              </div>
            </Field>

            <div>
              <Field label="出生时间(24 小时制)" required>
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    inputMode="numeric"
                    pattern="[0-9]*"
                    value={birthHour}
                    onChange={(e) =>
                      setBirthHour(e.target.value.replace(/\D/g, "").slice(0, 2))
                    }
                    placeholder="如 9"
                    className={`${dateInputClass} flex-1`}
                    required
                  />
                  <span className="text-sm text-muted">时</span>
                  <input
                    type="text"
                    inputMode="numeric"
                    pattern="[0-9]*"
                    value={birthMinute}
                    onChange={(e) =>
                      setBirthMinute(e.target.value.replace(/\D/g, "").slice(0, 2))
                    }
                    placeholder="如 30"
                    className={`${dateInputClass} flex-1`}
                    required
                  />
                  <span className="text-sm text-muted">分</span>
                  {/* 用空 div 占位让两框宽度跟日期那行三框对齐感更好 */}
                  <div aria-hidden className="flex-1" />
                </div>
              </Field>
              <button
                type="button"
                onClick={() => setTimeUncertain((v) => !v)}
                className="mt-2 text-xs text-accent hover:underline"
              >
                {timeUncertain ? "收起" : "出生时间不确定?"}
              </button>
              {timeUncertain && (
                <p className="mt-2 rounded-md bg-accent-soft px-3 py-2 text-xs leading-relaxed text-muted-strong">
                  不确定时间可以先选个近似值排出来看。出生时间每偏 4
                  分钟,上升经度约移 1°,可能会影响上升星座和宫位边界。
                  建议日后翻一翻户口本、出生证、或问问妈妈,精确到分钟最好。
                </p>
              )}
            </div>

            <Field label="出生城市" required>
              {selectedPlace ? (
                <SelectedPlaceCard
                  place={selectedPlace}
                  onClear={() => {
                    setSelectedPlace(null);
                    setPlaceQuery("");
                  }}
                />
              ) : (
                <>
                  <input
                    type="text"
                    value={placeQuery}
                    onChange={(e) => setPlaceQuery(e.target.value)}
                    placeholder="如:深圳、墨尔本、香港、纽约"
                    className={inputClass}
                    autoComplete="off"
                  />
                  {searchError && (
                    <p className="mt-2 text-xs text-red-600">{searchError}</p>
                  )}
                  {(searching || hits.length > 0) && (
                    <ul className="mt-2 divide-y divide-border overflow-hidden rounded-md border border-border bg-card">
                      {searching && (
                        <li className="flex items-center gap-2 px-3 py-3 text-sm text-muted">
                          <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />
                          搜索中…
                        </li>
                      )}
                      {hits.map((hit, i) => (
                        <li key={`${hit.lat}-${hit.lon}-${i}`}>
                          <button
                            type="button"
                            // iOS Safari 修:阻止 mousedown 默认行为(包括把焦点从输入框抢走),
                            // 这样 tap 期间页面不重排,click 能稳定落在 button 上。
                            // 不要加 onTouchStart preventDefault,会把 iOS 后续合成的 click 事件也屏蔽掉。
                            onMouseDown={(e) => e.preventDefault()}
                            onClick={() => {
                              setSelectedPlace(hit);
                              setHits([]);
                            }}
                            className="w-full px-3 py-3 text-left transition-colors hover:bg-accent-soft"
                          >
                            <div className="text-sm text-foreground">
                              {hit.display_name}
                            </div>
                            <div className="mt-0.5 text-xs text-muted">
                              {hit.lat.toFixed(4)}°, {hit.lon.toFixed(4)}° ·{" "}
                              {hit.tz}
                            </div>
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </>
              )}
            </Field>

            {submitError && (
              <p className="text-sm text-red-600">{submitError}</p>
            )}

            <button
              type="submit"
              disabled={!canSubmit}
              className="w-full rounded-full bg-accent px-8 py-3.5 text-base font-medium text-white shadow-sm transition-colors hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-40"
            >
              {submitting ? "排盘中..." : "排盘 →"}
            </button>
            {!canSubmit && !submitting && (
              <p className="text-center text-xs text-muted">
                {missingFieldsHint(birthDate, birthTime, selectedPlace)}
              </p>
            )}
          </form>
        </div>
      </section>
    </main>
  );
}

const inputClass =
  "w-full rounded-md border border-border bg-card px-3 py-3 text-base text-foreground placeholder:text-stone-400 focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20";

// 日期三个数字框:w-full + min-w-0 保证在 flex 容器里平均分配;占位用更浅的灰,跟真值一眼区分
const dateInputClass =
  "w-full min-w-0 rounded-md border border-border bg-card px-2 py-3 text-base text-foreground text-center placeholder:text-stone-400 placeholder:text-sm focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20";

function missingFieldsHint(
  birthDate: string,
  birthTime: string,
  selectedPlace: GeocodeHit | null,
): string {
  const missing: string[] = [];
  if (!birthDate) missing.push("出生日期");
  if (!birthTime) missing.push("出生时间");
  if (!selectedPlace) missing.push("出生城市");
  if (missing.length === 0) return "";
  return `还需要填:${missing.join("、")}`;
}

function Field({
  label,
  required,
  children,
}: {
  label: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-2 block text-sm font-medium text-foreground">
        {label}
        {required && <span className="ml-1 text-accent">*</span>}
      </span>
      {children}
    </label>
  );
}

function SelectedPlaceCard({
  place,
  onClear,
}: {
  place: GeocodeHit;
  onClear: () => void;
}) {
  return (
    <div className="flex items-start justify-between gap-3 rounded-md border border-accent/40 bg-accent-soft px-3 py-3">
      <div className="min-w-0 flex-1">
        <div className="text-sm text-foreground break-words">
          {place.display_name}
        </div>
        <div className="mt-1 text-xs text-muted-strong">
          {place.lat.toFixed(4)}°, {place.lon.toFixed(4)}° · {place.tz}
        </div>
      </div>
      <button
        type="button"
        onClick={onClear}
        className="shrink-0 text-xs text-muted-strong hover:text-foreground"
      >
        改
      </button>
    </div>
  );
}
