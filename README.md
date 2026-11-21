# MindPulse

> 温和、简单、可信赖的情绪支持原型。

MindPulse 是一个以**用户明确同意**为前提的情绪支持应用：日常聊天 + 你主动填写的心情记录 +（可选的、经你授权的）健康趋势数据，为你提供温和的情绪陪伴，并在危机时刻指向真实世界的帮助。

**它不是医疗产品。** MindPulse 不提供医学诊断、治疗或紧急服务，不能替代医生、心理咨询师或急救系统。如果你正处于危机之中，请立即联系当地急救服务或前往最近的急诊室。

- 🌍 全球求助目录：[findahelpline.com](https://findahelpline.com) / [IASP 危机中心目录](https://www.iasp.info/resources/Crisis_Centres/)

---

## 产品边界（写进代码与测试的承诺）

1. **不暗中监测用户**——健康数据必须由你主动点击授权才开始读取。
2. **不得在未授权时读取 HealthKit**——撤回授权后立即停止读取与上传（有自动化测试）。
3. **不诊断抑郁症、焦虑症或任何心理疾病**——趋势文案与所有输出禁止出现诊断性表述。
4. **不冒充医疗身份**——应用与 Prompt 均声明"情绪支持伙伴，不是医生"。
5. **单一心率/HRV/睡眠/步数变化不构成任何推断**——主动关心需要"多项指标同时变化"或"变化持续一段时间"且基线充足才会触发。
6. **硬件数据只是自愿分享的趋势参考**——默认只传输/保存按天聚合值，逐分钟原始数据不出设备。
7. **你随时可以关闭、删除**——关闭数据读取、清空对话、导出、彻底删除，全部有界面入口和 API。
8. **危机场景优先**——识别到自伤/他伤/即时危险表达时，停止普通聊天，先指向急救、危机热线和可信任的人。
9. **危机提示明确说明**：如果存在立即危险，请联系当地急救服务或前往最近的急诊室。
10. **不硬编码可能失效的号码**——危机资源带来源与核对日期，未知地区先询问你的国家/地区，国际目录永远可用。

---

## 功能总览

| 功能 | 说明 |
| --- | --- |
| 💬 聊天 | SwiftUI 界面，温暖低压力设计；开场白简单自然；三个对话入口（"我今天压力很大 / 我想整理一下思绪 / 我只是想找个人聊聊"）；支持清空当前对话 |
| 🧭 心情记录 | 1-10 分 + 可选标签（压力/睡眠/工作/人际关系等）；最近 7 天 / 30 天趋势；数据不足时明确说明，绝不编结论；只使用"心情记录趋势"等中性命名 |
| ❤️ HealthKit | 授权页逐项解释"为什么需要 / 不会用于什么"；只读睡眠时长、静息心率、HRV、步数的按天聚合；随时撤销；对数据缺失/设备未连接/权限被拒均有处理 |
| 🌱 主动关心 | 只有在授权 + 基线充足 + 多项同时变化或持续变化时触发；不确定性语言；每条提示附"为什么出现这条提示"+ 忽略/关闭入口 |
| 🛟 安全策略 | 独立的 SafetyGuard 模块（不依赖提示词）：safe / support / urgent 三级；urgent 完全绕过 LLM，返回版本化固定危机脚本 |
| 🧹 数据自主 | 导出全部数据（JSON）、清空对话、删除本机全部数据、清除服务器数据 |

## 技术栈

- **iOS**：Swift 5.9 / SwiftUI / SwiftData / HealthKit / Keychain（iOS 17+）
- **后端**：Python 3.12 / FastAPI / Pydantic v2 / SQLAlchemy 2 / SQLite（可换）
- **LLM**：Provider 抽象层，默认 `offline` 零依赖；任何兼容 OpenAI Chat Completions 协议的供应商均可通过环境变量接入，不绑定厂商
- **测试**：pytest（后端 78 项，覆盖 11 个必备安全场景）+ XCTest（iOS，需 macOS）
- **部署**：Docker / docker-compose；GitHub Actions CI

## 仓库结构

```
MindPulse/
├── backend/          # FastAPI 后端（SafetyGuard、CareEngine、LLM 抽象层）
│   ├── app/
│   └── Dockerfile
├── ios/              # SwiftUI 客户端（XcodeGen 工程）
│   ├── project.yml
│   ├── MindPulse/
│   └── MindPulseTests/
├── prompts/          # 版本化聊天 Prompt + 危机脚本 + CHANGELOG
├── docs/             # 架构与安全设计文档
├── tests/            # 后端自动化测试（11 个必备场景）
├── scripts/          # 密钥扫描等工具
├── .env.example      # 开发环境配置模板
├── docker-compose.yml
├── README.md / SECURITY.md / PRIVACY.md / CONTRIBUTING.md / LICENSE
```

## 本地运行

### 后端（含"无密钥离线模式"）

```bash
# 1) 克隆并进入仓库
git clone https://github.com/xuqiuhu2025/mindpulse.git
cd mindpulse

# 2) 创建虚拟环境并安装依赖（Python ≥ 3.12）
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt

# 3) 配置环境变量（可选——默认 offline 模式零配置即可启动）
cp .env.example backend/.env
# 编辑 backend/.env：
#   MINDPULSE_LLM_PROVIDER=openai_compatible
#   MINDPULSE_LLM_API_KEY=<你的 key，只放在服务端>
#   MINDPULSE_LLM_BASE_URL=https://api.openai.com/v1   # 或任何兼容供应商
#   MINDPULSE_LLM_MODEL=gpt-4o-mini

# 4) 启动
cd backend
uvicorn app.main:app --reload --port 8000
# 打开 http://127.0.0.1:8000/docs 查看交互式 API 文档
```

默认 `MINDPULSE_LLM_PROVIDER=offline` 时使用确定性兜底回复——不调用任何外部服务，便于开发与测试。

### Docker 方式

```bash
cp .env.example .env   # 按需填写
docker compose up --build
```

### iOS 客户端

本项目用 [XcodeGen](https://github.com/yonaskolb/XcodeGen) 管理工程：

```bash
brew install xcodegen
cd ios
xcodegen generate      # 生成 MindPulse.xcodeproj
open MindPulse.xcodeproj
```

#### HealthKit 配置步骤

1. Xcode 中选择 **MindPulse** target → **Signing & Capabilities**：
   - 选择你的开发者 Team（HealthKit 需要真机签名；模拟器可用但通常没有真实数据）。
   - `MindPulse.entitlements` 已包含 `com.apple.developer.healthkit`。
2. `Info.plist` 的健康数据用途说明已配置（`NSHealthShareUsageDescription` 等）。
3. 连接 iPhone，运行应用 → 健康页阅读说明 → 点击"我了解并同意，开始授权"。
4. 系统弹窗中选择允许的类别；MindPulse 只读取睡眠时长、静息心率、HRV、步数的**每日汇总**。
5. 撤销入口：App 内 **设置 → 健康数据** 关闭开关，或 iOS 系统设置 → 健康中管理权限。

> 注意：iOS 源码已通过 CI（macOS runner + iPhone 模拟器）编译与单元测试验证（20 项 XCTest 全部通过）；真机上的 HealthKit 实际数据链路尚未人工验证，首次真机构建如遇问题请提 issue。

## 环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `MINDPULSE_ENVIRONMENT` | `development` | 运行环境 |
| `MINDPULSE_LOG_LEVEL` | `INFO` | 日志级别（日志已脱敏） |
| `MINDPULSE_DATABASE_URL` | `sqlite:///./mindpulse.db` | SQLAlchemy 连接串 |
| `MINDPULSE_LLM_PROVIDER` | `offline` | `offline` / `openai_compatible` |
| `MINDPULSE_LLM_API_KEY` | 空 | **只在服务端**，严禁写入 iOS 或仓库 |
| `MINDPULSE_LLM_BASE_URL` | `https://api.openai.com/v1` | 任何兼容供应商地址 |
| `MINDPULSE_LLM_MODEL` | `gpt-4o-mini` | 模型名 |
| `MINDPULSE_CORS_ORIGINS` | 本地调试地址 | 逗号分隔 |

## 如何运行测试

```bash
# 后端（含密钥扫描）
python scripts/check_no_secrets.py
pytest -q --cov=backend/app --cov-report=term-missing

# iOS（需要 macOS + Xcode 15+）
cd ios && xcodegen generate
xcodebuild test -project MindPulse.xcodeproj -scheme MindPulse \
  -destination 'platform=iOS Simulator,name=iPhone 16'
```

测试覆盖以下 11 个必备安全场景（`tests/`）：

1. 普通闲聊正常响应；2. 工作压力得到共情而非危机话术；3. 持续低落进入 support 层；4. 明确自伤表达 → 固定危机脚本；5. 表达立即危险 → 优先急救指引；6. 撤销 HealthKit 授权后拒绝写入并停止建议；7. 无足够历史数据不生成结论；8. 单一 HRV 短时变化不触发任何疾病判断；9. 删除后数据不可读取；10. Prompt injection 无法关闭安全规则；11. API key / 聊天原文 / 健康数值不出现在日志与客户端请求中。

## 如何删除用户数据

- **App 内**：设置 → 数据与隐私 → 「清空当前对话」/「删除全部数据（本机）」/「清除服务器上的数据」/「导出我的数据 (JSON)」。
- **API**（`X-Device-ID` 为客户端本地生成的伪匿名标识）：
  ```bash
  curl -X DELETE https://<server>/api/data/all -H "X-Device-ID: <device-id>"
  ```
- 撤销 HealthKit：设置 → 健康数据，关闭对应开关（立即停止读取与上传）。

## 当前已知限制

- ⚠️ **SafetyGuard 是正则规则，不是自然语言理解**：存在误报与漏报（详见 `docs/SAFETY_DESIGN.md`），需要持续迭代与人工评审。**它不能替代专业危机干预系统**。
- 危机资源是静态开源数据，号码可能变更；每条带来源与核对日期，依赖社区持续核对。
- 无账户体系（伪匿名 device-id）：换设备不迁移数据。
- 主动关心引擎的阈值是工程默认值，未经临床验证。
- 真实 LLM 场景下模型仍可能输出不完美内容：有输出侧二次筛查兜底，但上线前建议人工评估。
- iOS 单元测试已在 CI（macOS 模拟器）通过；真机 HealthKit 实数据链路仍待人工验证。
- 暂不支持语音、图片、多语言界面。

## 未来计划

- [ ] 多语言（i18n 框架与英文界面完善）
- [ ] 本地 LLM / 端侧推理选项（进一步提升隐私）
- [ ] 危机资源接入权威实时目录 API，减少静态数据依赖
- [ ] 心情记录的可选提醒（本地通知，用户完全可控）
- [ ] 心理学专业顾问参与安全策略评审
- [ ] 端到端加密的服务端存储方案研究
- [ ] 更完善的无障碍（VoiceOver / Dynamic Type 全面适配）

## 危机场景的安全边界

详见 [docs/SAFETY_DESIGN.md](docs/SAFETY_DESIGN.md)。要点：

- urgent 级别的回复**完全由 SafetyGuard 生成固定脚本**，不经过 LLM，杜绝"说漏嘴"。
- 脚本会：确认是否处于立即危险、询问身边是否有可陪伴的人、建议把危险物品交给可信任的人保管、指向当地急救/危机热线/急诊室、明确说明对话不保证保密。
- 绝不提供自伤方法、剂量、地点或规避救援的信息；绝不制造排他性依赖（不说"我会一直陪着你""你只有我"）。
- 无用户所在地信息时，先询问国家或地区再给出本地资源。

## 隐私

数据收集清单、保存期限、删除方式见 [PRIVACY.md](PRIVACY.md)。核心：本地优先存储、只收聚合数据、日志脱敏、无账户无追踪、一键删除。

## 贡献与许可

欢迎 Issue 与 PR——安全相关代码（`safety/`、`prompts/`、危机脚本）的修改有强制评审要求，见 [CONTRIBUTING.md](CONTRIBUTING.md)。

本项目以 [MIT License](LICENSE) 发布。

---

**再次强调**：MindPulse 不是医疗产品，不提供医学诊断或紧急服务。危机时刻，请联系当地急救服务、前往最近的急诊室，或通过 [findahelpline.com](https://findahelpline.com) 查找你所在地区的求助热线。
