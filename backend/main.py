import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from backend.routers import test_runner, reports, ai_analysis
from core.db_client import DBClient
from core.log_factory import log


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化数据库
    await DBClient.init()
    log.info("数据库初始化完成")

    # 创建必要目录
    for d in ["reports/allure-results", "logs", "screenshots", "data"]:
        Path(d).mkdir(parents=True, exist_ok=True)

    yield

    log.info("后端服务已停止")


app = FastAPI(
    title="自动化测试平台 API",
    version="1.0.0",
    description="企业级 Web 自动化测试平台 - 支持 UI/API/AI 测试",
    lifespan=lifespan,
)

# CORS（允许前端 localhost:5173 访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(test_runner.router, prefix="/api/runner", tags=["测试执行"])
app.include_router(reports.router, prefix="/api/reports", tags=["测试报告"])
app.include_router(ai_analysis.router, prefix="/api/ai", tags=["AI 分析"])


@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}