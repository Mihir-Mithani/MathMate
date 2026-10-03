"""
Streamlit app for Hint-Based Math Tutor (Problem 13).
Single Tutor tab with V2 chained pipeline + history sidebar.
"""
import streamlit as st
import json
import os
import sys
import random
from typing import Optional
from datetime import datetime
from dotenv import load_dotenv

# Load .env from the package directory BEFORE importing modules that need it
_here = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_here, ".env"))

sys.path.insert(0, _here)

from pipeline_v2 import (
    start_problem,
    get_hint,
    can_unlock_level3,
    analyze_working,
    generate_targeted_hint,
    get_debug_log,
)
from guardrails import input_gate_code, normalise_numeric_equal


st.set_page_config(page_title="Hint-Based Math Tutor", page_icon="🧮", layout="wide")


# --- Session State ---
if "tutor_state" not in st.session_state:
    st.session_state.tutor_state = {
        "problem": "",
        "solution": None,
        "refusal": None,
        "hints_shown": [],  # list of {level, hint, follow_up, guard_status, attempts}
        "shown_levels": set(),
        "attempts_made": 0,
        "working_analysis": None,
        "targeted_hint": None,
        "final_answer": "",
    }

if "history" not in st.session_state:
    st.session_state.history = []  # list of completed problem sessions


# Bank of 6 extra problems (NOT in eval)
EXTRA_PROBLEMS = [
    {
        "id": "extra_001",
        "text": "A bakery sold 24 cupcakes in the morning and 18 in the afternoon. Each cupcake costs $2.50. How much money did the bakery make?",
        "answer": "$105.00"
    },
    {
        "id": "extra_002",
        "text": "A rectangular garden is 15 meters long and 10 meters wide. What is its perimeter?",
        "answer": "50 meters"
    },
    {
        "id": "extra_003",
        "text": "Tom reads 12 pages per day. How many pages does he read in 3 weeks?",
        "answer": "252 pages"
    },
    {
        "id": "extra_004",
        "text": "A box contains 36 chocolates. If 4 friends share them equally, how many does each get?",
        "answer": "9 chocolates"
    },
    {
        "id": "extra_005",
        "text": "A car travels 240 km on 15 liters of fuel. How many km per liter does it get?",
        "answer": "16 km/L"
    },
    {
        "id": "extra_006",
        "text": "Lisa has 3 bags with 8 marbles each. She gives 5 marbles to her brother. How many marbles does she have left?",
        "answer": "19 marbles"
    },
]


# --- Helper Functions ---
def format_hint_card(level: int, hint_text: str, follow_up: Optional[str], guard_status: str, attempts: int):
    """Render a hint card with guard badge."""
    level_names = {1: "🎯 Level 1: Orient", 2: "🧭 Level 2: Strategy", 3: "📝 Level 3: Walkthrough"}
    badge_colors = {
        "passed": "🟢",
        "fallback": "🔴",
    }

    if guard_status.startswith("regenerated"):
        badge = f"🟡 Regenerated {guard_status.split('_')[1]}×"
    else:
        badge = f"{badge_colors.get(guard_status, '⚪')} {guard_status.capitalize()}"

    with st.container(border=True):
        st.markdown(f"### {level_names.get(level, f'Level {level}')}")
        st.markdown(f"**Guard:** {badge}")
        st.markdown(hint_text)
        if follow_up:
            st.info(f"💡 {follow_up}")


def reset_tutor():
    """Reset tutor state for a new problem, saving current to history."""
    state = st.session_state.tutor_state
    if state["problem"] and (state["hints_shown"] or state["working_analysis"] or state["final_answer"]):
        # Save to history
        history_entry = {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "problem": state["problem"],
            "hints": state["hints_shown"].copy(),
            "working_analysis": state["working_analysis"],
            "targeted_hint": state["targeted_hint"],
            "final_answer": state["final_answer"],
            "solution_answer": state["solution"].final_answer if state["solution"] else None,
        }
        st.session_state.history.insert(0, history_entry)  # newest first

    # Reset tutor state
    st.session_state.tutor_state = {
        "problem": "",
        "solution": None,
        "refusal": None,
        "hints_shown": [],
        "shown_levels": set(),
        "attempts_made": 0,
        "working_analysis": None,
        "targeted_hint": None,
        "final_answer": "",
    }


def clear_history():
    """Clear the history sidebar."""
    st.session_state.history = []


def load_history_problem(index: int):
    """Load a problem from history back into the tutor."""
    if 0 <= index < len(st.session_state.history):
        entry = st.session_state.history[index]
        state = st.session_state.tutor_state
        state["problem"] = entry["problem"]
        state["hints_shown"] = entry["hints"].copy()
        state["shown_levels"] = set(h["level"] for h in entry["hints"])
        state["working_analysis"] = entry["working_analysis"]
        state["targeted_hint"] = entry["targeted_hint"]
        state["final_answer"] = entry["final_answer"]
        state["attempts_made"] = len([h for h in entry["hints"] if h["level"] == 3]) + (1 if entry["working_analysis"] else 0)
        # Note: solution is not restored (hidden), user would need to click Start Problem again


# --- Sidebar ---
with st.sidebar:
    st.header("⚙️ Settings")

    # Model selector
    model_option = st.selectbox(
        "Model",
        ["MODEL_MAIN (nemotron-3-super)", "MODEL_FAST (nemotron-3-super)"],
        index=0,
        help="MODEL_MAIN and MODEL_FAST both use nemotron-3-super-120b-a12b via NVIDIA NIM"
    )
    model_key = "MODEL_MAIN" if "MAIN" in model_option else "MODEL_FAST"
    model_name = os.getenv(model_key, "nvidia/nemotron-3-super-120b-a12b")

    # Debug toggle
    show_debug = st.checkbox("Show Debug Info", value=False)

    st.divider()

    # --- HISTORY PANEL ---
    st.header("📜 Session History")
    if st.button("Clear History", use_container_width=True):
        clear_history()
        st.rerun()

    if st.session_state.history:
        for idx, entry in enumerate(st.session_state.history):
            with st.expander(f"{entry['timestamp']} — {entry['problem'][:50]}{'...' if len(entry['problem']) > 50 else ''}", expanded=False):
                st.caption(f"Problem: {entry['problem']}")
                if entry["solution_answer"]:
                    st.caption(f"Answer: {entry['solution_answer']}")

                # Show hints given
                for h in entry["hints"]:
                    level_names = {1: "L1 Orient", 2: "L2 Strategy", 3: "L3 Walkthrough"}
                    guard_short = h["guard_status"]
                    if guard_short.startswith("regenerated"):
                        guard_short = f"regen {guard_short.split('_')[1]}×"
                    st.markdown(f"**{level_names.get(h['level'], f'L{h['level']}')}** ({guard_short})")
                    st.caption(h["hint"][:120] + ("..." if len(h["hint"]) > 120 else ""))

                # Show working analysis
                if entry["working_analysis"]:
                    wa = entry["working_analysis"]
                    if wa.has_error:
                        st.warning(f"⚠️ Step {wa.first_wrong_step_index + 1} flagged: {wa.error_type}")
                    else:
                        st.success("✅ No errors")

                # Show targeted hint
                if entry["targeted_hint"]:
                    th = entry["targeted_hint"]
                    st.info(f"Targeted hint: {th['hint'][:100]}...")

                # Show final answer
                if entry["final_answer"]:
                    correct = "✅" if entry["solution_answer"] and normalise_numeric_equal(entry["final_answer"], entry["solution_answer"]) else "❌"
                    st.markdown(f"**Your answer:** {entry['final_answer']} {correct}")

                if st.button("Load This Problem", key=f"load_{idx}", use_container_width=True):
                    load_history_problem(idx)
                    st.rerun()
    else:
        st.caption("No problems solved yet. Start a new problem!")

    st.divider()
    st.caption("Hint-Based Math Tutor — Problem 13")


# --- MAIN TUTOR TAB ---
def main():
    st.title("🧮 Hint-Based Math Tutor")
    st.caption("Progressive hints without revealing answers early")

    state = st.session_state.tutor_state

    # Problem input
    problem_text = st.text_area(
        "Math Word Problem",
        value=state["problem"],
        height=100,
        placeholder="Enter a math word problem...\n\nExample: Sarah has 15 apples. She gives 4 to her friend and buys 7 more. How many apples does she have now?"
    )

    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if st.button("Start Problem", type="primary", use_container_width=True):
            if problem_text.strip():
                with st.spinner("Starting problem..."):
                    result = start_problem(problem_text, model=model_name)

                    state["problem"] = problem_text
                    state["refusal"] = None
                    state["solution"] = None
                    state["hints_shown"] = []
                    state["shown_levels"] = set()
                    state["attempts_made"] = 0
                    state["working_analysis"] = None
                    state["targeted_hint"] = None

                    if result["status"] == "ok":
                        state["solution"] = result.get("solution")
                        st.success("Problem ready! Click Hint 1 to begin.")
                    else:
                        state["refusal"] = result["refusal_message"]
                        st.error(result["refusal_message"])
                    st.rerun()
            else:
                st.error("Please enter a problem")

    with col2:
        if st.button("Try Random Problem", use_container_width=True):
            prob = random.choice(EXTRA_PROBLEMS)
            state["problem"] = prob["text"]
            st.rerun()

    with col3:
        if st.button("New Problem", use_container_width=True):
            reset_tutor()
            st.rerun()

    # Show refusal if any
    if state["refusal"]:
        st.error(f"⛔ {state['refusal']}")
        st.stop()

    # Show solution in debug
    if show_debug and state["solution"]:
        with st.expander("🔍 Hidden Solution (Debug Only)"):
            sol = state["solution"]
            for step in sol.steps:
                st.write(f"- {step.description}: {step.expression} = {step.result}")
            st.write(f"**Final Answer:** {sol.final_answer}")

    # Hint buttons
    if state["solution"]:
        st.divider()
        st.subheader("Get Hints")

        hint_cols = st.columns(3)

        # Hint 1
        with hint_cols[0]:
            hint1_shown = any(h["level"] == 1 for h in state["hints_shown"])
            if st.button("Hint 1 (Orient)", disabled=hint1_shown, use_container_width=True):
                with st.spinner("Generating Hint 1..."):
                    prev_hints = [h["hint"] for h in state["hints_shown"]]
                    result = get_hint(state["problem"], state["solution"], 1, prev_hints, model=model_name)
                    state["hints_shown"].append({"level": 1, **result})
                    state["shown_levels"].add(1)
                    st.rerun()

        # Hint 2
        with hint_cols[1]:
            hint2_shown = any(h["level"] == 2 for h in state["hints_shown"])
            disabled = hint2_shown or not any(h["level"] == 1 for h in state["hints_shown"])
            if st.button("Hint 2 (Strategy)", disabled=disabled, use_container_width=True):
                with st.spinner("Generating Hint 2..."):
                    prev_hints = [h["hint"] for h in state["hints_shown"]]
                    result = get_hint(state["problem"], state["solution"], 2, prev_hints, model=model_name)
                    state["hints_shown"].append({"level": 2, **result})
                    state["shown_levels"].add(2)
                    st.rerun()

        # Hint 3
        with hint_cols[2]:
            hint3_shown = any(h["level"] == 3 for h in state["hints_shown"])
            can_unlock = can_unlock_level3(list(state["shown_levels"]), state["attempts_made"])
            disabled = hint3_shown or not can_unlock
            if st.button("Hint 3 (Walkthrough)", disabled=disabled, use_container_width=True):
                with st.spinner("Generating Walkthrough..."):
                    prev_hints = [h["hint"] for h in state["hints_shown"]]
                    result = get_hint(state["problem"], state["solution"], 3, prev_hints, model=model_name)
                    state["hints_shown"].append({"level": 3, **result})
                    state["shown_levels"].add(3)
                    st.rerun()

            if not can_unlock and not hint3_shown:
                st.caption("⚠️ Unlock after Level 1 & 2 or an attempt")

        # Display hints
        if state["hints_shown"]:
            st.divider()
            st.subheader("Hints Given")
            for h in state["hints_shown"]:
                format_hint_card(h["level"], h["hint"], h.get("follow_up"), h["guard_status"], h["attempts"])

    # Working check
    if state["solution"]:
        st.divider()
        st.subheader("📝 Check Your Working")

        working_text = st.text_area(
            "Show your working (one step per line)",
            height=100,
            placeholder="Example:\n15 - 4 = 11\n11 + 7 = 18"
        )

        col1, col2 = st.columns([1, 2])
        with col1:
            if st.button("Check My Working", type="secondary", use_container_width=True):
                if working_text.strip():
                    state["attempts_made"] += 1
                    with st.spinner("Analyzing working..."):
                        analysis = analyze_working(state["problem"], state["solution"], working_text, model=model_name)
                        state["working_analysis"] = analysis

                        # Determine current level for targeted hint
                        current_level = 1
                        if any(h["level"] >= 2 for h in state["hints_shown"]):
                            current_level = 2

                        targeted = generate_targeted_hint(
                            state["problem"], state["solution"], analysis, current_level, model=model_name
                        )
                        state["targeted_hint"] = targeted
                    st.rerun()
                else:
                    st.error("Please enter your working")

        with col2:
            if state["working_analysis"]:
                wa = state["working_analysis"]
                if wa.has_error:
                    st.warning(f"⚠️ Step {wa.first_wrong_step_index + 1} flagged: **{wa.error_type}**")
                else:
                    st.success("✅ No errors detected")

        # Show targeted hint
        if state["targeted_hint"]:
            th = state["targeted_hint"]
            format_hint_card(
                1 if "Orient" in str(th.get("follow_up", "")) else 2,
                th["hint"],
                th.get("follow_up"),
                th["guard_status"],
                th["attempts"]
            )

    # Final answer
    if state["solution"]:
        st.divider()
        st.subheader("🎯 Your Final Answer")
        final_answer = st.text_input("Enter your final answer", value=state["final_answer"])
        state["final_answer"] = final_answer

        if st.button("Check Answer", use_container_width=True):
            if final_answer.strip():
                correct = normalise_numeric_equal(final_answer, state["solution"].final_answer)
                if correct:
                    st.success("✅ Correct!")
                else:
                    st.error(f"❌ Incorrect. The answer is: {state['solution'].final_answer}")
            else:
                st.error("Please enter an answer")

    # Debug log
    if show_debug:
        st.divider()
        st.subheader("🐛 Debug Log")
        for entry in get_debug_log():
            st.json(entry)


if __name__ == "__main__":
    main()