import { proxyJson } from "@/lib/api";

export async function POST(request: Request) {
  const body = await request.json();
  return proxyJson("/geocode", body, { timeoutMs: 15_000 });
}
