"""
SQLAlchemy 异步数据库客户端
用于持久化测试执行结果
"""
import asyncio
from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy import select, func
import os


DB_URL = os.getenv("DB_URL", "sqlite+aiosqlite:///./data/test_results.db")


class Base(DeclarativeBase):
    pass


class TestRun(Base):
    __tablename__ = "test_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    module = Column(String(50), default="all")
    env = Column(String(20), default="dev")
    status = Column(String(20), default="running")  # running | success | failed
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    duration = Column(Float, default=0.0)
    total = Column(Integer, default=0)
    passed = Column(Integer, default=0)
    failed = Column(Integer, default=0)
    skipped = Column(Integer, default=0)
    trigger = Column(String(50), default="manual")  # manual | schedule | webhook
    git_commit = Column(String(100), nullable=True)

    cases = relationship("TestCase", back_populates="run", cascade="all, delete-orphan")


class TestCase(Base):
    __tablename__ = "test_cases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(Integer, ForeignKey("test_runs.id"), nullable=False)
    name = Column(String(500), nullable=False)
    module = Column(String(100), default="")
    status = Column(String(20), nullable=False)   # passed | failed | skipped
    duration = Column(Float, default=0.0)
    error_message = Column(Text, nullable=True)
    screenshot_path = Column(String(500), nullable=True)
    ai_analysis = Column(Text, nullable=True)

    run = relationship("TestRun", back_populates="cases")


class DBClient:
    _engine = None
    _session_factory = None

    @classmethod
    async def init(cls):
        import os
        os.makedirs("data", exist_ok=True)
        cls._engine = create_async_engine(DB_URL, echo=False)
        cls._session_factory = async_sessionmaker(cls._engine, expire_on_commit=False)
        async with cls._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    @classmethod
    def get_session(cls) -> AsyncSession:
        return cls._session_factory()

    @classmethod
    async def create_run(cls, name: str, module: str = "all", env: str = "dev", trigger: str = "manual") -> TestRun:
        async with cls.get_session() as session:
            run = TestRun(name=name, module=module, env=env, trigger=trigger)
            session.add(run)
            await session.commit()
            await session.refresh(run)
            return run

    @classmethod
    async def finish_run(cls, run_id: int, status: str, total: int, passed: int, failed: int, skipped: int):
        async with cls.get_session() as session:
            run = await session.get(TestRun, run_id)
            if run:
                run.status = status
                run.end_time = datetime.utcnow()
                run.total = total
                run.passed = passed
                run.failed = failed
                run.skipped = skipped
                if run.start_time:
                    run.duration = (run.end_time - run.start_time).total_seconds()
                await session.commit()

    @classmethod
    async def get_summary(cls) -> dict:
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
                "total": row.total or 0,
                "passed": row.passed or 0,
                "failed": row.failed or 0,
                "skipped": row.skipped or 0,
            }

    @classmethod
    async def get_recent_runs(cls, limit: int = 20) -> List[TestRun]:
        async with cls.get_session() as session:
            result = await session.execute(
                select(TestRun).order_by(TestRun.start_time.desc()).limit(limit)
            )
            return result.scalars().all()

    @classmethod
    async def get_trend(cls, days: int = 7) -> list:
        """获取最近N次执行的通过率趋势"""
        async with cls.get_session() as session:
            result = await session.execute(
                select(TestRun)
                .where(TestRun.status.in_(["success", "failed"]))
                .order_by(TestRun.start_time.desc())
                .limit(days)
            )
            runs = result.scalars().all()
            trend = []
            for run in reversed(runs):
                pass_rate = round(run.passed / run.total * 100, 1) if run.total else 0
                trend.append({
                    "date": run.start_time.strftime("%m-%d %H:%M") if run.start_time else "",
                    "passRate": pass_rate,
                    "total": run.total,
                    "passed": run.passed,
                    "failed": run.failed,
                })
            return trend