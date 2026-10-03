"""
V2 Chained Pipeline.
Input Gate -> Hidden Solver (x2) -> Hint Generator -> Schema Validation ->
Leak Guard (code + LLM) -> Regenerate up to 2x with feedback -> Fallback.
"""
import time
import json
import os
from typing import Optional, List, Dict, Any
from llm import call_json, call_llm, ValidationFailure
from guardrails import (
    input_gate_code,
    leak_check_code,
    normalise_numeric_equal,
    REFUSALS,
    SAFE_FALLBACK,
)
from schemas import Solution, Gate, Hint, LeakVerdict, WorkingAnalysis

# Get the directory where this file lives
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROMPTS_DIR = os.path.join(_HERE, "prompts")


def load_prompt(relative_path: str) -> str:
    """Load prompt from file using absolute path."""
    full_path = os.path.join(_PROMPTS_DIR, relative_path)
    with open(full_path, 'r') as f:
        return f.read()


# Global debug log
_debug_log: List[Dict[str, Any]] = []


def _log_call(card_id: str, version: str, latency: float, guard_result: str, **extra):
    """Log an LLM call for debug view."""
    _debug_log.append({
        "card_id": card_id,
        "version": version,
        "latency_ms": round(latency * 1000, 2),
        "guard_result": guard_result,
        **extra
    })


def get_debug_log() -> List[Dict[str, Any]]:
    """Get the debug log."""
    return _debug_log.copy()


def clear_debug_log():
    """Clear the debug log."""
    _debug_log.clear()


def start_problem(text: str, model: Optional[str] = None) -> Dict[str, Any]:
    """
    Start a new problem: input gate -> P0 classifier -> P1 solver (x2).
    Returns dict with status and either refusal_message or solution.
    """
    clear_debug_log()

    # 1. Input gate code check
    gate_result = input_gate_code(text)
    if gate_result:
        return {
            "status": "refused",
            "refusal_message": REFUSALS.get(gate_result, REFUSALS["off_topic"]),
            "category": gate_result,
        }

    # 2. P0 classifier (LLM)
    system_p0 = load_prompt("v2/p0_input_gate.md")
    user_p0 = f"Problem: {text}\n\nClassify this input."
    start = time.time()
    try:
        gate = call_json(system_p0, user_p0, Gate, model=model)
        _log_call("P0", "v2.0", time.time() - start, "passed" if gate.allowed else "blocked", category=gate.category)
    except ValidationFailure:
        # If P0 fails validation, fall back to code gate
        gate = Gate(allowed=True, reason="P0 validation failed, allowing", category="math_word_problem")
        _log_call("P0", "v2.0", time.time() - start, "validation_failed_fallback")

    if not gate.allowed or gate.category != "math_word_problem":
        return {
            "status": "refused",
            "refusal_message": REFUSALS.get(gate.category, REFUSALS["off_topic"]),
            "category": gate.category,
        }

    # 3. P1 solver twice (temperature 0 and 0.7)
    system_p1 = load_prompt("v2/p1_solver.md")
    user_p1 = f"Problem: {text}\n\nProvide a complete step-by-step solution."

    solutions = []
    for temp in [0.0, 0.7]:
        start = time.time()
        try:
            sol = call_json(system_p1, user_p1, Solution, model=model, temperature=temp)
            solutions.append(sol)
            _log_call("P1", "v2.0", time.time() - start, "success", temperature=temp)
        except ValidationFailure as e:
            _log_call("P1", "v2.0", time.time() - start, "validation_failed", temperature=temp, error=str(e))
            return {
                "status": "refused",
                "refusal_message": REFUSALS["unverifiable"],
                "category": "unverifiable",
            }

    # Check consistency of final answers
    if len(solutions) == 2:
        ans1 = solutions[0].final_answer
        ans2 = solutions[1].final_answer
        if not normalise_numeric_equal(ans1, ans2):
            _log_call("P1_consistency", "v2.0", 0, "mismatch", answer1=ans1, answer2=ans2)
            return {
                "status": "refused",
                "refusal_message": REFUSALS["unverifiable"],
                "category": "unverifiable",
            }

    return {
        "status": "ok",
        "solution": solutions[0],
    }


def get_hint(
    problem: str,
    solution: Solution,
    level: int,
    previous_hints: Optional[List[str]] = None,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate hint at given level with leak guard.
    Returns dict with hint, follow_up, guard_status, attempts.
    """
    if level not in (1, 2, 3):
        raise ValueError("Level must be 1, 2, or 3")

    previous_hints = previous_hints or []
    system_p2 = load_prompt("v2/p2_hint_generator.md")
    system_p3 = load_prompt("v2/p3_leak_judge.md")

    # Build solution text for prompt
    solution_text = ""
    for i, step in enumerate(solution.steps):
        solution_text += f"Step {i+1}: {step.description}"
        if step.expression:
            solution_text += f" | {step.expression}"
        if step.result:
            solution_text += f" = {step.result}"
        solution_text += "\n"
    solution_text += f"Final Answer: {solution.final_answer}\n"

    # Build previous hints context
    prev_hints_text = ""
    if previous_hints:
        prev_hints_text = "\nPrevious hints given:\n" + "\n".join(f"- {h}" for h in previous_hints)

    leak_feedback = ""
    attempts = 0
    max_attempts = 2 if level in (1, 2) else 0

    while True:
        attempts += 1

        # Build user prompt for P2
        user_p2 = f"""Problem: {problem}
Hint Level: {level}
Reference Solution:
{solution_text}{prev_hints_text}
Leak Feedback: {leak_feedback if leak_feedback else "None"}

Generate a hint at the requested level. Follow the level constraints strictly.
Return ONLY valid JSON matching the Hint schema."""

        # Generate hint with P2
        start = time.time()
        try:
            hint = call_json(system_p2, user_p2, Hint, model=model)
            _log_call("P2", "v2.0", time.time() - start, "success", level=level, attempt=attempts)
        except ValidationFailure as e:
            _log_call("P2", "v2.0", time.time() - start, "validation_failed", level=level, attempt=attempts, error=str(e))
            return {
                "hint": SAFE_FALLBACK[level],
                "follow_up": None,
                "guard_status": "fallback",
                "attempts": attempts,
            }

        # Level 3: no leak check
        if level == 3:
            return {
                "hint": hint.content,
                "follow_up": None,
                "guard_status": "passed",
                "attempts": attempts,
            }

        # Leak check: code first
        code_leak, code_reason = leak_check_code(hint.content, solution.final_answer, problem)
        if code_leak:
            _log_call("leak_code", "v2.0", 0, "leak", level=level, attempt=attempts, reason=code_reason)
            if attempts > max_attempts:
                return {
                    "hint": SAFE_FALLBACK[level],
                    "follow_up": None,
                    "guard_status": "fallback",
                    "attempts": attempts,
                }
            leak_feedback = f"Code leak check failed: {code_reason}. Regenerate without leaking."
            continue

        # Leak check: LLM judge (P3)
        user_p3 = f"""Problem: {problem}
Correct Final Answer: {solution.final_answer}

Hint to Evaluate (Level {level}):
{hint.content}

Evaluate this hint for leaks. Return LeakVerdict JSON."""

        start = time.time()
        try:
            verdict = call_json(system_p3, user_p3, LeakVerdict, model=model)
            _log_call("P3", "v2.0", time.time() - start, "leak" if verdict.has_leak else "passed", level=level, attempt=attempts, severity=verdict.severity, leak_type=verdict.leak_type)
        except ValidationFailure as e:
            _log_call("P3", "v2.0", time.time() - start, "validation_failed", level=level, attempt=attempts, error=str(e))
            # Default to safe: assume leak
            verdict = LeakVerdict(has_leak=True, leak_type="other", explanation="Judge validation failed", severity="major")

        if verdict.has_leak:
            severity = verdict.severity
            if severity in ("partial", "minor", "major", "full"):  # treat any leak as regenerate
                if attempts > max_attempts:
                    return {
                        "hint": SAFE_FALLBACK[level],
                        "follow_up": None,
                        "guard_status": "fallback",
                        "attempts": attempts,
                    }
                leak_feedback = f"LLM leak judge failed: {verdict.explanation} (type: {verdict.leak_type}, severity: {verdict.severity}). Regenerate strictly."
                continue

        # Passed all checks
        follow_up = None
        if level == 1 and hint.guiding_question:
            follow_up = hint.guiding_question
        elif level == 2:
            parts = []
            if hint.concept:
                parts.append(f"Concept: {hint.concept}")
            if hint.sub_goal:
                parts.append(f"First sub-goal: {hint.sub_goal}")
            if parts:
                follow_up = " | ".join(parts)

        return {
            "hint": hint.content,
            "follow_up": follow_up,
            "guard_status": "passed" if attempts == 1 else f"regenerated_{attempts-1}",
            "attempts": attempts,
        }


def can_unlock_level3(shown_levels: List[int], attempts_made: int) -> bool:
    """Check if level 3 can be unlocked."""
    return (1 in shown_levels and 2 in shown_levels) or attempts_made > 0


def analyze_working(
    problem: str,
    solution: Solution,
    student_working: str,
    model: Optional[str] = None,
) -> WorkingAnalysis:
    """Analyze student working for errors (stretch)."""
    system_p4 = load_prompt("v2/p4_working_analyzer.md")

    solution_text = ""
    for i, step in enumerate(solution.steps):
        solution_text += f"Step {i+1}: {step.description}"
        if step.expression:
            solution_text += f" | {step.expression}"
        if step.result:
            solution_text += f" = {step.result}"
        solution_text += "\n"

    user_p4 = f"""Problem: {problem}
Correct Solution:
{solution_text}
Student Working: {student_working}

Analyze the student's working. Identify the FIRST wrong step, classify the error type,
and explain what the student should do differently. Return WorkingAnalysis JSON."""

    try:
        return call_json(system_p4, user_p4, WorkingAnalysis, model=model)
    except ValidationFailure:
        return WorkingAnalysis(
            has_error=False,
            first_wrong_step_index=None,
            error_type=None,
            expected_step=None,
            explanation="Could not analyze working."
        )


def generate_targeted_hint(
    problem: str,
    solution: Solution,
    analysis: WorkingAnalysis,
    level: int,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate targeted hint based on working analysis (stretch)."""
    system_p5 = load_prompt("v2/p5_targeted_hint.md")

    solution_text = ""
    for i, step in enumerate(solution.steps):
        solution_text += f"Step {i+1}: {step.description}"
        if step.expression:
            solution_text += f" | {step.expression}"
        if step.result:
            solution_text += f" = {step.result}"
        solution_text += "\n"

    user_p5 = f"""Problem: {problem}
Hint Level: {level}
Reference Solution:
{solution_text}
Error Analysis:
- First wrong step: {analysis.first_wrong_step_index + 1 if analysis.first_wrong_step_index is not None else 'N/A'}
- Error type: {analysis.error_type}
- Expected correct step: {analysis.expected_step}
- Explanation: {analysis.explanation}

Generate a TARGETED hint addressing this specific error at the requested level.
Follow level constraints strictly. Return ONLY valid JSON matching the Hint schema."""

    try:
        hint = call_json(system_p5, user_p5, Hint, model=model)
        # Apply leak guard to targeted hint too
        if level in (1, 2):
            code_leak, code_reason = leak_check_code(hint.content, solution.final_answer, problem)
            if code_leak:
                return {"hint": SAFE_FALLBACK[level], "follow_up": None, "guard_status": "fallback", "attempts": 1}
        return {"hint": hint.content, "follow_up": None, "guard_status": "passed", "attempts": 1}
    except ValidationFailure:
        return {"hint": SAFE_FALLBACK[level], "follow_up": None, "guard_status": "fallback", "attempts": 1}