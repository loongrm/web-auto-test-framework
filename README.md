# 企业级 AI 增强 Web 自动化测试平台

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://python.org)
[![Playwright](https://img.shields.io/badge/Playwright-1.49-green.svg)](https://playwright.dev)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB.svg)](https://react.dev)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 项目架构
1. **React 前端看板**
   - 模块：Dashboard/TestRunner/AI分析
   - 通信：HTTP/api

2. **FastAPI 后端服务（:8000）**
   - 接口：/runner/reports/ai/screenshots(静态)

3. **底层依赖**
   - Pytest 引擎（UI + API）
   - SQLite DB（结果持久化）
   - OpenAI API（AI分析）

4. **CI/CD**
   - Jenkins + Docker
   - 多环境并行 + 企业微信通知

## 核心特性

| 特性 | 说明 |
|------|------|
| **UI 自动化** | Playwright + Page Object 模式，支持 chromium/firefox/webkit |
| **API 自动化** | requests 封装 + Postman Collection 导入执行 |
| **数据驱动** | YAML 外部测试数据，零代码修改切换用例 |
| **Allure 报告** | 自动生成带截图、步骤、参数的可视化报告 |
| **AI 失败分析** | 上传截图+日志，GPT-4o 视觉分析根因和修复建议 |
| **AI 用例生成** | 输入用户故事，自动生成 UI/API 测试用例集 |
| **AI 报告摘要** | 执行结束后 AI 生成摘要、关键问题、优化建议 |
| **前端看板** | React + Ant Design，实时执行触发、趋势图、详情页 |
| **CI/CD** | Jenkins 多环境并行流水线，企业微信实时通知 |
| **容器化** | Docker + docker-compose，环境一致性保证 |

## 快速使用

### 1. 环境准备

```bash
# Python 3.12+
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# Node.js 18+
cd frontend && npm install && cd ..

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入真实值（OPENAI_API_KEY可选）
```

### 2. 运行测试

```bash
# 全量测试（生成Allure报告）
pytest

# 按标签运行
pytest -m smoke              # 冒烟测试
pytest -m "p0 and ui"        # P0 级 UI 测试

# 并行执行
pytest -n 4

# 失败重试
pytest --reruns 2 --reruns-delay 1
```

### 3. 查看 Allure 报告

```bash
allure serve reports/allure-results
# 浏览器自动打开 http://localhost:XXXXX
```

### 4. 启动完整平台

```bash
# 终端1：后端服务
uvicorn backend.main:app --reload --port 8000

# 终端2：前端看板
cd frontend && npm run dev
# 访问 http://localhost:5173

# 终端3（可选）：Allure 报告服务
docker run -p 5050:5050 \
  -v $(pwd)/reports/allure-results:/app/allure-results \
  frankescobar/allure-docker-service
```

### 5. Docker 一键启动

```bash
# 启动后端 + Allure 服务
docker compose up backend allure -d

# 执行测试（test 环境）
docker compose --profile test run test-runner

# 查看报告：http://localhost:5050
```

## 目录说明
```text
auto-test-platform/
├── tests/
│   ├── ui/
│   │   ├── pages/          # Page Object（定位器集中管理）
│   │   └── test_cases/     # UI 测试用例
│   ├── api/
│   │   ├── client/         # requests 封装
│   │   └── test_cases/     # API 测试用例
│   └── conftest.py         # Playwright fixtures + 截图 Hook
├── core/                   # 公共基础库
│   ├── config_reader.py    # 多环境配置读取
│   ├── log_factory.py      # Loguru 日志工厂
│   ├── allure_helper.py    # Allure 附件工具
│   └── db_client.py        # SQLAlchemy 异步 ORM
├── ai/                     # AI 增强模块
│   ├── failure_analyzer.py # GPT-4o 视觉失败分析
│   ├── case_generator.py   # AI 测试用例生成
│   └── locator_healer.py   # 智能选择器修复
├── backend/                # FastAPI 后端
│   ├── main.py
│   ├── routers/            # test_runner / reports / ai_analysis
│   ├── services/           # wechat / jenkins / allure_parser
│   └── models/             # Pydantic schemas
├── frontend/               # React + Ant Design 看板
│   └── src/
│       ├── pages/          # Dashboard / TestRunner / AIAnalysis / ReportDetail / ReportSummary
│       ├── components/     # AppLayout
│       └── api/            # axios 封装
├── data/                   # YAML 测试数据
├── config/                 # 多环境配置
├── Dockerfile
├── docker-compose.yml
└── Jenkinsfile             # 多环境并行流水线
```

## 环境变量说明

| 变量 | 必填 | 说明 |
|------|------|------|
| `TEST_ENV` | 否 | 环境选择：dev/test/prod，默认 dev |
| `TEST_USER` | 是 | 被测应用登录用户名 |
| `TEST_PASSWORD` | 是 | 被测应用登录密码 |
| `OPENAI_API_KEY` | 否 | OpenAI Key，不填则 AI 功能降级跳过 |
| `OPENAI_BASE_URL` | 否 | 可替换为代理地址 |
| `WECHAT_WEBHOOK` | 否 | 企业微信群机器人 Webhook |
| `JENKINS_URL` | 否 | Jenkins 地址 |
| `DB_URL` | 否 | 数据库连接串，默认 SQLite |

## AI功能说明

> **AI功能为可选模块**，未配置`OPENAI_API_KEY`时所有AI接口自动降级，不影响正常测试执行。

| 功能 | 入口 | 说明 |
|------|------|------|
| 失败根因分析 | 看板→报告详情→AI分析 | 截图+日志 → 失败类型+修复建议 |
| 用例生成 | AI分析→用例生成 Tab | 用户故事 → 结构化测试用例 |
| 报告摘要 | 看板→AI摘要按钮 | 执行结果 → 风险等级+关键问题+建议 |
| 选择器修复 | AI分析→选择器修复 Tab | 失效选择器+HTML → 替代选择器 |

## Jenkins配置

1. 安装插件：Allure、Pipeline、Git、Email Extension
2. 创建Pipeline任务，选择`Pipeline from SCM`
3. 配置环境变量（在Credentials中存储敏感信息）：
   - `WECHAT_WEBHOOK`：企业微信Webhook URL
   - `TEAM_EMAIL`：故障通知邮箱
4. 流水线类型（`PIPELINE_TYPE`参数）：
   - `single`：单环境顺序执行
   - `multi-env`：DEV + TEST并行执行，适合合并主干时用
   - `smoke-only`：仅执行冒烟用例，适合快速验证

## 项目要点

- **分层设计**：Page Object + 数据驱动，用例/数据/页面三层解耦
- **AI 集成**：GPT-4o多模态分析失败截图，智能输出根因和修复方案
- **工程化**：FastAPI+React完整前后端分离，SQLite持久化执行历史
- **CI/CD**：Jenkins多环境并行流水线，Docker容器化，企业微信实时通知
- **可观测性**：Allure报告 + 失败截图 + 结构化日志，三位一体排障链路