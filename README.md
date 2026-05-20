# AI增强版Web自动化测试平台

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-blue?style=flat-square&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/Playwright-1.49-green?style=flat-square&logo=playwright" alt="Playwright">
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi" alt="FastAPI">
  <img src="https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react" alt="React">
  <img src="https://img.shields.io/badge/MySQL-8.0-4479A1?style=flat-square&logo=mysql" alt="MySQL">
  <img src="https://img.shields.io/badge/Docker-latest-2496ED?style=flat-square&logo=docker" alt="Docker">
  <img src="https://img.shields.io/badge/Jenkins-CI/CD-D24939?style=flat-square&logo=jenkins" alt="Jenkins">
</p>

Web自动化测试平台，集成 UI 自动化、API 自动化、AI 智能分析、可视化看板与 CI/CD 全流程交付。基于 Page Object 模式与数据驱动架构，通过 GPT-4o 多模态能力实现失败根因自动分析，并提供完整的前后端分离管理平台。

---

## 目录

- [系统架构](#系统架构)
- [核心功能](#核心功能)
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
┌─────────────────────────────────────────────────────┐
│           React 前端看板（localhost:5173）            │
│    测试看板 / 执行触发 / 失败详情 / AI 分析           │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP /api
┌──────────────────────▼──────────────────────────────┐
│           FastAPI 后端服务（localhost:8000）           │
│   /runner（触发）  /reports（数据）  /ai（分析）      │
└─────────┬──────────────────┬──────────────┬──────────┘
          │                  │              │
   ┌──────▼──────┐   ┌───────▼──────┐  ┌───▼────────┐
   │ Pytest 引擎  │   │  MySQL 数据库 │  │ OpenAI API │
   │  UI + API   │   │  结果持久化   │  │  AI 分析   │
   └──────┬──────┘   └──────────────┘  └────────────┘
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

### AI 智能辅助

| 功能 | 入口 | 说明 |
|------|------|------|
| 失败根因分析 | 报告详情 → AI 分析 | 截图 + 错误日志多模态分析，输出失败类型、根因、修复建议、置信度 |
| 用例生成 | AI 分析 → 用例生成 | 输入用户故事，生成覆盖正常/边界/异常场景的结构化测试用例 |
| 执行摘要 | 报告详情 → AI 摘要 | 分析执行结果，生成风险等级、关键问题、优化建议 |
| 选择器修复 | AI 分析 → 选择器修复 | 失效选择器 + 页面 HTML，推荐替代选择器 |

> AI 功能为**可选模块**。未配置 `OPENAI_API_KEY` 时所有 AI 接口自动降级返回 `available: false`，不影响测试主流程执行。

### 可视化平台

- **测试看板**：统计卡片（通过率 / 通过 / 失败 / 跳过）+ 执行趋势折线图 + 历史记录表格
- **执行触发**：前端选择模块、环境、标签，异步触发测试，每 2 秒轮询展示实时进度
- **失败详情**：失败用例列表，支持查看错误日志、失败截图、逐条触发 AI 分析
- **邮件通知**：测试完成后自动发送 HTML 格式邮件，包含统计数据、失败用例列表

---

## 技术栈

| 分类 | 技术 | 说明 |
|------|------|------|
| 测试框架 | Pytest 9 | fixture 机制、Hook、parametrize 参数化 |
| UI 自动化 | Playwright 1.49 | 内置自动等待，BrowserContext 隔离，Trace Viewer |
| API 测试 | Requests 2.32 | Session 复用，统一封装日志与断言 |
| 测试报告 | Allure 2.13 | 步骤 / 截图 / 附件 / 环境信息 / 中文分类 |
| 后端服务 | FastAPI 0.115 | 异步框架，自动生成 OpenAPI 文档 |
| 数据库 | MySQL 8 + SQLAlchemy 2 | 异步 ORM，连接池管理 |
| 前端 | React 18 + Ant Design 5 | Recharts 趋势图，axios 请求封装 |
| AI | OpenAI GPT-4o | 多模态视觉分析，结构化 JSON 输出 |
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
- Git

### 1. 克隆仓库

```bash
git clone https://github.com/your-username/web-auto-test-framework.git
cd web-auto-test-framework
```

### 2. Python 环境

```bash
# 创建虚拟环境
python -m venv .venv

# 激活（Windows）
.venv\Scripts\activate.bat
# 激活（macOS / Linux）
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/

# 安装 Playwright 浏览器
playwright install chromium
```

### 3. 前端环境

```bash
cd frontend
npm install
cd ..
```

### 4. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填写数据库连接、邮件配置等
```

### 5. 创建数据库（使用 MySQL 时）

```sql
CREATE DATABASE testdb CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 6. 安装 Allure 命令行工具

```bash
# macOS
brew install allure

# Windows（Scoop）
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
│   │   ├── pages/                  # Page Object 层
│   │   │   ├── base_page.py        # 基类：封装定位、等待、断言、截图
│   │   │   ├── login_page.py       # 登录页面对象
│   │   │   └── dashboard_page.py   # 商品列表页面对象
│   │   └── test_cases/
│   │       └── test_login.py       # UI 测试用例（登录 / 退出 / 购物车）
│   └── api/
│       ├── client/
│       │   └── http_client.py      # requests 封装：日志 / 断言 / Allure 附件
│       ├── postman_runner.py        # Newman CLI 执行 Postman Collection
│       └── test_cases/
│           └── test_user_api.py    # API 测试用例（JSONPlaceholder）
│
├── core/                           # 公共基础库
│   ├── config_reader.py            # 单例配置读取，支持点号路径和多环境合并
│   ├── log_factory.py              # Loguru 日志工厂，控制台 + 文件双输出
│   ├── allure_helper.py            # Allure 附件封装、环境信息写入
│   └── db_client.py                # SQLAlchemy 异步 ORM，三张核心数据表
│
├── ai/                             # AI 增强模块
│   ├── failure_analyzer.py         # GPT-4o 多模态失败根因分析
│   ├── case_generator.py           # 基于用户故事生成测试用例
│   └── locator_healer.py           # 失效选择器智能修复
│
├── backend/                        # FastAPI 后端服务
│   ├── main.py                     # 应用入口、路由注册、生命周期管理
│   ├── models/
│   │   └── schemas.py              # Pydantic 请求 / 响应模型
│   ├── routers/
│   │   ├── test_runner.py          # 测试触发接口（线程池 + 主循环 DB 写入）
│   │   ├── reports.py              # 报告数据接口（看板 / 趋势 / 失败用例 / AI 摘要）
│   │   └── ai_analysis.py          # AI 功能接口（分析 / 生成 / 修复 / 历史记录）
│   └── services/
│       ├── email_service.py        # SMTP 邮件通知（HTML 模板）
│       ├── allure_parser.py        # Allure JSON 结果解析
│       └── jenkins_service.py      # Jenkins API 集成
│
├── frontend/                       # React 前端
│   └── src/
│       ├── api/index.ts            # axios 封装，所有后端接口类型定义
│       ├── components/
│       │   └── AppLayout.tsx       # 全局布局（侧边栏 + 顶部导航）
│       └── pages/
│           ├── Dashboard.tsx       # 测试看板（统计 + 趋势图 + 执行记录）
│           ├── TestRunner.tsx      # 执行触发（异步轮询进度）
│           ├── AIAnalysis.tsx      # AI 智能辅助（分析 / 生成 / 修复）
│           ├── ReportDetail.tsx    # 失败用例详情（截图 + 错误 + AI 分析）
│           └── ReportSummary.tsx   # AI 执行摘要（风险等级 + 关键问题 + 建议）
│
├── config/
│   ├── config.yaml                 # 基础配置（浏览器、URL、超时）
│   ├── dev.yaml                    # 开发环境覆盖
│   └── prod.yaml                   # 生产环境覆盖
│
├── data/
│   ├── login_data.yaml             # UI 登录测试数据
│   └── api_data.yaml               # API 测试数据
│
├── .env.example                    # 环境变量模板
├── pytest.ini                      # pytest 全局配置
├── requirements.txt                # Python 依赖
├── Dockerfile                      # 测试镜像构建（含 Playwright 浏览器）
├── docker-compose.yml              # 多容器编排（后端 / 测试执行 / Allure 服务）
└── Jenkinsfile                     # 多模式并行流水线
```

---

## 使用说明

### 直接运行测试

```bash
# 确保虚拟环境已激活

# 全量测试
pytest

# 按标签筛选
pytest -m smoke          # 冒烟测试（约 30 秒）
pytest -m "p0 and ui"    # P0 级 UI 测试

# 并行执行
pytest -n 4

# 失败自动重试
pytest --reruns 2 --reruns-delay 1
```

### 查看 Allure 报告

```bash
allure serve reports/allure-results
```

### 启动完整平台

```bash
# 终端 1：后端服务
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# 终端 2：前端看板
cd frontend && npm run dev
# 访问 http://localhost:5173

# 终端 3（可选）：Allure 报告服务
docker run -p 5050:5050 \
  -v $(pwd)/reports/allure-results:/app/allure-results \
  frankescobar/allure-docker-service
```

### 通过前端触发测试

1. 打开 `http://localhost:5173`
2. 进入「执行测试」页面
3. 选择模块（全量 / UI / API）、环境（Dev / Test / Prod）
4. 标签过滤可选填（如 `smoke`），**留空则执行全部用例**
5. 点击「开始执行」，页面自动轮询展示进度
6. 执行完成后在「测试看板」查看结果，邮件同步收到通知

### Docker 部署

```bash
# 构建镜像
docker build -t web-auto-test-framework .

# 启动后端 + Allure 服务
docker compose up backend allure -d

# 在容器内执行测试（test 环境）
docker compose --profile test run test-runner
```

---

## 环境变量

复制 `.env.example` 为 `.env` 并填写以下配置：

| 变量 | 必填 | 默认值 | 说明 |
|------|:----:|--------|------|
| `TEST_ENV` | 否 | `dev` | 运行环境：`dev` / `test` / `prod` |
| `TEST_USER` | 是 | — | 被测应用登录用户名 |
| `TEST_PASSWORD` | 是 | — | 被测应用登录密码 |
| `DB_URL` | 否 | SQLite | 数据库连接串，MySQL 示例：`mysql+aiomysql://user:pass@localhost:3306/testdb` |
| `OPENAI_API_KEY` | 否 | — | OpenAI Key，未填则 AI 功能自动降级 |
| `OPENAI_BASE_URL` | 否 | `https://api.openai.com/v1` | 可替换为国内代理地址 |
| `ALERT_EMAIL` | 否 | — | 邮件通知收件人，多个用英文逗号分隔 |
| `SMTP_HOST` | 否 | `smtp.qq.com` | SMTP 服务器地址 |
| `SMTP_PORT` | 否 | `465` | SMTP 端口 |
| `SMTP_USER` | 否 | — | 发件人邮箱地址 |
| `SMTP_PASSWORD` | 否 | — | 邮箱授权码（非登录密码） |
| `SMTP_USE_SSL` | 否 | `true` | 是否使用 SSL |
| `PLATFORM_URL` | 否 | `http://localhost:5173` | 前端看板地址（邮件跳转链接） |
| `ALLURE_URL` | 否 | `http://localhost:5050` | Allure 报告服务地址 |
| `JENKINS_URL` | 否 | — | Jenkins 地址 |
| `JENKINS_USER` | 否 | — | Jenkins 用户名 |
| `JENKINS_TOKEN` | 否 | — | Jenkins API Token |

> **安全提示**：`.env` 已加入 `.gitignore`，请勿将包含真实密钥的 `.env` 文件提交到版本库。

---

## CI/CD 配置

### Jenkins 插件要求

- Pipeline
- Git
- Allure Jenkins Plugin
- Email Extension Plugin
- Docker Pipeline

### 流水线模式

在 Jenkins 任务的 `PIPELINE_TYPE` 参数中选择：

| 模式 | 说明 | 适用场景 |
|------|------|---------|
| `single` | 单环境顺序执行 | 日常手动触发 |
| `multi-env` | DEV（冒烟）+ TEST（全量）并行 | 合并主干后验证 |
| `smoke-only` | 仅执行 `smoke` 标签用例 | 快速冒烟验证 |

### 触发方式

- **手动触发**：在 Jenkins 任务页面点击「立即构建」
- **定时触发**：Jenkinsfile 中已配置每日 02:00 自动执行全量回归
- **Webhook 触发**：在 GitHub / Gitee 仓库配置 Jenkins Webhook，代码推送后自动触发

### 全局环境变量（在 Jenkins 系统配置中添加）

| 变量名 | 说明 |
|--------|------|
| `TEAM_EMAIL` | 告警通知邮箱 |

---

## 注意事项

**通过前端平台触发测试时**，必须将 `config/dev.yaml` 中的 `browser.headless` 设为 `true`，因为后端子进程无法打开 GUI 浏览器窗口：

```yaml
# config/dev.yaml
browser:
  headless: true
```

本地直接运行 `pytest` 调试时，可临时改为 `false` 以便观察浏览器操作。

**MySQL 连接失败时**，执行以下 SQL 确认用户权限：

```sql
GRANT ALL PRIVILEGES ON testdb.* TO 'your_user'@'localhost';
FLUSH PRIVILEGES;
```

若出现 `caching_sha2_password` 认证报错，安装 cryptography 包：

```bash
pip install cryptography
```

**AI 功能返回 429 错误**，表示 OpenAI 账户余额不足，前往 [platform.openai.com/settings/billing](https://platform.openai.com/settings/billing) 充值后重试。

---

## License

[MIT License](LICENSE)