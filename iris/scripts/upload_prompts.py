"""
一键迁移：把 iris_config.yaml 里的 4 个 prompt 上传到 Langfuse 平台。

运行方式:
    cd iris
    python -m scripts.upload_prompts

运行完之后:
    1. 打开 https://cloud.langfuse.com → 左侧 Prompts 页面
    2. 你会看到 4 个 prompt，每个都有 version 1，标签 [production]
    3. 以后你直接在网页上改 prompt → 保存 → 新版本自动创建
    4. 确认效果好 → 给新版本打 production 标签 → 线上自动生效
"""

import sys
from pathlib import Path

# 让 import 能找到 iris 包
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from langfuse import get_client
from core.config import load_config


def main():
    cfg = load_config()
    langfuse = get_client()

    # ── 要上传的 prompt 清单 ──
    # name: Langfuse 上的名字（代码里用这个名字来拉取）
    # prompt: 当前 yaml 里的 prompt 内容
    # description: 在 Langfuse UI 上显示的说明
    prompts = [
        {
            "name": "iris-ticker-extraction",
            "prompt": cfg.get("prompts", {}).get("ticker_extraction", ""),
            "description": "从用户输入中提取股票代码 (ticker)，用于加载历史分析上下文。返回 JSON。",
        },
        {
            "name": "iris-metadata-extraction",
            "prompt": cfg.get("prompts", {}).get("metadata_extraction", ""),
            "description": "从分析报告中提取 ticker / recommendation / confidence，供前端渲染。",
        },
        {
            "name": "iris-compaction-summary",
            "prompt": cfg.get("compaction", {}).get("summary_prompt", ""),
            "description": "上下文压缩时使用的摘要指令，告诉 LLM 保留什么、丢弃什么。",
        },
        {
            "name": "iris-memory-flush",
            "prompt": cfg.get("compaction", {}).get("memory_flush", {}).get("prompt", ""),
            "description": "压缩前的记忆冲刷指令，让 LLM 把关键发现存入 DB。",
        },
    ]

    for p in prompts:
        if not p["prompt"] or not p["prompt"].strip():
            print(f"  SKIP {p['name']} (prompt is empty)")
            continue

        try:
            langfuse.create_prompt(
                name=p["name"],
                type="text",
                prompt=p["prompt"].strip(),
                labels=["production"],  # 第一个版本直接标记为 production
                config={"description": p["description"]},
            )
            print(f"  OK   {p['name']}")
        except Exception as e:
            # 如果已经存在同名 prompt，create_prompt 会创建新版本
            # 但如果内容一样可能报错，这里兜底
            print(f"  WARN {p['name']}: {e}")

    langfuse.flush()
    print("\nDone! Go to https://cloud.langfuse.com → Prompts to see them.")


if __name__ == "__main__":
    main()
