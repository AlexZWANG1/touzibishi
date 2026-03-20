"""Extract build_dcf assumptions from past analysis runs."""
import sqlite3, json, sys
sys.path.insert(0, ".")

conn = sqlite3.connect("iris.db")
cur = conn.cursor()
cur.execute("SELECT id, ticker, timeline_json FROM analysis_runs ORDER BY rowid DESC LIMIT 10")
for row in cur.fetchall():
    run_id, ticker, timeline_json = row
    print(f"=== Run: {run_id}, Ticker: {ticker} ===")
    if not timeline_json:
        print("  No timeline data")
        continue
    timeline = json.loads(timeline_json)
    for entry in timeline:
        tool = entry.get("tool")
        if tool == "build_dcf":
            args = entry.get("args", {})
            assumptions = args.get("assumptions", {})
            print(f"  build_dcf assumptions:")
            for k, v in assumptions.items():
                if k == "segments":
                    print(f"    segments:")
                    for seg in v:
                        print(f"      {seg.get('name','?')}: rev={seg.get('current_annual_revenue')} growth={seg.get('growth_rates')}")
                else:
                    print(f"    {k}: {v}")
            result = entry.get("result", {})
            if isinstance(result, dict):
                fv = result.get("fair_value_per_share")
                gap = result.get("gap_pct")
                multiples = result.get("implied_multiples", {})
                print(f"  RESULT: FV=${fv}, Gap={gap}%")
                print(f"  MULTIPLES: P/E={multiples.get('fwd_pe')} EV/EBITDA={multiples.get('ev_ebitda')} FCF_yield={multiples.get('fcf_yield')}")
            print()
        elif tool == "get_comps":
            result = entry.get("result", {})
            if isinstance(result, dict):
                median = result.get("median", {})
                print(f"  get_comps median: P/E={median.get('fwd_pe')} EV/EBITDA={median.get('ev_ebitda')}")
                print(f"  target_vs_median: {result.get('target_vs_median', {})}")
            print()
    print()
