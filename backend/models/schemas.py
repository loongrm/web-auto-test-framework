from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class RunRequest(BaseModel):
    module:  str = Field(default="all")
    markers: Optional[str] = None
    env:     str = Field(default="dev")
    trigger: str = Field(default="manual")


class RunResponse(BaseModel):
    task_id: str
    run_id:  Optional[int] = None
    status:  str
    message: str


class TaskStatus(BaseModel):
    task_id:    str
    status:     str
    returncode: Optional[int] = None
    stdout:     Optional[str] = None
    stderr:     Optional[str] = None
    run_id:     Optional[int] = None
    passed:     Optional[int] = None
    failed:     Optional[int] = None
    total:      Optional[int] = None


class TestRunSummary(BaseModel):
    id:         int
    name:       str
    module:     str
    env:        str
    status:     str
    start_time: Optional[datetime]
    end_time:   Optional[datetime]
    duration:   float
    total:      int
    passed:     int
    failed:     int
    skipped:    int
    pass_rate:  float

    @classmethod
    def from_db(cls, run) -> "TestRunSummary":
        total  = run.total  or 0
        passed = run.passed or 0
        return cls(
            id=run.id, name=run.name,
            module=run.module or "all", env=run.env or "dev",
            status=run.status,
            start_time=run.start_time, end_time=run.end_time,
            duration=run.duration or 0.0,
            total=total, passed=passed,
            failed=run.failed or 0, skipped=run.skipped or 0,
            pass_rate=round(passed / total * 100, 1) if total else 0.0,
        )


class SummaryStats(BaseModel):
    total:     int
    passed:    int
    failed:    int
    skipped:   int
    pass_rate: float


class DashboardData(BaseModel):
    stats:       SummaryStats
    trend:       list
    recent_runs: List[TestRunSummary]


class AnalyzeFailureRequest(BaseModel):
    error_log:      str
    test_code:      Optional[str] = None
    test_case_name: Optional[str] = ""
    run_id:         Optional[int] = None
    case_id:        Optional[int] = None


class GenerateCasesRequest(BaseModel):
    user_story: str
    case_type:  str = "ui"


class HealLocatorRequest(BaseModel):
    broken_selector:  str
    page_html:        str
    element_purpose:  Optional[str] = ""