"""
Streamlit app for Hint-Based Math Tutor.
4 tabs: Tutor (V1 naive), Compare, Evaluate, Prompt History.
"""
import streamlit as st
import json
import os
import sys
from datetime import datetime
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pipeline_v1 import get_hint_v1
from pipeline_v2 import run_pipeline_v2
from schemas import ProblemInput, Hint
from guardrails import input_gate_code_check
from llm import get_counters, reset_counters


st.set_page_config(page_title="Hint-Based Math Tutor", page_icon="🧮", layout="wide")


# --- Session State ---
if "tutor_history" not in st.session_state:
    st.session_state.tutor_history = []  # List of (problem, level, hint_text)
if "current_problem" not in st.session_state:
    st.session_state.current_problem = ""


# --- TAB 1: TUTOR (V1 Naive) ---
def tab_tutor():
    st.header("🧮 Math Tutor (V1 Naive Baseline)")
    st.caption("Single prompt, no gates, no hidden solution, no leak check")

    problem_text = st.text_area(
        "Math Word Problem",
        value=st.session_state.current_problem,
        height=120,
        placeholder="Enter a math word problem...\n\nExample: Sarah has 15 apples. She gives 4 to her friend and buys 7 more. How many apples does she have now?"
    )
    st.session_state.current_problem = problem_text

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Hint 1 (Small Nudge)", use_container_width=True):
            if problem_text.strip():
                with st.spinner("Generating hint..."):
                    hint = get_hint_v1(problem_text, 1)
                    st.session_state.tutor_history.append((problem_text, 1, hint))
                    st.rerun()
            else:
                st.error("Please enter a problem")

    with col2:
        if st.button("Hint 2 (Bigger Hint)", use_container_width=True):
            if problem_text.strip():
                with st.spinner("Generating hint..."):
                    hint = get_hint_v1(problem_text, 2)
                    st.session_state.tutor_history.append((problem_text, 2, hint))
                    st.rerun()
            else:
                st.error("Please enter a problem")

    with col3:
        if st.button("Hint 3 (Full Solution)", use_container_width=True):
            if problem_text.strip():
                with st.spinner("Generating hint..."):
                    hint = get_hint_v1(problem_text, 3)
                    st.session_state.tutor_history.append((problem_text, 3, hint))
                    st.rerun()
            else:
                st.error("Please enter a problem")

    if st.button("Clear History", use_container_width=True):
        st.session_state.tutor_history = []
        st.rerun()

    # Display hint history
    st.divider()
    st.subheader("Hint History")

    for i, (prob, lvl, hint_text) in enumerate(reversed(st.session_state.tutor_history)):
        level_names = {1: "🎯 Level 1: Small Nudge", 2: "🧭 Level 2: Bigger Hint", 3: "📝 Level 3: Full Solution"}
        with st.expander(f"{level_names.get(lvl, f'Level {lvl}')}", expanded=(i == 0)):
            st.markdown(hint_text)


# --- TAB 2: COMPARE ---
def tab_compare():
    st.header("⚖️ V1 vs V2 Comparison")
    st.caption("Side-by-side comparison on the same input")

    problem_text = st.text_area(
        "Test Problem",
        height=100,
        placeholder="Enter a problem to compare V1 and V2 outputs..."
    )

    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        level = st.selectbox("Hint Level", [1, 2, 3], format_func=lambda x: {1: "1 - Orient", 2: "2 - Strategy", 3: "3 - Walkthrough"}[x])
    with col2:
        working = st.text_area("Student Working (optional)", height=80)
    with col3:
        st.write("")
        st.write("")
        run_compare = st.button("Compare", type="primary", use_container_width=True)

    if run_compare and problem_text.strip():
        reset_counters()

        # V1
        with st.spinner("Running V1..."):
            v1_hint = get_hint_v1(problem_text, level)
        v1_calls, v1_valid = get_counters()

        reset_counters()

        # V2
        prob_input = ProblemInput(problem_text=problem_text, student_working=working if working else None, hint_level=level)
        with st.spinner("Running V2..."):
            v2_resp = run_pipeline_v2(prob_input)
        v2_calls, v2_valid = get_counters()

        st.divider()
        c1, c2 = st.columns(2)

        with c1:
            st.subheader("V1 (Naive Baseline)")
            st.caption(f"API Calls: {v1_calls} | First-try Valid: {v1_valid}")
            st.markdown(v1_hint)

        with c2:
            st.subheader("V2 (Chained Pipeline)")
            st.caption(f"API Calls: {v2_calls} | First-try Valid: {v2_valid}")
            st.markdown(format_hint(v2_resp.hint))
            st.write(f"**Leak Check:** {'✅ Passed' if v2_resp.leak_check_passed else '🚫 Failed'}")
            if v2_resp.working_analysis:
                wa = v2_resp.working_analysis
                st.info(f"**Working Analysis:** {'Error found' if wa.has_error else 'No error'} | Type: {wa.error_type or 'N/A'}")


def format_hint(hint: Hint) -> str:
    """Format hint for display."""
    level_names = {1: "🎯 Level 1: Orient", 2: "🧭 Level 2: Strategy", 3: "📝 Level 3: Walkthrough"}
    out = f"### {level_names.get(hint.level, f'Level {hint.level}')}\n\n{hint.content}"
    if hint.guiding_question:
        out += f"\n\n**Guiding Question:** {hint.guiding_question}"
    if hint.concept:
        out += f"\n\n**Concept:** {hint.concept}"
    if hint.sub_goal:
        out += f"\n\n**First Sub-goal:** {hint.sub_goal}"
    return out


# --- TAB 3: EVALUATE ---
def tab_evaluate():
    st.header("📊 Evaluation")
    st.caption("Run evaluation suite on test cases")

    if st.button("Run Full Evaluation", type="primary"):
        with st.spinner("Running evaluation... This may take a minute."):
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), "eval"))
            from run_eval import main as run_eval_main
            import io
            import contextlib

            f = io.StringIO()
            with contextlib.redirect_stdout(f):
                run_eval_main()
            output = f.getvalue()

        st.code(output)

        results_dir = "eval/results"
        if os.path.exists(results_dir):
            files = sorted([f for f in os.listdir(results_dir) if f.endswith('.json')])
            if files:
                latest = files[-1]
                with open(os.path.join(results_dir, latest), 'r') as f:
                    data = json.load(f)

                st.subheader("Latest Results")
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.metric("Guardrail Accuracy", f"{data['guardrails']['accuracy']:.0%}")
                    st.metric("V1 Leak Rate", f"{data['v1_leak']['leak_rate']:.0%}")
                with c2:
                    st.metric("V2 Leak Rate", f"{data['v2_leak']['leak_rate']:.0%}")
                    st.metric("V1 Quality", f"{data['v1_quality']['avg_quality']:.2f}")
                with c3:
                    st.metric("V2 Quality", f"{data['v2_quality']['avg_quality']:.2f}")
                    st.metric("Working Detection", f"{data['working_analysis']['detection_rate']:.0%}")

                st.metric("Format Validity", f"{data['format_validity']['format_validity_rate']:.0%}")


# --- TAB 4: PROMPT HISTORY ---
def tab_prompt_history():
    st.header("📜 Prompt History")
    st.caption("Timestamped prompt versions from Git")

    history_path = "PROMPT_HISTORY.md"
    if os.path.exists(history_path):
        with open(history_path, 'r') as f:
            content = f.read()
        st.markdown(content)
    else:
        st.info("No PROMPT_HISTORY.md found. Create it to track prompt changes.")

    st.divider()
    st.subheader("Current Prompt Files")

    prompt_dirs = {
        "V1": "prompts/v1",
        "V2": "prompts/v2"
    }

    for version, path in prompt_dirs.items():
        if os.path.exists(path):
            st.write(f"**{version}** ({path})")
            files = sorted(os.listdir(path))
            for fname in files:
                fpath = os.path.join(path, fname)
                with open(fpath, 'r') as f:
                    content = f.read()
                with st.expander(f"{fname}"):
                    st.code(content, language="markdown")


# --- MAIN ---
def main():
    st.title("🧮 Hint-Based Math Tutor")
    st.caption("Progressive hints without revealing answers early | V1 vs V2 comparison")

    tabs = st.tabs(["🧮 Tutor (V1)", "⚖️ Compare", "📊 Evaluate", "📜 Prompt History"])

    with tabs[0]:
        tab_tutor()
    with tabs[1]:
        tab_compare()
    with tabs[2]:
        tab_evaluate()
    with tabs[3]:
        tab_prompt_history()


if __name__ == "__main__":
    main()