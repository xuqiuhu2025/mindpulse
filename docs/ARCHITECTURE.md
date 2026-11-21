# 架构设计（ARCHITECTURE）

> 版本：v0.1.0 ｜ 2026-11-21

## 总览

```mermaid
flowchart LR
    subgraph iOS["iOS 客户端 (SwiftUI)"]
        UI[聊天 / 心情 / 健康 / 设置]
        SD[(SwiftData 本地库)]
        HK[HealthKit 聚合查询]
        CE[CareEvaluator 本地评估]
    end
    subgraph Backend["FastAPI 后端"]
        API[REST API]
        SG[SafetyGuard 规则分级]
        CS[ChatService]
        PM[PromptService prompts/]
        LP[LLM Provider 抽象层]
        CEng[CareEngine 主动关心]
        CR[CrisisResourceService]
        DB[(SQLite)]
    end
    LLM[LLM 供应商\n(OpenAI 兼容协议)]

    UI --> SD
    HK --> SD
    SD --> CE
    UI -- HTTPS: 聊天/心情/快照/同意/删除 --> API
    API --> SG
    SG -- safe/support --> CS --> PM --> LP --> LLM
    SG -- urgent --> CR
    SG -- urgent -->|固定脚本,不过 LLM| API
    CEng --> DB
    CR --> RES[(crisis_resources.json)]
    LP -- 输出二次筛查 --> SG
```

## 核心设计决策

### 1. SafetyGuard 在聊天流程之前、独立于 LLM

```
用户输入 ──> SafetyGuard.classify()
              ├─ urgent  → 版本化固定脚本（不调 LLM）→ 返回危机资源
              ├─ support → 系统章程 + support 附加说明 → LLM → 输出筛查 → 返回
              └─ safe    → 系统章程 → LLM → 输出筛查 → 返回
```

- urgent 完全绕过 LLM：危机响应是**确定性**的，不可能被模型输出破坏。
- 输出筛查（`screen_output`）兜底拦截方法/剂量类内容。
- 注入输入会被标记并记录（不含原文），章程照常注入 system prompt。

### 2. 本地优先存储

所有用户数据的权威副本在设备上（SwiftData）。服务端存在的意义只有三个：跑 LLM 聊天、服务端侧的主动关心聚合、以及跨设备调试。用户可以随时 `DELETE /api/data/all` 清掉服务端副本而不影响本地。

### 3. LLM Provider 抽象

`LLMProvider` 协议 + 工厂。默认 `offline`（确定性模板，测试与离线开发用），`openai_compatible` 通过环境变量对接任意供应商。换供应商零代码改动。

### 4. 同意是数据的开关

`ConsentService.active_scopes()` 是健康数据的唯一闸门：快照写入、主动关心评估、趋势展示都要先过这一关。撤回即生效。

## 数据模型

| 表 | 关键字段 | 说明 |
| --- | --- | --- |
| `conversations` / `messages` | role, content, safety_level | 聊天记录 |
| `mood_entries` | score(1-10), tags, note | 心情记录 |
| `consent_records` | scope, granted, granted_at, revoked_at | 同意审计链 |
| `health_trend_snapshots` | date, sleep_hours, resting_hr, hrv_sdnn, steps | **按天聚合**，(device_id, date) 唯一 |
| `safety_events` | level, signal_categories, prompt_injection | 无原文的审计 |
| `user_prefs` | care_enabled, care_frequency, country | 轻量偏好 |

## API 一览

| 方法 | 路径 | 鉴权 | 说明 |
| --- | --- | --- | --- |
| POST | `/api/chat` | device-id | 聊天（含 SafetyGuard 分级） |
| POST | `/api/chat/clear` | device-id | 清空当前对话 |
| POST/GET | `/api/mood`、`/api/mood/trends` | device-id | 心情记录与中性趋势 |
| POST/GET | `/api/health/snapshots` | device-id | 聚合快照写入/读取（未授权 403） |
| GET | `/api/health/trends` | device-id | 中性趋势视图 |
| GET | `/api/care/suggestions` | device-id | 主动关心建议（含原因） |
| GET/PUT | `/api/care/settings`、POST `/api/care/dismiss` | device-id | 关闭/减少主动关心 |
| GET/POST | `/api/consent` | device-id | 同意管理 |
| GET | `/api/data/export` | device-id | 导出全部数据 |
| DELETE | `/api/data/all` | device-id | 彻底删除 |
| GET | `/api/crisis/resources?country=CN` | 公开 | 危机资源（未知地区返回 need_country） |

## 关键阈值（care engine）

- 基线：每指标 ≥ 10 天数据（不含最近窗口）
- 最近窗口：3 天均值 vs 基线均值
- 触发：≥ 2 项指标同时偏离（睡眠 ↓20% / 步数 ↓30% / 静息心率 ↑8bpm / HRV ↓25%），或单项偏离在 7 天窗口中持续 ≥ 5 天
- 全部可经环境变量调整；用户可一键关闭
