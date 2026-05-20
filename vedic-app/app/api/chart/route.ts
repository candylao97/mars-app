import { proxyJson } from "@/lib/api";

export async function POST(request: Request) {
  const body = await request.json();
  return proxyJson("/chart", body, { timeoutMs: 20_000 });
}
