# 部署指南

> 仓库已内置全部部署所需配置（Dockerfile / render.yaml / docker-compose.yml）。
> 演示部署默认使用 **offline provider**（确定性回复模板，不调用任何外部 LLM，不消耗任何密钥）。

## 方式一：Render（网页操作，约 2 分钟，无需 CLI）

1. 打开一键部署入口：
   **https://render.com/deploy?repo=https://github.com/xuqiuhu2025/mindpulse**
2. 用你的 GitHub 账号登录 Render 并授权，页面会自动读取 `render.yaml` 蓝图。
3. 点击 **Apply / Create Resources**，等待构建完成（约 2-5 分钟）。
4. 拿到形如 `https://mindpulse-backend-xxxx.onrender.com` 的地址，即可：

```bash
curl https://<你的地址>/health
curl -X POST https://<你的地址>/api/chat \
  -H "Content-Type: application/json" \
  -H "X-Device-ID: demo-device-0001" \
  -d '{"message":"hello"}'
```

**免费层限制**：磁盘是临时的（服务重启后 SQLite 数据清空）；15 分钟无流量会休眠，首次唤醒有 ~30 秒冷启动。

## 方式二：Railway（CLI 或网页）

```bash
npm i -g @railway/cli
railway login          # 浏览器授权你的 GitHub 账号
railway init
railway up             # 直接使用仓库根的 Dockerfile
railway domain         # 生成公开地址
```

## 方式三：本地 Docker（不依赖任何云平台）

```bash
docker compose up --build
curl http://127.0.0.1:8000/health
```

## 接入真实 LLM（可选）

在平台的环境变量里配置（密钥只放服务端，绝不进客户端或仓库）：

```
MINDPULSE_LLM_PROVIDER=openai_compatible
MINDPULSE_LLM_API_KEY=<你的 key>
MINDPULSE_LLM_BASE_URL=https://api.openai.com/v1   # 或任何兼容供应商
MINDPULSE_LLM_MODEL=gpt-4o-mini
```

## iOS 客户端连接在线 Demo

App 内 **设置 → 关于 → 服务器地址**，填入部署地址（必须 https）即可。
