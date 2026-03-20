"""Show thinking + timeline from a real analysis run, with proper encoding."""
import sqlite3, json, sys
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect("iris.db")
cur = conn.cursor()

# Get GOOGL run with rich thinking
cur.execute("SELECT id, ticker, thinking_text, reasoning_text, timeline_json FROM analysis_runs WHERE id='5b823a4484f84bc9'")
row = cur.fetchone()
run_id, ticker, thinking, reasoning, timeline_json = row

print(f"=== {ticker} (run: {run_id}) ===\n")

print("=" * 80)
print("AGENT 完整思考过程 (Thinking Blocks)")
print("=" * 80)
if thinking:
    blocks = thinking.split("\n---\n")
    for i, block in enumerate(blocks):
        print(f"\n--- Thinking Block #{i+1} ---")
        print(block.strip())
else:
    print("No thinking text")

print("\n" + "=" * 80)
print("AGENT 最终分析输出 (Reasoning)")
print("=" * 80)
print(reasoning if reasoning else "No reasoning")

print("\n" + "=" * 80)
print("完整 TIMELINE (每一步的执行顺序)")
print("=" * 80)
timeline = json.loads(timeline_json) if timeline_json else []
for i, entry in enumerate(timeline):
    tool = entry.get("tool", "?")
    status = entry.get("status", "?")
    if tool == "thinking":
        full = entry.get("fullText", entry.get("message", ""))
        first_line = full.strip().split("\n")[0][:100]
        print(f"\n[{i:>2}] 🧠 THINKING: {first_line}")
        print(f"     Full text ({len(full)} chars):")
        for line in full.strip().split("\n")[:6]:
            print(f"       {line}")
        if full.count("\n") > 6:
            print(f"       ... ({full.count(chr(10))} lines total)")
    else:
        args = entry.get("args", {})
        result = entry.get("result", {})

        # Format args
        if tool == "build_dcf":
            a = args.get("assumptions", {})
            segs = a.get("segments", [])
            seg_info = ", ".join(f"{s.get('name','?')}" for s in segs)
            args_str = f"wacc={a.get('wacc')} tg={a.get('terminal_growth')} segs=[{seg_info}]"
            if isinstance(result, dict) and "fair_value_per_share" in result:
                result_str = f"FV=${result['fair_value_per_share']} gap={result.get('gap_pct')}%"
            else:
                result_str = str(result)[:80]
        elif tool == "fmp_get_financials":
            args_str = f"{args.get('ticker','?')} {args.get('statement_type','?')}"
            result_str = "ok" if isinstance(result, dict) else str(result)[:60]
        elif tool == "get_comps":
            args_str = f"{args.get('ticker','?')} peers={args.get('peers',[])}"
            if isinstance(result, dict):
                med = result.get("median", {})
                result_str = f"median P/E={med.get('fwd_pe')} EV/EB={med.get('ev_ebitda')}"
            else:
                result_str = str(result)[:60]
        elif tool == "recall_memory":
            args_str = f"{args.get('company','?')} type={args.get('memory_type','?')}"
            result_str = "found" if isinstance(result, dict) and result.get("content") else "empty"
        elif tool == "save_memory":
            args_str = f"{args.get('company','?')}"
            result_str = "saved"
        elif tool == "yf_quote":
            args_str = f"{args.get('ticker','?')}"
            if isinstance(result, dict):
                result_str = f"price=${result.get('regularMarketPrice', result.get('price','?'))}"
            else:
                result_str = str(result)[:60]
        elif tool == "exa_search":
            args_str = args.get("query", "?")[:60]
            result_str = f"{len(result.get('results',[])) if isinstance(result, dict) else 0} results"
        elif tool == "web_fetch":
            args_str = args.get("url", "?")[:60]
            result_str = f"{len(str(result))} chars" if result else "empty"
        else:
            args_str = str(args)[:60]
            result_str = str(result)[:60]

        print(f"\n[{i:>2}] 🔧 {tool} ({status})")
        print(f"     Args: {args_str}")
        print(f"     Result: {result_str}")

# Also show one more run - AAPL
print("\n\n" + "=" * 80)
print("=" * 80)
cur.execute("SELECT id, ticker, thinking_text, reasoning_text FROM analysis_runs WHERE id='7fd1973fd9c344af'")
row2 = cur.fetchone()
if row2:
    run_id2, ticker2, thinking2, reasoning2 = row2
    print(f"\n=== {ticker2} (run: {run_id2}) ===")
    print("\n--- THINKING ---")
    if thinking2:
        blocks2 = thinking2.split("\n---\n")
        for i, block in enumerate(blocks2):
            print(f"\n  Block #{i+1}:")
            print(f"  {block.strip()[:300]}")
    print("\n--- REASONING (first 1500 chars) ---")
    print(reasoning2[:1500] if reasoning2 else "No reasoning")
