import { getFastApiBase } from "@/lib/api";

// 流式端点:不能用 proxyJson(那个会 buffer 完才返回)。直接 fetch + 把 body 透传。
// 无客户端 AbortController 超时,依赖 Anthropic 自家流控制。
export async function POST(request: Request) {
  const base = getFastApiBase();
  const bodyText = await request.text();
  let upstream: Response;
  try {
    upstream = await fetch(`${base}/interpret`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: bodyText,
      cache: "no-store",
    });
  } catch (e) {
    const detail = e instanceof Error ? e.message : String(e);
    return Response.json(
      { error: "upstream_unavailable", detail },
      { status: 502 },
    );
  }

  if (!upstream.ok) {
    const errText = await upstream.text();
    return new Response(errText, {
      status: upstream.status,
      headers: { "Content-Type": "application/json" },
    });
  }

  // 关键:body 是 ReadableStream,直接转手出去,Next.js 不要 buffer
  return new Response(upstream.body, {
    status: 200,
    headers: {
      "Content-Type":
        upstream.headers.get("Content-Type") ?? "text/plain; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      "X-Accel-Buffering": "no",
    },
  });
}
