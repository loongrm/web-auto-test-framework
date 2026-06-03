"""
RAG 失败分析编排器

把整个 RAG 闭环串联起来，是上层（后端路由）调用的统一入口：

  检索 → 增强 → 生成 → 校验 → 回写
"""

from typing import List, Dict, Optional
from core.log_factory import log
from ai.rag.embedding import EmbeddingEncoder
from ai.rag.knowledge_base import FailureKnowledgeBase
from ai.llm.client import LLMClient
from ai.schemas.analysis import FailureAnalysis


class RAGFailureAnalyzer:
    """RAG 增强的失败分析器（单例使用）。"""

    def __init__(self):
        # 共享同一个 encoder，避免重复加载模型
        self._encoder = EmbeddingEncoder()
        self._kb = FailureKnowledgeBase(encoder=self._encoder)
        self._llm = LLMClient()
        log.info(
            f"RAG 分析器就绪 | LLM={'可用' if self._llm.available else '降级'} | "
            f"知识库={'可用' if self._kb.available else '禁用'} | "
            f"embedding={self._encoder.backend}"
        )

    @property
    def status(self) -> dict:
        """组件状态，供健康检查/监控页展示。"""
        return {
            "llm_available": self._llm.available,
            "kb_stats": self._kb.stats(),
        }

    def analyze(
        self,
        case_id: str,
        error_message: str,
        test_name: str,
        test_code: str = "",
        write_back: bool = True,
    ) -> Dict:
        """分析一条失败，返回结构化结果 + 检索元信息。

        Args:
            case_id: 用例唯一标识，作为知识库主键
            write_back: 是否把本次分析回写知识库（形成闭环）

        Returns:
            含分析结果、检索到的相似案例、各组件状态的字典
        """
        # ── 1. 检索历史相似案例 ──────────────────────────────────
        # 注意：检索用的 failure_type 此刻还不知道，先用 unknown 占位，
        #       主要靠 error_message 的语义做召回
        similar = self._kb.search_similar(
            failure_type="unknown",
            error_message=error_message,
            test_name=test_name,
            top_k=3,
        )

        # ── 2. 构造增强上下文 ────────────────────────────────────
        retrieved_context = self._format_retrieved(similar)

        # ── 3. LLM 生成（内含重试与降级）─────────────────────────
        analysis: FailureAnalysis = self._llm.analyze_failure(
            error_message=error_message,
            test_name=test_name,
            test_code=test_code,
            retrieved_context=retrieved_context,
        )

        # ── 4. 回写知识库（闭环）─────────────────────────────────
        if write_back and self._kb.available:
            self._kb.add_case(
                case_id=case_id,
                failure_type=analysis.failure_type.value,
                error_message=error_message,
                test_name=test_name,
                root_cause=analysis.root_cause,
                suggestion=analysis.suggestion,
            )

        # ── 5. 组装返回 ──────────────────────────────────────────
        return {
            "available": True,
            "analysis": analysis.model_dump(),
            "retrieved_cases": similar,
            "retrieval_used": len(similar) > 0,
            "llm_backend": self._llm.backend or "rule_fallback",
        }

    @staticmethod
    def _format_retrieved(cases: List[Dict]) -> str:
        """把检索结果格式化为注入 prompt 的文本。

        只在有解决方案的案例上拼接，空方案的案例对模型无增益。
        """
        if not cases:
            return ""
        lines = []
        for c in cases:
            if not c.get("root_cause"):
                continue
            lines.append(
                f"[案例 {c['id']}, 相似度 {c['score']}]\n"
                f"  失败类型: {c.get('failure_type', '')}\n"
                f"  当时根因: {c.get('root_cause', '')}\n"
                f"  当时建议: {c.get('suggestion', '')}"
            )
        return "\n\n".join(lines)
