"""
RAG 失败分析系统 —— 独立演示脚本

这个 demo 不依赖测试平台的任何代码，可单独运行，用来验证 RAG 闭环：
  1. 知识库为空时分析（无检索增益，纯 LLM/规则）
  2. 积累几条案例后，相似失败能检索到历史方案
  3. LLM 不可用时（无 key），自动降级到规则引擎，依然有结果

运行前置：
    pip install chromadb sentence-transformers pydantic tenacity
    # LLM 部分可选，不配 OPENAI_API_KEY 也能跑（走规则降级）
    pip install openai
    export OPENAI_API_KEY=sk-xxx   # 可选

运行：
    python demo.py

首次运行会下载本地 embedding 模型（约100MB），需联网一次；
之后完全离线可用。国内慢的话可设置镜像：
    export HF_ENDPOINT=https://hf-mirror.com
"""

import os
import sys
import logging

# ── 用标准 logging 顶替项目的 core.log_factory，让 demo 独立可跑 ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("rag-demo")

# 把 core.log_factory.log 这个依赖在内存里"伪造"出来，
# 这样可以直接复用 ai/ 下的真实模块，无需改动它们的 import。
import types
fake = types.ModuleType("core.log_factory")
fake.log = log
sys.modules["core"] = types.ModuleType("core")
sys.modules["core.log_factory"] = fake


# ─────────────────────────────────────────────────────────────────────
# 下面直接导入你项目里的真实 RAG 模块
# （demo.py 放在项目根目录运行即可）
# ─────────────────────────────────────────────────────────────────────
from ai.rag.analyzer import RAGFailureAnalyzer


# ── 准备一批模拟失败案例 ──────────────────────────────────────────────
SAMPLE_FAILURES = [
    {
        "case_id": "demo_001",
        "test_name": "test_login_success[standard_user]",
        "error_message": (
            "playwright._impl._errors.TimeoutError: Locator.click: Timeout 30000ms exceeded.\n"
            "waiting for locator('#login-button') to be visible"
        ),
    },
    {
        "case_id": "demo_002",
        "test_name": "test_add_to_cart",
        "error_message": (
            "playwright._impl._errors.TimeoutError: Locator.click: Timeout 30000ms exceeded.\n"
            "waiting for locator('.add-to-cart-btn') to be visible"
        ),
    },
    {
        "case_id": "demo_003",
        "test_name": "test_user_api[get_user]",
        "error_message": "AssertionError: 状态码不匹配，期望 200 实际 401 Unauthorized",
    },
    {
        "case_id": "demo_004",
        "test_name": "test_checkout",
        "error_message": (
            "playwright._impl._errors.TargetClosedError: Page.goto: "
            "Target page, context or browser has been closed"
        ),
    },
]


def print_result(title: str, result: dict):
    """格式化打印分析结果。"""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print('='*70)
    a = result["analysis"]
    print(f"  失败类型   : {a['failure_type']}")
    print(f"  根本原因   : {a['root_cause']}")
    print(f"  修复建议   : {a['suggestion']}")
    print(f"  置信度     : {a['confidence']}")
    print(f"  疑似偶发   : {a['is_flaky']}")
    print(f"  分析来源   : {result['llm_backend']}  "
          f"(llm=真实模型 / rule_fallback=规则降级)")
    print(f"  是否用检索 : {result['retrieval_used']}")
    if result["retrieved_cases"]:
        print(f"  检索到的相似历史案例:")
        for c in result["retrieved_cases"]:
            print(f"     - {c['id']} (相似度 {c['score']}) "
                  f"类型={c['failure_type']}")
            if c.get("suggestion"):
                print(f"       历史建议: {c['suggestion']}")


def main():
    print("\n初始化 RAG 分析器（首次会加载 embedding 模型，请稍候）...")
    analyzer = RAGFailureAnalyzer()

    print(f"\n系统状态: {analyzer.status}")

    # ── 场景一：冷启动，知识库为空 ───────────────────────────────────
    print("\n\n########## 场景一：知识库为空，分析第一条超时失败 ##########")
    r1 = analyzer.analyze(**SAMPLE_FAILURES[0])
    print_result("demo_001（首次，无历史可检索）", r1)

    # ── 场景二：再灌入几条，形成知识积累 ─────────────────────────────
    print("\n\n########## 场景二：继续分析，知识库开始积累 ##########")
    analyzer.analyze(**SAMPLE_FAILURES[2])  # 401 案例入库
    analyzer.analyze(**SAMPLE_FAILURES[3])  # TargetClosed 案例入库

    # ── 场景三：分析一条与 demo_001 高度相似的超时失败 ───────────────
    print("\n\n########## 场景三：分析相似失败，检验 RAG 检索 ##########")
    print("（demo_002 和 demo_001 都是 click 超时，应能检索到 demo_001）")
    r3 = analyzer.analyze(**SAMPLE_FAILURES[1])
    print_result("demo_002（应检索到 demo_001 这条相似案例）", r3)

    # ── 总结 ─────────────────────────────────────────────────────────
    print(f"\n\n{'='*70}")
    print("  演示结束。最终知识库状态:")
    print(f"  {analyzer.status['kb_stats']}")
    print('='*70)
    print("\n要点观察：")
    print("  1. 若未配 OPENAI_API_KEY，所有分析来源应为 rule_fallback，")
    print("     但依然给出了合理的分类和建议 —— 这就是降级链路的价值。")
    print("  2. 场景三的 retrieval_used 应为 True，证明 RAG 检索生效。")
    print("  3. 知识库案例数随分析次数增长 —— 这就是知识积累闭环。\n")


if __name__ == "__main__":
    main()
