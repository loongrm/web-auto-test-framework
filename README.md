# AI 增强 Web 自动化测试平台

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-blue?style=flat-square&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/Playwright-1.49-green?style=flat-square&logo=playwright" alt="Playwright">
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi" alt="FastAPI">
  <img src="https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react" alt="React">
  <img src="https://img.shields.io/badge/RAG-ChromaDB-orange?style=flat-square" alt="RAG">
  <img src="https://img.shields.io/badge/Ollama-本地LLM-black?style=flat-square" alt="Ollama">
  <img src="https://img.shields.io/badge/Docker-latest-2496ED?style=flat-square&logo=docker" alt="Docker">
  <img src="https://img.shields.io/badge/Jenkins-CI/CD-D24939?style=flat-square&logo=jenkins" alt="Jenkins">
</p>

Web 自动化测试平台，集成 UI 自动化、API 自动化、**基于 RAG 的 AI 失败分析**、可视化看板与 CI/CD 全流程交付。基于 Page Object 模式与数据驱动架构，AI 模块采用检索增强生成（RAG）+ 本地大模型，实现零成本、可离线、带知识积累的失败根因分析。

---

## 目录

- [系统架构](#系统架构)
- [核心功能](#核心功能)
- [AI 模块（RAG）设计](#ai-模块rag设计)
- [技术栈](#技术栈)
- [快速开始](#快速开始)
- [项目结构](#项目结构)
- [使用说明](#使用说明)
- [环境变量](#环境变量)
- [CI/CD 配置](#cicd-配置)
- [注意事项](#注意事项)

---

## 系统架构

```
┌──────────────────────────────────────────────────────┐
│            React 前端看板（localhost:5173）            │
│      测试看板 / 执行触发 / 失败详情 / AI 分析          │
└───────────────────────┬──────────────────────────────┘
                        │ HTTP /api
┌───────────────────────▼──────────────────────────────┐
│            FastAPI 后端服务（localhost:8000）          │
│   /runner（触发）  /reports（数据）  /ai（RAG 分析）   │
└────────┬──────────────────┬──────────────┬───────────┘
         │                  │              │
  ┌──────▼──────┐   ┌───────▼──────┐  ┌───▼──────────────┐
  │ Pytest 引擎  │   │  MySQL 数据库 │  │ RAG 失败分析子系统 │
  │  UI + API   │   │  结果持久化   │  │ 见下方 RAG 设计    │
  └──────┬──────┘   └──────────────┘  └──────────────────┘
         │
  ┌──────▼──────────────────────────────┐
  │  CI/CD：Jenkins + Docker            │
  │  多环境并行流水线 + 邮件通知         │
  └─────────────────────────────────────┘
```

---

## 核心功能

### 测试框架

| 功能 | 说明 |
|------|------|
| UI 自动化 | Playwright + Page Object 模式，三层架构（BasePage / PageObject / TestCase）解耦 |
| API 自动化 | requests 封装 HttpClient，统一日志、断言与 Allure 附件，支持 Postman Collection 导入 |
| 数据驱动 | YAML 文件管理测试数据，`pytest.mark.parametrize` 参数化，零代码扩展用例 |
| 多浏览器 | 支持 Chromium / Firefox / WebKit，headless 模式可配置 |
| 并行执行 | pytest-xdist 多进程并行，`-n auto` 按 CPU 核数自动分配 |
| 失败重试 | pytest-rerunfailures 自动重试，过滤偶发环境问题 |

### 可观测性

| 功能 | 说明 |
|------|------|
| Allure 报告 | 自动生成带步骤、截图、请求响应的可视化报告 |
| 失败截图 | 用例失败时 Hook 自动截图并附加到 Allure 报告 |
| 结构化日志 | Loguru 按天切割，分 INFO / ERROR 双文件输出，线程安全 |
| 执行历史 | MySQL 持久化每次执行记录，支持趋势分析与历史查询 |

### AI 智能分析（RAG）

| 功能 | 入口 | 说明 |
|------|------|------|
| 失败根因分析 | AI 分析页 / 失败详情 | 检索历史相似失败案例，结合 LLM 生成失败类型、根因、修复建议、置信度 |
| 知识积累 | 自动 | 每次分析结果回写向量知识库，检索质量随使用提升 |
| 三级降级 | 自动 | 云端 API → 本地 Ollama → 规则引擎，保证任何情况下都有结果 |

> AI 模块**零成本、可离线运行**：默认使用本地 embedding 模型与本地 Ollama，不依赖任何付费 API。未配置任何 LLM 时，自动降级到规则引擎，不影响测试主流程。

### 可视化平台

- **测试看板**：统计卡片（通过率 / 通过 / 失败 / 跳过）+ 执行趋势折线图 + 历史记录表格
- **执行触发**：前端选择模块、环境、标签，异步触发测试，轮询展示实时进度
- **失败详情**：失败用例列表，支持查看错误日志、失败截图、逐条触发 AI 分析
- **邮件通知**：测试完成后自动发送 HTML 格式邮件，包含统计数据、失败用例列表

---

## AI 模块（RAG）设计

失败分析采用检索增强生成（RAG）架构，核心是「检索历史经验 → 增强提示 → 结构化生成 → 回写知识库」的闭环：

```
失败发生
   │
   ▼
1. 构造查询文本（错误类型 + 信息 + 用例名）
   │
   ▼
2. 本地 embedding 编码（bge-small，512 维，离线零成本）
   │
   ▼
3. ChromaDB 检索 top-k 相似历史案例（余弦相似度 + 阈值过滤）
   │
   ▼
4. 增强 prompt（当前失败 + 历史案例的解决方案）
   │
   ▼
5. LLM 生成结构化分析（三级降级 + JSON 模式 + Pydantic 校验）
   │
   ▼
6. 结果回写知识库（知识积累闭环）
```

**关键设计**

| 设计点 | 实现 | 价值 |
|--------|------|------|
| 本地 embedding | sentence-transformers + bge-small-zh | 高频检索零成本、离线、数据不出本机 |
| 向量知识库 | ChromaDB（嵌入式持久化） | 零运维，失败案例持续积累 |
| 三级降级 | 云端 OpenAI → 本地 Ollama → 规则引擎 | LLM 不可用时系统仍可用 |
| 结构化输出 | JSON 模式 + Pydantic 校验 + 容错解析 | 解决小模型 function calling 字段遵守率低的问题 |
| 调用可靠性 | tenacity 指数退避重试，区分可重试 / 不可重试错误 | 网络抖动自动重试，余额不足立即降级 |

---

## 技术栈

| 分类 | 技术 | 说明 |
|------|------|------|
| 测试框架 | Pytest | fixture 机制、Hook、parametrize 参数化 |
| UI 自动化 | Playwright 1.49 | 内置自动等待，BrowserContext 隔离，Trace Viewer |
| API 测试 | Requests 2.32 | Session 复用，统一封装日志与断言 |
| 测试报告 | Allure 2.13 | 步骤 / 截图 / 附件 / 环境信息 / 中文分类 |
| 后端服务 | FastAPI 0.115 | 异步框架，自动生成 OpenAPI 文档 |
| 数据库 | MySQL 8 + SQLAlchemy 2 | 异步 ORM，连接池管理 |
| 前端 | React 18 + Ant Design 5 | Recharts 趋势图，axios 请求封装 |
| AI - LLM | OpenAI SDK（兼容 Ollama） | 云端 GPT-4o / 本地 qwen2.5，统一接口 |
| AI - 检索 | ChromaDB + sentence-transformers | 向量库 + 本地 embedding（bge-small） |
| AI - 可靠性 | Pydantic + tenacity | 结构化约束 + 重试降级 |
| 日志 | Loguru 0.7 | 彩色控制台 + 按天切割文件 |
| 配置管理 | PyYAML + python-dotenv | 多环境 YAML 深度合并，环境变量覆盖 |
| 容器化 | Docker + docker-compose | 多服务编排，测试镜像预装 Playwright 浏览器 |
| CI/CD | Jenkins Pipeline | 多模式流水线，Git Webhook 触发，邮件通知 |

---

## 快速开始

### 前置要求

- Python 3.10+
- Node.js 18+
- MySQL 8.0（或保留默认 SQLite）
- Ollama（可选，用于本地 LLM 失败分析）
- Git

### 1. 克隆仓库

```bash
git clone https://github.com/your-username/web-auto-test-framework.git
cd web-auto-test-framework
```

### 2. Python 环境

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate.bat
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
playwright install chromium
```

### 3. 前端环境

```bash
cd frontend && npm install && cd ..
```

### 4. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填写数据库、邮件等配置
```

### 5. 配置本地 LLM（可选，推荐）

AI 失败分析默认使用本地 Ollama，零成本离线运行：

```bash
# 安装 Ollama: https://ollama.com/download
ollama pull qwen2.5:3b
ollama run qwen2.5:3b "你好"   # 验证可用
```

> 首次运行 AI 分析时，会自动下载本地 embedding 模型（bge-small，约 100MB），需联网一次，之后完全离线。国内可设 `HF_ENDPOINT=https://hf-mirror.com` 加速。

### 6. 安装 Allure 命令行工具

```bash
# macOS
brew install allure
# Windows (Scoop)
scoop install allure
```

---

## 项目结构

```
web-auto-test-framework/
│
├── tests/                          # 测试代码
│   ├── conftest.py                 # Playwright fixture、失败截图 Hook、Allure 环境信息
│   ├── ui/
│   │   ├── pages/                  # Page Object 层（base_page / login_page / dashboard_page）
│   │   └── test_cases/             # UI 测试用例
│   └── api/
│       ├── client/http_client.py   # requests 封装：日志 / 断言 / Allure 附件
│       ├── postman_runner.py        # Newman CLI 执行 Postman Collection
│       └── test_cases/             # API 测试用例
│
├── core/                           # 公共基础库
│   ├── config_reader.py            # 单例配置读取，多环境合并
│   ├── log_factory.py              # Loguru 日志工厂
│   ├── allure_helper.py            # Allure 附件封装
│   └── db_client.py                # SQLAlchemy 异步 ORM，核心数据表
│
├── ai/                             # AI 增强模块（RAG）
│   ├── schemas/
│   │   └── analysis.py             # Pydantic 结构化输出定义 + function calling schema
│   ├── rag/
│   │   ├── embedding.py            # 本地优先 embedding 编码器（云端降级）
│   │   ├── knowledge_base.py       # ChromaDB 失败案例向量知识库
│   │   └── analyzer.py             # RAG 编排器（检索 → 生成 → 回写闭环）
│   └── llm/
│       └── client.py               # LLM 客户端（三级降级 + JSON 模式 + 重试）
│
├── backend/                        # FastAPI 后端服务
│   ├── main.py                     # 应用入口、路由注册、生命周期管理
│   ├── models/schemas.py           # Pydantic 请求 / 响应模型
│   ├── routers/
│   │   ├── test_runner.py          # 测试触发接口（线程池 + 主循环 DB 写入）
│   │   ├── reports.py              # 报告数据接口（看板 / 趋势 / 失败用例 / AI 摘要）
│   │   └── ai_analysis.py          # RAG 失败分析接口
│   └── services/
│       ├── email_service.py        # SMTP 邮件通知（HTML 模板）
│       ├── allure_parser.py        # Allure JSON 结果解析
│       └── jenkins_service.py      # Jenkins API 集成
│
├── frontend/                       # React 前端
│   └── src/
│       ├── api/index.ts            # axios 封装，后端接口类型定义
│       ├── components/AppLayout.tsx
│       └── pages/                  # Dashboard / TestRunner / AIAnalysis / ReportDetail / ReportSummary
│
├── config/                         # 多环境配置（config / dev / prod .yaml）
├── data/                           # YAML 测试数据 + ChromaDB 持久化目录（chroma/）
├── demo.py                         # RAG 子系统独立演示脚本
├── .env.example                    # 环境变量模板
├── pytest.ini                      # pytest 全局配置
├── requirements.txt                # Python 依赖
├── Dockerfile                      # 测试镜像构建
├── docker-compose.yml              # 多容器编排
└── Jenkinsfile                     # 多模式并行流水线
```

---

## 使用说明

### 直接运行测试

```bash
pytest                          # 全量测试
pytest -m smoke                 # 冒烟测试
pytest -m "p0 and ui"           # P0 级 UI 测试
pytest -n 4                     # 并行执行
pytest --reruns 2 --reruns-delay 1   # 失败重试
```

### 查看 Allure 报告

```bash
allure serve reports/allure-results
```

### 启动完整平台

```bash
# 终端 1：后端
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# 终端 2：前端
cd frontend && npm run dev      # 访问 http://localhost:5173

# 终端 3（可选）：Allure 报告服务
docker run -p 5050:5050 \
  -v $(pwd)/reports/allure-results:/app/allure-results \
  frankescobar/allure-docker-service
```

### 验证 AI 模块（独立 demo）

整合进平台前，可单独验证 RAG 子系统：

```bash
python demo.py
```

演示三个场景：知识库冷启动、相似失败检索、LLM 不可用时规则降级。

### 通过前端触发测试

1. 打开 `http://localhost:5173`，进入「执行测试」
2. 选择模块、环境，标签留空则执行全部
3. 点击「开始执行」，轮询展示进度
4. 完成后在「测试看板」查看结果，邮件同步通知
5. 失败用例可在「AI 分析」页粘贴错误日志，获取 RAG 增强的根因分析

---

## 环境变量

复制 `.env.example` 为 `.env` 并填写：

| 变量 | 必填 | 默认值 | 说明 |
|------|:----:|--------|------|
| `TEST_ENV` | 否 | `dev` | 运行环境：`dev` / `test` / `prod` |
| `TEST_USER` | 是 | — | 被测应用登录用户名 |
| `TEST_PASSWORD` | 是 | — | 被测应用登录密码 |
| `DB_URL` | 否 | SQLite | 数据库连接串，MySQL：`mysql+aiomysql://user:pass@localhost:3306/testdb` |
| `OPENAI_API_KEY` | 否 | — | 云端 LLM Key。**留空则使用本地 Ollama** |
| `OPENAI_BASE_URL` | 否 | OpenAI 官方 | 可替换为兼容服务地址（如 deepseek） |
| `OPENAI_MODEL` | 否 | `gpt-4o` | 云端模型名 |
| `OLLAMA_BASE_URL` | 否 | `http://localhost:11434/v1` | 本地 Ollama 地址 |
| `OLLAMA_MODEL` | 否 | `qwen2.5:3b` | 本地模型名 |
| `ALERT_EMAIL` | 否 | — | 邮件收件人，多个用英文逗号分隔 |
| `SMTP_HOST` | 否 | `smtp.qq.com` | SMTP 服务器 |
| `SMTP_PORT` | 否 | `465` | SMTP 端口 |
| `SMTP_USER` | 否 | — | 发件人邮箱 |
| `SMTP_PASSWORD` | 否 | — | 邮箱授权码（非登录密码） |
| `SMTP_USE_SSL` | 否 | `true` | 是否使用 SSL |
| `PLATFORM_URL` | 否 | `http://localhost:5173` | 前端地址（邮件跳转链接） |
| `ALLURE_URL` | 否 | `http://localhost:5050` | Allure 报告地址 |

> **安全提示**：`.env` 已加入 `.gitignore`，请勿提交含真实密钥的 `.env`。

### LLM 后端选择逻辑

系统启动时自动探测，按优先级选定后端：

1. 若配置了有效 `OPENAI_API_KEY` → 使用云端
2. 否则探测本地 Ollama 服务 → 可用则使用本地
3. 都不可用 → 降级到规则引擎

> 想用本地 Ollama，把 `OPENAI_API_KEY` 留空即可。

---

## CI/CD 配置

### Jenkins 插件要求

Pipeline · Git · Allure Jenkins Plugin · Email Extension Plugin · Docker Pipeline

### 流水线模式

| 模式 | 说明 | 适用场景 |
|------|------|---------|
| `single` | 单环境顺序执行 | 日常手动触发 |
| `multi-env` | DEV（冒烟）+ TEST（全量）并行 | 合并主干后验证 |
| `smoke-only` | 仅执行 `smoke` 标签用例 | 快速冒烟验证 |

### 触发方式

- **手动触发**：Jenkins 任务页面「立即构建」
- **定时触发**：Jenkinsfile 已配置每日 02:00 全量回归
- **Webhook 触发**：GitHub / Gitee 配置 Jenkins Webhook，推送后自动触发

---

## 注意事项

**通过前端平台触发测试时**，须将 `config/dev.yaml` 的 `browser.headless` 设为 `true`，因为后端子进程无法打开 GUI 窗口：

```yaml
browser:
  headless: true
```

本地直接 `pytest` 调试时可临时改为 `false` 观察浏览器。

**AI 模块首次运行**会下载本地 embedding 模型（约 100MB），需联网一次。国内加速：

```bash
export HF_ENDPOINT=https://hf-mirror.com   # Windows: set HF_ENDPOINT=...
```

**MySQL 连接失败**时确认用户权限：

```sql
GRANT ALL PRIVILEGES ON testdb.* TO 'your_user'@'localhost';
FLUSH PRIVILEGES;
```

若出现 `caching_sha2_password` 认证报错：`pip install cryptography`。

**本地 Ollama 未生效**（AI 分析走了规则引擎）：确认 Ollama 服务在运行（`ollama list`），且 `.env` 中 `OPENAI_API_KEY` 为空（否则会优先尝试云端）。
