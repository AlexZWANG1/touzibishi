"""
Prompt Evaluation — 用 Langfuse Dataset 跑 A/B 测试。

这个脚本做的事情:
  1. 在 Langfuse 上创建测试数据集 (只在第一次运行时创建)
  2. 用当前 production prompt 跑一遍所有测试用例
  3. 对比 LLM 输出和期望输出，计算 accuracy
  4. 结果自动上传到 Langfuse → 在 UI 上看 Experiment 对比

运行方式:
    cd iris
    python -m scripts.eval_prompts

    # 指定要测试的 prompt label (比如测试 staging 版本):
    python -m scripts.eval_prompts --label staging

    # 只跑 ticker 提取的测试:
    python -m scripts.eval_prompts --suite ticker

你可以在 Langfuse 网页上:
  1. 改 prompt → 保存为新版本 → 打 staging 标签
  2. 跑 python -m scripts.eval_prompts --label staging
  3. 对比 staging vs production 的 accuracy
  4. 效果好 → 在 Langfuse 上把 staging 改成 production
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from langfuse import get_client, Evaluation
from langfuse.openai import OpenAI


# ── 测试数据 ──────────────────────────────────────────────────
# input: 用户输入
# expected_output: 期望 LLM 返回的 JSON

TICKER_EXTRACTION_CASES = [
    # 明确的 ticker
    {"input": "分析 NVDA 在 AI 基础设施赛道的投资机会", "expected_output": {"ticker": "NVDA"}},
    {"input": "帮我看看 META 的财报", "expected_output": {"ticker": "META"}},
    {"input": "AAPL 最近的估值合理吗", "expected_output": {"ticker": "AAPL"}},
    {"input": "analyze MSFT cloud business", "expected_output": {"ticker": "MSFT"}},
    {"input": "600519.SS 贵州茅台值得买吗", "expected_output": {"ticker": "600519.SS"}},
    # 不是 ticker — 应该返回 null
    {"input": "分析 AI Agent 产业链", "expected_output": {"ticker": None}},
    {"input": "EV/EBITDA 是什么意思", "expected_output": {"ticker": None}},
    {"input": "宏观经济对 GDP 的影响", "expected_output": {"ticker": None}},
    {"input": "你好，请问怎么用", "expected_output": {"ticker": None}},
    {"input": "对比一下半导体行业的几家公司", "expected_output": {"ticker": None}},
    # 容易误判的边界 case
    {"input": "AI 这个赛道未来怎么样", "expected_output": {"ticker": None}},  # AI 是 C3.ai 的代码，但这里是行业
    {"input": "分析一下 TSLA 的 EV 业务", "expected_output": {"ticker": "TSLA"}},  # EV=电动车不是 ticker
]

METADATA_EXTRACTION_CASES = [
    {
        "input": {
            "query": "分析 NVDA",
            "excerpt": "NVIDIA 当前价格 $118，DCF 公允价值 $155，安全边际 31%。推荐 BUY，置信度 high。"
        },
        "expected_output": {"ticker": "NVDA", "recommendation": "BUY", "confidence": "high"},
    },
    {
        "input": {
            "query": "看看 AAPL",
            "excerpt": "Apple 当前估值略高于公允价值，建议 HOLD 观望，等待更好的入场点。置信度 medium。"
        },
        "expected_output": {"ticker": "AAPL", "recommendation": "HOLD", "confidence": "medium"},
    },
    {
        "input": {
            "query": "分析 AI Agent 产业链",
            "excerpt": "AI Agent 基础设施赛道正在快速发展，主要玩家包括 LangChain、CrewAI 等。"
        },
        "expected_output": {"ticker": None, "recommendation": None, "confidence": None},
    },
    {
        "input": {
            "query": "BABA 还能持有吗",
            "excerpt": "阿里云增速放缓至 7%，原始论点（监管正常化 + 云业务重新加速）已失效。建议 SELL，置信度 high。"
        },
        "expected_output": {"ticker": "BABA", "recommendation": "SELL", "confidence": "high"},
    },
]


# ── 评估函数 ──────────────────────────────────────────────────

def ticker_accuracy(*, input, output, expected_output, **kwargs) -> Evaluation:
    """对比 ticker 提取结果是否正确。"""
    try:
        result = json.loads(output) if isinstance(output, str) else output
        expected = expected_output if isinstance(expected_output, dict) else json.loads(expected_output)

        got = result.get("ticker")
        want = expected.get("ticker")

        # 统一: None 和 null 和 "" 都算 null
        got = got if got else None
        want = want if want else None

        if got is not None:
            got = got.upper()
        if want is not None:
            want = want.upper()

        correct = (got == want)
        comment = f"got={got}, want={want}"
        return Evaluation(name="ticker_accuracy", value=1.0 if correct else 0.0, comment=comment)
    except Exception as e:
        return Evaluation(name="ticker_accuracy", value=0.0, comment=f"parse error: {e}")


def metadata_accuracy(*, input, output, expected_output, **kwargs) -> Evaluation:
    """对比 metadata 提取结果 (ticker + recommendation + confidence)。"""
    try:
        result = json.loads(output) if isinstance(output, str) else output
        expected = expected_output if isinstance(expected_output, dict) else json.loads(expected_output)

        score = 0.0
        total = 3  # ticker, recommendation, confidence
        details = []

        for key in ["ticker", "recommendation", "confidence"]:
            got = result.get(key) or None
            want = expected.get(key) or None
            if got and isinstance(got, str):
                got = got.upper()
            if want and isinstance(want, str):
                want = want.upper()
            match = (got == want)
            if match:
                score += 1
            details.append(f"{key}: got={got} want={want} {'OK' if match else 'MISS'}")

        return Evaluation(
            name="metadata_accuracy",
            value=score / total,
            comment="; ".join(details),
        )
    except Exception as e:
        return Evaluation(name="metadata_accuracy", value=0.0, comment=f"parse error: {e}")


def avg_accuracy(*, item_results, **kwargs) -> Evaluation:
    """Run-level: 计算整个 dataset 的平均准确率。"""
    values = []
    for r in item_results:
        for ev in r.evaluations:
            if "accuracy" in ev.name:
                values.append(ev.value)
    if not values:
        return Evaluation(name="avg_accuracy", value=None)
    avg = sum(values) / len(values)
    return Evaluation(name="avg_accuracy", value=avg, comment=f"{avg:.1%} ({len(values)} items)")


# ── Task 函数 ──────────────────────────────────────────────────

def make_ticker_task(prompt_text: str):
    """创建 ticker 提取的 task 函数。"""
    model = os.getenv("METADATA_MODEL") or "gpt-5.4-mini"

    def task(*, item, **kwargs):
        user_input = item["input"] if isinstance(item, dict) else item.input
        client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL"),
        )
        response = client.chat.completions.create(
            model=model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": prompt_text},
                {"role": "user", "content": str(user_input)[:500]},
            ],
        )
        return response.choices[0].message.content

    return task


def make_metadata_task(prompt_text: str):
    """创建 metadata 提取的 task 函数。"""
    model = os.getenv("METADATA_MODEL") or "gpt-5.4-mini"

    def task(*, item, **kwargs):
        item_input = item["input"] if isinstance(item, dict) else item.input
        if isinstance(item_input, str):
            item_input = json.loads(item_input)
        query = item_input.get("query", "")
        excerpt = item_input.get("excerpt", "")

        client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL"),
        )
        response = client.chat.completions.create(
            model=model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": prompt_text},
                {"role": "user", "content": f"Query: {query}\n\nAnalysis excerpt:\n{excerpt}"},
            ],
        )
        return response.choices[0].message.content

    return task


# ── 主流程 ──────────────────────────────────────────────────

def run_ticker_eval(langfuse, label: str):
    """跑 ticker 提取评估。"""
    print(f"\n{'='*60}")
    print(f"  TICKER EXTRACTION EVAL (prompt label: {label})")
    print(f"{'='*60}")

    # 获取 prompt
    try:
        prompt_obj = langfuse.get_prompt("iris-ticker-extraction", label=label, type="text")
        prompt_text = prompt_obj.prompt
        print(f"  Prompt: iris-ticker-extraction (version {prompt_obj.version})")
    except Exception as e:
        print(f"  FAIL: Cannot fetch prompt 'iris-ticker-extraction' with label '{label}': {e}")
        print(f"  Hint: Run 'python -m scripts.upload_prompts' first to create prompts.")
        return

    # 跑 experiment
    result = langfuse.run_experiment(
        name="iris-ticker-extraction",
        run_name=f"ticker-{label}-v{prompt_obj.version}",
        description=f"Evaluate iris-ticker-extraction prompt (label={label}, version={prompt_obj.version})",
        data=TICKER_EXTRACTION_CASES,
        task=make_ticker_task(prompt_text),
        evaluators=[ticker_accuracy],
        run_evaluators=[avg_accuracy],
    )

    print(result.format())


def run_metadata_eval(langfuse, label: str):
    """跑 metadata 提取评估。"""
    print(f"\n{'='*60}")
    print(f"  METADATA EXTRACTION EVAL (prompt label: {label})")
    print(f"{'='*60}")

    try:
        prompt_obj = langfuse.get_prompt("iris-metadata-extraction", label=label, type="text")
        prompt_text = prompt_obj.prompt
        print(f"  Prompt: iris-metadata-extraction (version {prompt_obj.version})")
    except Exception as e:
        print(f"  FAIL: Cannot fetch prompt 'iris-metadata-extraction' with label '{label}': {e}")
        print(f"  Hint: Run 'python -m scripts.upload_prompts' first to create prompts.")
        return

    result = langfuse.run_experiment(
        name="iris-metadata-extraction",
        run_name=f"metadata-{label}-v{prompt_obj.version}",
        description=f"Evaluate iris-metadata-extraction prompt (label={label}, version={prompt_obj.version})",
        data=METADATA_EXTRACTION_CASES,
        task=make_metadata_task(prompt_text),
        evaluators=[metadata_accuracy],
        run_evaluators=[avg_accuracy],
    )

    print(result.format())


def main():
    parser = argparse.ArgumentParser(description="IRIS Prompt Evaluation")
    parser.add_argument("--label", default="production",
                        help="Langfuse prompt label to test (default: production)")
    parser.add_argument("--suite", choices=["ticker", "metadata", "all"], default="all",
                        help="Which eval suite to run (default: all)")
    args = parser.parse_args()

    langfuse = get_client()

    if args.suite in ("ticker", "all"):
        run_ticker_eval(langfuse, args.label)

    if args.suite in ("metadata", "all"):
        run_metadata_eval(langfuse, args.label)

    langfuse.flush()
    print(f"\nDone! View results at https://cloud.langfuse.com → Datasets → Experiments")


if __name__ == "__main__":
    main()
