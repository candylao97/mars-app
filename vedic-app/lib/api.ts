/**
 * 服务器端调用 FastAPI 的小工具。
 * 仅供 Route Handlers 使用,绝不能被 client component 直接 import
 * (process.env.FASTAPI_URL 是私有环境变量,不会进客户端 bundle)。
 */

export function getFastApiBase(): string {
  const url = process.env.FASTAPI_URL;
  if (!url) {
    throw new Error("FASTAPI_URL is not set (check .env.local)");
  }
  return url.replace(/\/+$/, "");
}

/** 把 body JSON 透传到 FastAPI 对应端点,把响应原样返回前端。 */
export async function proxyJson(
  path: string,
  body: unknown,
  init?: { timeoutMs?: number },
): Promise<Response> {
  const base = getFastApiBase();
  const controller = new AbortController();
  const timer = setTimeout(
    () => controller.abort(),
    init?.timeoutMs ?? 30_000,
  );
  try {
    const upstream = await fetch(`${base}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: controller.signal,
      cache: "no-store",
    });
    const text = await upstream.text();
    return new Response(text, {
      status: upstream.status,
      headers: { "Content-Type": "application/json" },
    });
  } catch (e) {
    const detail = e instanceof Error ? e.message : String(e);
    return Response.json(
      { error: "upstream_unavailable", detail },
      { status: 502 },
    );
  } finally {
    clearTimeout(timer);
  }
}
