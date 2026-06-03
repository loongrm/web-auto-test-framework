"""
AI 分析的结构化输出 Schema

设计目的：
  - 用 Pydantic 强约束 LLM 输出，杜绝"返回一段自由文本然后自己 parse"的脆弱做法
  - 这些 schema 同时用于两个地方：
      1. 转换为 OpenAI function calling 的 JSON Schema（约束模型输出）
      2. 接收模型输出后做二次校验（双保险）
  - 枚举类型把"失败分类"这种开放问题收敛成有限集合，便于后续统计和检索
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class FailureType(str, Enum):
    """失败类型枚举。

    收敛为有限集合的好处：
      - 模型不会自由发挥造出五花八门的分类名
      - 可以基于类型做聚合统计、趋势分析
      - 检索时可按类型过滤，提升相关性
    """
    ELEMENT_NOT_FOUND = "element_not_found"   # 元素定位失败
    TIMEOUT           = "timeout"             # 等待/加载超时
    ASSERTION_FAILED  = "assertion_failed"    # 断言不通过（疑似真实缺陷）
    NETWORK_ERROR     = "network_error"       # 网络/接口错误
    AUTH_ERROR        = "auth_error"          # 认证/权限问题
    DATA_ERROR        = "data_error"          # 测试数据问题
    ENV_ERROR         = "env_error"           # 环境配置问题（如 headless）
    UNKNOWN           = "unknown"             # 无法归类


class RiskLevel(str, Enum):
    HIGH    = "high"
    MEDIUM  = "medium"
    LOW     = "low"
    UNKNOWN = "unknown"


class FailureAnalysis(BaseModel):
    """单条失败的根因分析结果。

    这是 LLM 必须返回的结构。每个字段的 description 会被注入到
    function calling 的 schema 里，相当于给模型的"字段级提示"。
    """
    failure_type: FailureType = Field(
        description="失败类型，必须从给定枚举中选择最匹配的一项",
        default=FailureType.UNKNOWN,   # 加默认值：模型漏填时归为未分类
    )
    root_cause: str = Field(
        description="根本原因的简明描述，1-3句话，聚焦技术本质而非现象",
        min_length=5,
        max_length=500,
    )
    suggestion: str = Field(
        description="具体可操作的修复建议，给出明确的代码或配置改动方向",
        min_length=5,
        max_length=500,
    )
    confidence: float = Field(
        description="对本次分析的置信度，0.0-1.0。证据充分则高，靠猜则低",
        ge=0.0,
        le=1.0,
        default=0.5,   # 加默认值：小模型偶尔漏填此字段时，用 0.5 兜底而非校验失败
    )
    is_flaky: bool = Field(
        description="是否疑似偶发性失败（flaky），即非稳定复现、可能与时序/环境有关",
        default=False,
    )
    referenced_cases: List[str] = Field(
        description="本次分析参考了哪些历史相似案例的ID（来自检索结果），没有则空列表",
        default_factory=list,
    )

    @field_validator("failure_type", mode="before")
    @classmethod
    def coerce_failure_type(cls, v):
        """宽容处理失败类型：小模型可能返回枚举外的自创值，归到 unknown 而非报错。"""
        if isinstance(v, FailureType):
            return v
        if isinstance(v, str):
            v_clean = v.strip().lower()
            # 精确匹配枚举值
            valid = {e.value for e in FailureType}
            if v_clean in valid:
                return v_clean
            # 模糊匹配：包含关键词就归类
            if "timeout" in v_clean:           return FailureType.TIMEOUT
            if "element" in v_clean or "locator" in v_clean: return FailureType.ELEMENT_NOT_FOUND
            if "assert" in v_clean:            return FailureType.ASSERTION_FAILED
            if "network" in v_clean:           return FailureType.NETWORK_ERROR
            if "auth" in v_clean:              return FailureType.AUTH_ERROR
            if "env" in v_clean:               return FailureType.ENV_ERROR
        return FailureType.UNKNOWN

    @field_validator("root_cause", "suggestion")
    @classmethod
    def not_placeholder(cls, v: str) -> str:
        """拦截模型偷懒返回的占位符，并兜底空值。"""
        if not v or not v.strip():
            return "（模型未提供，建议人工补充）"
        placeholders = {"n/a", "none", "无", "未知", "暂无", "string"}
        if v.strip().lower() in placeholders:
            return "（模型未提供有效内容，建议人工排查）"
        return v.strip()


class RunSummary(BaseModel):
    """整次测试执行的 AI 摘要。"""
    summary: str = Field(
        description="对本次执行的总体评价，2-4句话",
        min_length=10,
        max_length=800,
    )
    risk_level: RiskLevel = Field(description="当前发布风险等级")
    key_issues: List[str] = Field(
        description="按重要性排序的关键问题列表，每项一句话",
        default_factory=list,
        max_length=10,
    )
    recommendations: List[str] = Field(
        description="改进建议列表，每项一句话",
        default_factory=list,
        max_length=10,
    )


def pydantic_to_openai_tool(model: type[BaseModel], name: str, description: str) -> dict:
    """把 Pydantic 模型转换为 OpenAI function calling 的 tool 定义。

    这是连接"Pydantic schema"和"function calling 强约束"的桥梁：
    模型的 JSON Schema 直接作为 function 的 parameters，
    OpenAI 会保证返回的 arguments 符合这个 schema。
    """
    schema = model.model_json_schema()
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": schema,
        },
    }
