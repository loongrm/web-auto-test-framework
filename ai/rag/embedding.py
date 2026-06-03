"""
Embedding 编码器

设计决策：
  采用"本地优先"策略 —— 默认用 sentence-transformers 本地模型编码，
  原因有三：
    1. 离线可用，不受 API 余额/网络影响（吸取了之前 key 余额为0的教训）
    2. 零边际成本，可以放心地把每条失败都向量化入库
    3. 检索这种"高频低价值"操作不该花钱在云端 API 上

  云端 embedding（OpenAI text-embedding-3-small）作为可选降级，
  仅在显式配置且本地模型不可用时启用。

模型选择：
  默认 bge-small-zh-v1.5，512维，中文语义检索效果好且体积小（~100MB）。
  错误日志里中英文混杂，这个模型对混合文本表现稳定。
"""

import os
from typing import List, Optional
from core.log_factory import log


class EmbeddingEncoder:
    """统一的 embedding 接口，屏蔽底层是本地还是云端。"""

    def __init__(self, model_name: str = "BAAI/bge-small-zh-v1.5"):
        self._model_name = model_name
        self._local_model = None
        self._openai_client = None
        self._backend: Optional[str] = None  # "local" | "openai" | None
        self._init_backend()

    def _init_backend(self):
        """初始化编码后端，本地优先。"""
        # 尝试加载本地模型
        try:
            from sentence_transformers import SentenceTransformer
            log.info(f"正在加载本地 embedding 模型: {self._model_name}")
            self._local_model = SentenceTransformer(self._model_name)
            self._backend = "local"
            log.info("本地 embedding 模型加载成功")
            return
        except Exception as e:
            log.warning(f"本地 embedding 模型加载失败，尝试云端降级: {e}")

        # 降级到云端
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            try:
                from openai import OpenAI
                self._openai_client = OpenAI(
                    api_key=api_key,
                    base_url=os.getenv("OPENAI_BASE_URL"),
                )
                self._backend = "openai"
                log.info("已降级到云端 embedding（text-embedding-3-small）")
                return
            except Exception as e:
                log.error(f"云端 embedding 初始化失败: {e}")

        log.error("embedding 后端不可用，RAG 检索将被禁用")
        self._backend = None

    @property
    def available(self) -> bool:
        return self._backend is not None

    @property
    def backend(self) -> Optional[str]:
        return self._backend

    @property
    def dimension(self) -> int:
        """向量维度，建库时需要。"""
        if self._backend == "local":
            # 兼容 sentence-transformers 新旧版本的方法名
            if hasattr(self._local_model, "get_embedding_dimension"):
                return self._local_model.get_embedding_dimension()
            return self._local_model.get_sentence_embedding_dimension()
        if self._backend == "openai":
            return 1536  # text-embedding-3-small
        return 0

    def encode(self, texts: List[str]) -> List[List[float]]:
        """把文本列表编码为向量列表。"""
        if not texts:
            return []

        if self._backend == "local":
            # normalize_embeddings=True：归一化后用内积等价于余弦相似度
            vectors = self._local_model.encode(
                texts, normalize_embeddings=True, show_progress_bar=False
            )
            return vectors.tolist()

        if self._backend == "openai":
            resp = self._openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=texts,
            )
            return [item.embedding for item in resp.data]

        raise RuntimeError("embedding 后端不可用")

    def encode_one(self, text: str) -> List[float]:
        """编码单条文本的便捷方法。"""
        return self.encode([text])[0]
