import os
from datetime import datetime
from typing import Optional, List

from sqlalchemy import (
    Column, Integer, String, Float, DateTime,
    Text, Boolean, ForeignKey, select, func
)
from sqlalchemy.ext.asyncio import (
    create_async_engine, AsyncSession, async_sessionmaker
)
from sqlalchemy.orm import DeclarativeBase, relationship

# 数据库连接串（从环境变量读取）
DB_URL = os.getenv("DB_URL", "sqlite+aiosqlite:///./data/test_results.db")


# ORM基类
class Base(DeclarativeBase):
    pass


# 数据表模型

class TestRun(Base):
    """测试执行记录主表"""
    __tablename__ = "test_runs"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    name       = Column(String(200), nullable=False)
    module     = Column(String(50),  default="all")
    env        = Column(String(20),  default="dev")
    status     = Column(String(20),  default="running")   # running | success | failed
    start_time = Column(DateTime,    default=datetime.utcnow)
    end_time   = Column(DateTime,    nullable=True)
    duration   = Column(Float,       default=0.0)
    total      = Column(Integer,     default=0)
    passed     = Column(Integer,     default=0)
    failed     = Column(Integer,     default=0)
    skipped    = Column(Integer,     default=0)
    trigger    = Column(String(50),  default="manual")    # manual | schedule | webhook | jenkins
    git_commit = Column(String(100), nullable=True)
    ai_summary = Column(Text,        nullable=True)       # 缓存 AI 摘要 JSON

    cases      = relationship("TestCase",         back_populates="run", cascade="all, delete-orphan")
    ai_records = relationship("AIAnalysisRecord", back_populates="run", cascade="all, delete-orphan")


class TestCase(Base):
    """单条测试用例执行结果"""
    __tablename__ = "test_cases"

    id              = Column(Integer,      primary_key=True, autoincrement=True)
    run_id          = Column(Integer,      ForeignKey("test_runs.id"), nullable=False)
    name            = Column(String(500),  nullable=False)
    module          = Column(String(100),  default="")
    status          = Column(String(20),   nullable=False)   # passed | failed | skipped
    duration        = Column(Float,        default=0.0)
    error_message   = Column(Text,         nullable=True)
    screenshot_path = Column(String(500),  nullable=True)
    ai_analysis     = Column(Text,         nullable=True)    # 存储 AIAnalysisResult JSON

    run = relationship("TestRun", back_populates="cases")


class AIAnalysisRecord(Base):
    """AI 分析记录（每次调用均保存，可多次分析同一用例）"""
    __tablename__ = "ai_analysis_records"

    id             = Column(Integer,     primary_key=True, autoincrement=True)
    run_id         = Column(Integer,     ForeignKey("test_runs.id"), nullable=True)
    case_id        = Column(Integer,     ForeignKey("test_cases.id"), nullable=True)
    test_case_name = Column(String(500), default="")
    failure_type   = Column(String(100), default="unknown")
    root_cause     = Column(Text,        nullable=True)
    suggestion     = Column(Text,        nullable=True)
    confidence     = Column(Float,       default=0.0)
    is_flaky       = Column(Boolean,     default=False)
    flaky_reason   = Column(Text,        nullable=True)
    created_at     = Column(DateTime,    default=datetime.utcnow)

    run = relationship("TestRun", back_populates="ai_records")


# 数据库客户端

class DBClient:
    _engine          = None
    _session_factory = None

    # 初始化

    @classmethod
    async def init(cls):
        """应用启动时调用，创建引擎和所有表"""
        os.makedirs("data", exist_ok=True)

        # MySQL需要aiomysql，SQLite需要aiosqlite
        cls._engine = create_async_engine(
            DB_URL,
            echo=False,
            pool_pre_ping=True,       # 自动检测断线重连
            pool_recycle=3600,        # 连接复用 1 小时后回收（MySQL 需要）
        )
        cls._session_factory = async_sessionmaker(
            cls._engine,
            expire_on_commit=False,
            class_=AsyncSession,
        )
        async with cls._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    @classmethod
    def get_session(cls) -> AsyncSession:
        """获取异步 Session（配合 async with 使用）"""
        if cls._session_factory is None:
            raise RuntimeError("DBClient 未初始化，请先调用 await DBClient.init()")
        return cls._session_factory()

    # TestRun 操作

    @classmethod
    async def create_run(
        cls,
        name:    str,
        module:  str = "all",
        env:     str = "dev",
        trigger: str = "manual",
    ) -> TestRun:
        """创建一条新的执行记录，返回带id的对象"""
        async with cls.get_session() as session:
            run = TestRun(name=name, module=module, env=env, trigger=trigger)
            session.add(run)
            await session.commit()
            await session.refresh(run)
            return run

    @classmethod
    async def finish_run(
        cls,
        run_id:  int,
        status:  str,
        total:   int,
        passed:  int,
        failed:  int,
        skipped: int,
    ):
        """测试结束后更新执行记录的状态和统计数字"""
        async with cls.get_session() as session:
            run = await session.get(TestRun, run_id)
            if not run:
                return
            run.status   = status
            run.end_time = datetime.utcnow()
            run.total    = total
            run.passed   = passed
            run.failed   = failed
            run.skipped  = skipped
            if run.start_time:
                run.duration = (run.end_time - run.start_time).total_seconds()
            await session.commit()

    @classmethod
    async def save_ai_summary(cls, run_id: int, summary_json: str):
        """将AI摘要JSON字符串缓存到test_runs.ai_summary"""
        async with cls.get_session() as session:
            run = await session.get(TestRun, run_id)
            if run:
                run.ai_summary = summary_json
                await session.commit()

    @classmethod
    async def get_recent_runs(cls, limit: int = 20) -> List[TestRun]:
        """按开始时间倒序获取最近的执行记录"""
        async with cls.get_session() as session:
            result = await session.execute(
                select(TestRun)
                .order_by(TestRun.start_time.desc())
                .limit(limit)
            )
            return list(result.scalars().all())

    @classmethod
    async def get_summary(cls) -> dict:
        """汇总所有已完成执行的通过/失败/跳过数量"""
        async with cls.get_session() as session:
            result = await session.execute(
                select(
                    func.sum(TestRun.total).label("total"),
                    func.sum(TestRun.passed).label("passed"),
                    func.sum(TestRun.failed).label("failed"),
                    func.sum(TestRun.skipped).label("skipped"),
                ).where(TestRun.status.in_(["success", "failed"]))
            )
            row = result.first()
            return {
                "total":   row.total   or 0,
                "passed":  row.passed  or 0,
                "failed":  row.failed  or 0,
                "skipped": row.skipped or 0,
            }

    @classmethod
    async def get_trend(cls, days: int = 10) -> list:
        """获取最近 N 次执行的通过率趋势数据（供前端折线图使用）"""
        async with cls.get_session() as session:
            result = await session.execute(
                select(TestRun)
                .where(TestRun.status.in_(["success", "failed"]))
                .order_by(TestRun.start_time.desc())
                .limit(days)
            )
            runs = list(result.scalars().all())
            trend = []
            for run in reversed(runs):
                pass_rate = round(run.passed / run.total * 100, 1) if run.total else 0
                trend.append({
                    "date":     run.start_time.strftime("%m-%d %H:%M") if run.start_time else "",
                    "passRate": pass_rate,
                    "total":    run.total,
                    "passed":   run.passed,
                    "failed":   run.failed,
                })
            return trend

    # TestCase 操作

    @classmethod
    async def save_cases(cls, run_id: int, cases: List[dict]):
        """批量写入用例执行结果"""
        if not cases:
            return
        async with cls.get_session() as session:
            for c in cases:
                case = TestCase(
                    run_id          = run_id,
                    name            = c.get("name", ""),
                    module          = c.get("module", ""),
                    status          = c.get("status", "unknown"),
                    duration        = c.get("duration", 0.0),
                    error_message   = c.get("error_message"),
                    screenshot_path = c.get("screenshot_path"),
                )
                session.add(case)
            await session.commit()

    @classmethod
    async def get_failed_cases(cls, run_id: int) -> List[TestCase]:
        """获取指定运行中所有状态为 failed 的用例"""
        async with cls.get_session() as session:
            result = await session.execute(
                select(TestCase)
                .where(
                    TestCase.run_id == run_id,
                    TestCase.status == "failed",
                )
                .order_by(TestCase.id)
            )
            return list(result.scalars().all())

    @classmethod
    async def update_case_ai_analysis(cls, case_id: int, ai_json: str):
        """将 AI 分析结果 JSON 写回到对应的 test_cases 记录"""
        async with cls.get_session() as session:
            case = await session.get(TestCase, case_id)
            if case:
                case.ai_analysis = ai_json
                await session.commit()

    # AIAnalysisRecord 操作

    @classmethod
    async def save_ai_analysis(cls, data: dict) -> AIAnalysisRecord:
        """保存一条AI分析记录"""
        async with cls.get_session() as session:
            record = AIAnalysisRecord(
                run_id         = data.get("run_id"),
                case_id        = data.get("case_id"),
                test_case_name = data.get("test_case_name", ""),
                failure_type   = data.get("failure_type", "unknown"),
                root_cause     = data.get("root_cause", ""),
                suggestion     = data.get("suggestion", ""),
                confidence     = data.get("confidence", 0.0),
                is_flaky       = data.get("is_flaky", False),
                flaky_reason   = data.get("flaky_reason", ""),
            )
            session.add(record)
            await session.commit()
            await session.refresh(record)
            return record

    @classmethod
    async def get_ai_history(cls, run_id: int) -> List[AIAnalysisRecord]:
        """获取某次运行的所有AI分析记录，按时间倒序"""
        async with cls.get_session() as session:
            result = await session.execute(
                select(AIAnalysisRecord)
                .where(AIAnalysisRecord.run_id == run_id)
                .order_by(AIAnalysisRecord.created_at.desc())
            )
            return list(result.scalars().all())