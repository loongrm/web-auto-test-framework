"""
失败案例向量知识库（基于 ChromaDB）

职责：
  - 把每条失败案例及其分析结果向量化后持久化存储
  - 提供"按当前失败检索历史相似案例"的能力
  - 形成知识积累闭环：每次新分析都回写，库越用越聪明

文档结构设计：
  - document（被编码的文本）：失败的语义描述，决定检索召回质量
  - metadata：结构化字段，支持按类型/状态过滤 + 携带历史解决方案
"""

import os
from typing import List, Dict, Optional
from datetime import datetime
from core.log_factory import log
from ai.rag.embedding import EmbeddingEncoder


class FailureKnowledgeBase:
    """失败案例知识库。"""

    COLLECTION_NAME = "failure_cases"

    def __init__(self, persist_dir: str = "data/chroma", encoder: Optional[EmbeddingEncoder] = None):
        self._persist_dir = persist_dir
        self._encoder = encoder or EmbeddingEncoder()
        self._client = None
        self._collection = None
        self._init_store()

    def _init_store(self):
        """初始化 ChromaDB 持久化客户端与集合。"""
        if not self._encoder.available:
            log.warning("embedding 不可用，知识库以禁用状态运行")
            return
        try:
            import chromadb
            os.makedirs(self._persist_dir, exist_ok=True)
            self._client = chromadb.PersistentClient(path=self._persist_dir)
            # 用余弦相似度（与归一化向量配合）
            self._collection = self._client.get_or_create_collection(
                name=self.COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
            log.info(f"知识库已就绪 | 现有案例数: {self._collection.count()}")
        except Exception as e:
            log.error(f"知识库初始化失败: {e}")
            self._collection = None

    @property
    def available(self) -> bool:
        return self._collection is not None

    @staticmethod
    def _build_document(failure_type: str, error_message: str, test_name: str) -> str:
        """构造被编码的语义文本。

        把最能表征"这是什么失败"的信息拼接起来。
        测试名 + 失败类型 + 错误信息三者结合，检索召回质量最好。
        """
        return (
            f"测试用例: {test_name}\n"
            f"失败类型: {failure_type}\n"
            f"错误信息: {error_message[:1000]}"  # 截断超长堆栈
        )

    def add_case(
        self,
        case_id: str,
        failure_type: str,
        error_message: str,
        test_name: str,
        root_cause: str = "",
        suggestion: str = "",
    ) -> bool:
        """新增一条失败案例到知识库。

        root_cause / suggestion 是这次分析得出的解决方案，
        作为 metadata 存储 —— 下次检索到这条案例时，可以把
        当时的解决方案一并喂给模型，这是 RAG 增益的核心来源。
        """
        if not self.available:
            return False
        try:
            doc = self._build_document(failure_type, error_message, test_name)
            vector = self._encoder.encode_one(doc)
            self._collection.upsert(
                ids=[case_id],
                embeddings=[vector],
                documents=[doc],
                metadatas=[{
                    "failure_type": failure_type,
                    "test_name":    test_name,
                    "root_cause":   root_cause[:500],
                    "suggestion":   suggestion[:500],
                    "created_at":   datetime.utcnow().isoformat(),
                }],
            )
            log.debug(f"案例已入库: {case_id}")
            return True
        except Exception as e:
            log.warning(f"案例入库失败 {case_id}: {e}")
            return False

    def search_similar(
        self,
        failure_type: str,
        error_message: str,
        test_name: str,
        top_k: int = 3,
        min_score: float = 0.5,
    ) -> List[Dict]:
        """检索与当前失败最相似的历史案例。

        Args:
            top_k: 返回最多几条
            min_score: 相似度下限，低于此值的不返回（避免牵强附会的检索结果污染 prompt）

        Returns:
            相似案例列表，每项含 id / score / root_cause / suggestion 等
        """
        if not self.available or self._collection.count() == 0:
            return []
        try:
            query_doc = self._build_document(failure_type, error_message, test_name)
            query_vec = self._encoder.encode_one(query_doc)
            n = min(top_k, self._collection.count())
            results = self._collection.query(
                query_embeddings=[query_vec],
                n_results=n,
            )

            cases = []
            ids       = results.get("ids", [[]])[0]
            distances = results.get("distances", [[]])[0]
            metadatas = results.get("metadatas", [[]])[0]

            for cid, dist, meta in zip(ids, distances, metadatas):
                # ChromaDB cosine 返回的是距离，相似度 = 1 - 距离
                score = 1.0 - dist
                if score < min_score:
                    continue
                cases.append({
                    "id":           cid,
                    "score":        round(score, 3),
                    "failure_type": meta.get("failure_type", ""),
                    "test_name":    meta.get("test_name", ""),
                    "root_cause":   meta.get("root_cause", ""),
                    "suggestion":   meta.get("suggestion", ""),
                })
            log.debug(f"检索到 {len(cases)} 条相似案例（top_k={top_k}）")
            return cases
        except Exception as e:
            log.warning(f"相似案例检索失败: {e}")
            return []

    def stats(self) -> dict:
        """知识库统计信息，可用于监控页面展示。"""
        if not self.available:
            return {"available": False, "count": 0}
        return {
            "available": True,
            "count": self._collection.count(),
            "embedding_backend": self._encoder.backend,
            "dimension": self._encoder.dimension,
        }
