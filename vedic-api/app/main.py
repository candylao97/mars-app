"""
FastAPI 入口。

端点:
  GET  /healthz       存活探测
  POST /chart         BirthInput → ChartResult
  POST /interpret     InterpretRequest → InterpretResponse  (第 5 步接 Anthropic)

服务设计为内网服务,Next.js Route Handler 做唯一调用方,所以不开放 CORS。
"""

import hashlib
import logging
import os

import anthropic
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

logger = logging.getLogger("vedic-api")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s")

# 启动时加载 .env(ANTHROPIC_API_KEY 等)。只在 FastAPI 进程里读,绝不下放前端。
# override=True:如果父 shell 把 ANTHROPIC_API_KEY 预设成空串(某些 harness 会),
# 也用 .env 里的真值覆盖,避免"key 在 .env 里但被空环境变量挡掉"这种坑。
load_dotenv(override=True)

from .chart_service import build_chart
from . import geocode
from .interpret_service import build_prompts
from .models import (
    BirthInput,
    ChartResult,
    GeocodeHit,
    GeocodeRequest,
    GeocodeResponse,
    InterpretPreviewResponse,
    InterpretRequest,
)

DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")

# 解读缓存:同一张盘 + 同一天的解读,直接命中,不再烧 token。
# in-memory dict,FastAPI 重启会清空,MVP 阶段够用;后面要持久化再上 Redis。
# key = sha256(birth_utc + lat + lon + today)
_INTERPRETATION_CACHE: dict[str, str] = {}
_INTERPRETATION_CACHE_MAX = 5000  # 防止无限增长;到上限简单清空(MVP 策略)


def _cache_key(chart: ChartResult, today: str) -> str:
    h = hashlib.sha256()
    h.update(chart.meta.birth_utc.encode())
    # 经纬度限到 4 位小数,跟 Nominatim 返回精度一致
    h.update(f"{round(chart.meta.lat, 4)},{round(chart.meta.lon, 4)}".encode())
    h.update(today.encode())
    return h.hexdigest()[:16]

app = FastAPI(title="Vedic Chart API", version="0.1.0")


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.post("/chart", response_model=ChartResult)
def compute_chart_endpoint(payload: BirthInput) -> ChartResult:
    try:
        return build_chart(
            birth_local=payload.birth_local,
            tz_name=payload.tz,
            lat=payload.lat,
            lon=payload.lon,
            today=payload.today,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # noqa: BLE001
        return JSONResponse(
            status_code=500,
            content={"error": "chart_failed", "detail": str(e)},
        )


@app.post("/interpret")
def interpret_endpoint(payload: InterpretRequest):
    """
    把 ChartResult + 当前日期喂给 vedic_interpret 定稿 prompt,调 Anthropic 流式接口。
    返回 text/plain 流,客户端按 chunk 增量渲染。usage 在流结束时落日志(不下发)。
    """
    # 维护开关:Railway 上设 MAINTENANCE_MODE=1 即可立刻暂停生成
    # 不调 Anthropic、不烧 token,只返回友好提示
    if os.environ.get("MAINTENANCE_MODE") == "1":
        raise HTTPException(
            status_code=503,
            detail=(
                "MAINTENANCE: 第一阶段反馈收集完毕,我们正在整理大家的意见做改进。"
                "下一版准备好后会通过你之前留的微信通知。感谢你的测试 ❤️"
            ),
        )

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail=(
                "ANTHROPIC_API_KEY not set on the FastAPI service. "
                "在 vedic-api/.env 文件里加 ANTHROPIC_API_KEY=sk-ant-... 后重启服务。"
            ),
        )

    chart = payload.chart
    system_prompt, user_prompt, today = build_prompts(chart, today=payload.today)
    cache_key = _cache_key(chart, today)

    # 缓存命中:直接吐文本,Anthropic 一次都不调
    cached = _INTERPRETATION_CACHE.get(cache_key)
    if cached is not None:
        logger.info("interpret CACHE HIT key=%s len=%d", cache_key, len(cached))

        def yield_cached():
            yield cached.encode("utf-8")

        return StreamingResponse(
            yield_cached(),
            media_type="text/plain; charset=utf-8",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "X-Accel-Buffering": "no",
                "X-Interpret-Cache": "HIT",
            },
        )

    client = anthropic.Anthropic(api_key=api_key)

    def generate():
        chunks: list[str] = []
        completed = False
        try:
            with client.messages.stream(
                model=DEFAULT_MODEL,
                max_tokens=4000,
                # SYSTEM_PROMPT 标 ephemeral 缓存:5 分钟内同 prefix 享受 ~90% input 折扣
                system=[
                    {
                        "type": "text",
                        "text": system_prompt,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[{"role": "user", "content": user_prompt}],
            ) as stream:
                for chunk in stream.text_stream:
                    if chunk:
                        chunks.append(chunk)
                        yield chunk.encode("utf-8")
                # 流结束后,把最终 usage 记到服务端日志(用于成本监控,不下发给前端)
                final = stream.get_final_message()
                u = final.usage
                logger.info(
                    "interpret done | input=%s output=%s cache_create=%s cache_read=%s",
                    u.input_tokens,
                    u.output_tokens,
                    getattr(u, "cache_creation_input_tokens", 0) or 0,
                    getattr(u, "cache_read_input_tokens", 0) or 0,
                )
                completed = True
        except anthropic.AuthenticationError as e:
            logger.error("anthropic auth failed: %s", e)
            yield f"\n\n[解读生成失败:Anthropic auth] {e}".encode("utf-8")
        except anthropic.RateLimitError as e:
            logger.error("anthropic rate-limited: %s", e)
            yield f"\n\n[解读生成失败:被限速] {e}".encode("utf-8")
        except anthropic.APIStatusError as e:
            logger.error("anthropic api error: %s", e)
            yield f"\n\n[解读生成失败:API 错误] {e}".encode("utf-8")
        except Exception as e:  # noqa: BLE001
            logger.exception("interpret stream crashed")
            yield f"\n\n[解读生成失败] {e}".encode("utf-8")
        finally:
            # 只在流完整完成时入缓存;失败的不缓存(避免把"[解读生成失败]"那种留着)
            if completed and chunks:
                full = "".join(chunks)
                if len(_INTERPRETATION_CACHE) >= _INTERPRETATION_CACHE_MAX:
                    # MVP 简单策略:满了清空,等下一轮重新攒
                    _INTERPRETATION_CACHE.clear()
                _INTERPRETATION_CACHE[cache_key] = full
                logger.info(
                    "interpret cached key=%s len=%d (cache size now %d)",
                    cache_key,
                    len(full),
                    len(_INTERPRETATION_CACHE),
                )

    return StreamingResponse(
        generate(),
        media_type="text/plain; charset=utf-8",
        headers={
            # 关键:让中间任何代理(Nginx / Next.js)都不要缓冲
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/interpret/preview", response_model=InterpretPreviewResponse)
def interpret_preview_endpoint(payload: InterpretRequest) -> InterpretPreviewResponse:
    """干跑:把会喂给模型的 prompt 原样吐出,绝不调 Anthropic。
    用来人眼核对真实 nakshatra / dasha 时间线是否进入 prompt。"""
    chart = payload.chart
    moon = chart.planets.get("月亮")
    if moon is None:
        raise HTTPException(status_code=400, detail="missing 月亮 in chart")
    system_prompt, user_prompt, today = build_prompts(chart, today=payload.today)
    return InterpretPreviewResponse(
        today=today,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        moon_sign=moon.sign,
        moon_nakshatra=moon.nakshatra,
        current_mahadasha=chart.current_dasha.mahadasha,
        current_maha_period=chart.current_dasha.maha_period,
        dasha_segment_count=len(chart.dasha_timeline),
    )


@app.post("/geocode", response_model=GeocodeResponse)
async def geocode_endpoint(payload: GeocodeRequest) -> GeocodeResponse:
    try:
        hits = await geocode.search(payload.q, limit=payload.limit)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"geocode upstream failed: {e}")
    return GeocodeResponse(
        results=[GeocodeHit(**h.to_dict()) for h in hits]
    )
