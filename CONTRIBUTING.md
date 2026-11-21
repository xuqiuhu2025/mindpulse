# CONTRIBUTING.md — 参与贡献

感谢关注 MindPulse。这个项目对"安全"的要求高于一般应用，请先读完本文件再动手。

## 行为准则

对任何贡献者保持尊重与善意。请勿在代码库、Issue 或讨论中：

- 提供自伤/他伤的方法、剂量、地点或规避救援的信息；
- 使用诊断性语言描述他人或自己；
- 发布聊天记录、健康数据等真实用户内容。

## 环境搭建

```bash
# 后端
python -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
pytest -q                     # 必须全绿

# iOS（macOS）
brew install xcodegen
cd ios && xcodegen generate
xcodebuild test -project MindPulse.xcodeproj -scheme MindPulse \
  -destination 'platform=iOS Simulator,name=iPhone 16'
```

提交前请本地运行：

```bash
python scripts/check_no_secrets.py   # 密钥扫描，CI 同样会执行
```

## ⚠️ 安全评审要求（强制）

以下路径的修改必须经过**人工安全评审**（由维护者或受邀的心理学/危机干预背景贡献者执行），并在 PR 中说明动机与影响面：

- `backend/app/safety/`（分级规则、模式库）
- `prompts/`（尤其 `crisis_*` 危机脚本）
- `backend/app/services/care_engine.py`（主动关心阈值与文案）
- `backend/app/resources/crisis_resources.json`（危机资源数据）

同时必须同步更新：

- `tests/test_safety_guard.py` / `tests/test_prompts.py` 等（契约断言）；
- `docs/SAFETY_DESIGN.md`（设计文档）；
- `prompts/CHANGELOG.md`（Prompt 版本变更记录）。

## 提交规范

- 使用 Conventional Commits：`feat: …` / `fix: …` / `docs: …` / `test: …` / `refactor: …`
- 一个 PR 聚焦一件事；安全类修改单独成 PR。
- 不提交任何真实密钥、真实用户数据、真实健康数据；`.env` 与 `*.db` 已被 .gitignore 覆盖，请保持。

## 危机资源更新

`backend/app/resources/crisis_resources.json` 中的每条资源都必须带 `source`（官方/权威来源链接）与 `verified`（核对日期 YYYY-MM）。提交 PR 时请附上你核对时的截图或链接。

## 分支与发布

- `main` 为稳定分支，CI 必须全绿；
- 版本遵循 SemVer；发布时打 tag 并在 GitHub Releases 提供说明。

## 新手友好任务

查找标记了 `good first issue` 的 Issue。文档翻译、危机资源核对、测试补充都是高价值贡献。
