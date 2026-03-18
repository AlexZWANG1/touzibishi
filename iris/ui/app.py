import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import streamlit as st
from dotenv import load_dotenv
load_dotenv()

st.set_page_config(page_title="IRIS — Investment Research", layout="wide", page_icon="🔍")


@st.cache_resource
def get_harness():
    from main import build_harness
    return build_harness()


def render_tool_log(tool_log: list[dict]):
    with st.expander(f"Tool Calls ({len(tool_log)})", expanded=False):
        for i, entry in enumerate(tool_log):
            status_icon = "✅" if entry["status"] == "ok" else "❌" if entry["status"] == "blocked" else "⚠️"
            st.markdown(f"{status_icon} **{i+1}. {entry['tool']}** — `{entry['status']}`")
            if entry.get("reason"):
                st.caption(f"  Blocked: {entry['reason']}")


def render_sidebar():
    with st.sidebar:
        st.title("IRIS")
        st.caption("Intelligent Research & Investment System")
        st.divider()
        st.markdown("**How to use:**")
        st.markdown("1. Enter a ticker or research question")
        st.markdown("2. Optionally paste documents")
        st.markdown("3. Click **Run Analysis**")
        st.divider()
        with st.expander("Model Config"):
            model = st.text_input("OpenAI Model", value=os.getenv("OPENAI_MODEL", "gpt-4o"))
            if model != os.getenv("OPENAI_MODEL", "gpt-4o"):
                os.environ["OPENAI_MODEL"] = model
                st.cache_resource.clear()
                st.success("Model updated — restart analysis")

        st.divider()
        st.markdown("**Run Telemetry**")
        result = st.session_state.get("last_result")
        if result is None:
            st.caption("No run yet")
            return

        st.caption(f"Run ID: `{result.run_id or '-'}`")

        breakdown = result.budget_breakdown or {}
        rounds = breakdown.get("tool_rounds", {})
        calls = breakdown.get("tool_calls", {})

        rounds_used = rounds.get("counted_total", 0)
        rounds_limit = max(1, rounds.get("limit", 1))
        calls_used = calls.get("total", 0)
        calls_limit = max(1, calls.get("limit", 1))

        st.caption(f"Rounds: {rounds_used}/{rounds_limit}")
        st.progress(min(1.0, rounds_used / rounds_limit))

        st.caption(f"Tool Calls: {calls_used}/{calls_limit}")
        st.progress(min(1.0, calls_used / calls_limit))

        st.caption(f"Total Tool Log Entries: {len(result.tool_log)}")
        if result.error:
            st.error(f"Stop reason: {result.error}")
        else:
            st.success("Stop reason: final response produced")


def main():
    render_sidebar()
    st.title("IRIS Investment Analysis")
    st.caption("AI-native investment research with full audit trail")

    col1, col2 = st.columns([1, 1])

    with col1:
        query = st.text_input(
            "Research query",
            placeholder="e.g. 分析 NVDA 在 AI 训练基础设施的投资机会",
        )
        docs_input = st.text_area(
            "Paste documents (optional)",
            placeholder="Paste earnings call transcript, research report excerpt...",
            height=200,
        )
        run_btn = st.button("Run Analysis", type="primary", use_container_width=True)

    with col2:
        if "last_result" in st.session_state:
            result = st.session_state["last_result"]
            if result.ok:
                st.success("Analysis Complete")
                st.markdown(result.reply)
                render_tool_log(result.tool_log)
                st.caption(f"Tokens: {result.total_input_tokens:,} in / {result.total_output_tokens:,} out")
            else:
                st.error(f"Analysis failed: {result.error}")
                render_tool_log(result.tool_log)

    if run_btn and query:
        harness, _ = get_harness()
        docs = [docs_input] if docs_input.strip() else None
        with col2:
            with st.spinner("Analyzing... (1-3 minutes)"):
                result = harness.run(query, context_docs=docs)
                st.session_state["last_result"] = result
                st.rerun()


if __name__ == "__main__":
    main()
