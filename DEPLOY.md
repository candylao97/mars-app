# 部署指南

这个项目是两个独立服务,分开部署 + 用环境变量把它们连起来。

```
┌──────────────┐   FASTAPI_URL   ┌──────────────┐
│  vedic-app   │ ──────────────▶ │  vedic-api   │
│  (Next.js)   │                 │  (Python)    │
│  公开域名     │                 │  内网/直连     │
└──────────────┘                 └──────────────┘
                                         │
                                         ▼ ANTHROPIC_API_KEY
                                  Anthropic API
```

用户只接触 `vedic-app` 域名;`vedic-api` 不需要公开域名,但需要 `vedic-app` 能反向访问到它。

---

## 1. 部署 `vedic-api`(Python FastAPI)

**推荐平台**:Railway / Render / Fly.io。三家都支持 Dockerfile-based 部署。**首推 Railway**,$5/月无冷启动,适合长跑的 streaming 接口。

### 必需的环境变量

| 变量 | 值 | 说明 |
|---|---|---|
| `ANTHROPIC_API_KEY` | `sk-ant-...` | 你在 console.anthropic.com 拿的 key,**仅在此处设置**,绝不下放前端 |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-6`(可省) | 默认就是这个 |
| `PORT` | 由平台自动注入 | 不用手动设 |

### Railway 步骤

1. 装 Railway CLI:`brew install railway` 然后 `railway login`
2. 进 `vedic-api` 目录:`cd vedic-api`
3. `railway init` → 选 "Empty Project"
4. `railway up` → 上传代码,Railway 自动用 Dockerfile 构建
5. 在 Railway 控制台 → Variables → 加 `ANTHROPIC_API_KEY`
6. 部署完成后,Settings → Networking → "Generate Domain" 拿到 URL,比如 `https://vedic-api-production.up.railway.app`
7. 测一下:`curl https://你的域名/healthz` 应返回 `{"status":"ok"}`

### Render 步骤(替代)

1. console.render.com → New → Web Service
2. 连 GitHub repo,选 `vedic-api` 子目录,Runtime: Docker
3. Environment Variables 加 `ANTHROPIC_API_KEY`
4. Plan 选 Standard($7/月,无冷启动)。Free 也行但解读首次调用会冷启 10-30 秒
5. 部署完拿到 URL

### 本地用 Docker 验证(可选)

```bash
cd vedic-api
docker build -t vedic-api .
docker run -p 8000:8000 -e ANTHROPIC_API_KEY=sk-ant-... vedic-api
curl http://localhost:8000/healthz
```

---

## 2. 部署 `vedic-app`(Next.js)

**推荐平台**:Vercel(Next.js 官方,一键部署,免费额度足够 MVP)。

### 必需的环境变量

| 变量 | 值 | 说明 |
|---|---|---|
| `FASTAPI_URL` | `https://vedic-api-production.up.railway.app`(填上一步拿到的 URL) | 不带尾斜杠 |

### Vercel 步骤

1. vercel.com → Import Project → 连 GitHub repo,选 `vedic-app` 作为 Root Directory
2. Framework Preset 应自动识别为 Next.js;构建命令、输出目录都用默认
3. Environment Variables → 加 `FASTAPI_URL`
4. Deploy → 拿到 `https://你的项目.vercel.app`
5. 自定义域名可在 Settings → Domains 里挂

### 本地验证 production build(可选)

```bash
cd vedic-app
npm run build
FASTAPI_URL=http://localhost:8000 npm run start
# 访问 http://localhost:3000
```

---

## 3. 上线后必做的健康检查

```bash
# FastAPI 通
curl https://你的-vedic-api.../healthz

# 真实排盘可走通(回归用例,Candy 的盘)
curl -s -X POST https://你的-vedic-app.../api/chart \
  -H 'Content-Type: application/json' \
  -d '{"birth_local":"1997-08-13T09:55:00","tz":"Asia/Shanghai","lat":22.5431,"lon":114.0579}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['ascendant']['sign'], d['planets']['月亮']['nakshatra'], d['current_dasha']['mahadasha'])"
# 期望输出: 处女 Anuradha 金星
```

如果对上,整条链路就活了。

---

## 4. 成本估算

- **Vercel**:个人项目免费(100GB 流量/月、Serverless 函数足够 MVP 用)
- **Railway**:$5/月起(单服务)
- **Anthropic**:claude-sonnet-4-6,带 prompt cache,单次解读 ~$0.05。100 个用户/月 ≈ $5
- **Nominatim**:免费,但限速 1 req/s,我们的 debounce 已经在限内

预计 MVP 月支出 **$10-15**。

---

## 5. 部署后该看哪些日志

- **FastAPI**(Railway/Render dashboard):每次 /interpret 完成会落一行:
  ```
  interpret done | input=652 output=2940 cache_create=1878 cache_read=0
  ```
  追这行可监控调用量 + 缓存命中率。
- **Next.js**(Vercel dashboard):Functions 日志看 /api/* 错误。
- 钱:console.anthropic.com → Usage tab 看真实账单。

---

## 6. 不要忘记

- `.env`、`.env.local`、`vedic-api/.env` 都已在 `.gitignore` 里,**别 commit ANTHROPIC_API_KEY**
- 部署平台的 env vars 是唯一存 key 的地方
- 上线前在 prod 域名再跑一次 §3 那个 curl,确认数据通路
