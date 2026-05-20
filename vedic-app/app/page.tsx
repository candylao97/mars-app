import Link from "next/link";

export default function Home() {
  return (
    <main className="flex flex-1 flex-col">
      <header className="px-6 pt-8 sm:px-10">
        <span className="text-sm tracking-widest text-muted uppercase">
          Jyotish · 吠陀占星
        </span>
      </header>

      <section className="flex flex-1 flex-col justify-center px-6 py-16 sm:px-10 sm:py-24">
        <div className="mx-auto w-full max-w-xl">
          <h1 className="text-3xl font-medium leading-tight tracking-tight sm:text-4xl">
            用吠陀占星<span className="text-accent">看清</span>
            <br />
            你现在所处的人生周期
          </h1>

          <p className="mt-6 text-base leading-relaxed text-muted-strong sm:text-lg">
            输入出生年月日时和地点,系统按 Lahiri 岁差与整宫制排出你的本命盘,
            并由 AI 给出你性格、事业、感情、当前大运的中文解读。
          </p>

          <div className="mt-10">
            <Link
              href="/chart"
              className="inline-flex items-center justify-center rounded-full bg-accent px-8 py-3.5 text-base font-medium text-white shadow-sm transition-colors hover:bg-accent-hover"
            >
              开始排盘
            </Link>
            <p className="mt-3 text-xs text-muted">
              出生时间越精确,上升与大运越准
            </p>
          </div>

          <ul className="mt-16 space-y-5 border-t border-border pt-10 text-sm text-muted-strong">
            <li className="flex gap-3">
              <span className="text-accent">·</span>
              <span>九大行星的星座、宫位、出生星宿,与 AstroSage 核对一致</span>
            </li>
            <li className="flex gap-3">
              <span className="text-accent">·</span>
              <span>Vimshottari 大运时间线,告诉你正在走哪个 20 年</span>
            </li>
            <li className="flex gap-3">
              <span className="text-accent">·</span>
              <span>中文解读不堆术语,十段结构覆盖人生主要维度</span>
            </li>
          </ul>
        </div>
      </section>

      <footer className="px-6 py-8 text-xs text-muted sm:px-10">
        仅供自我探索,非命运论断
      </footer>
    </main>
  );
}
