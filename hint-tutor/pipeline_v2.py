"""
V2 Chained Pipeline.
Input Gate -> Hidden Solver (x2) -> Hint Generator -> Schema Validation ->
Leak Guard (code + LLM) -> Regenerate up to 2x with feedback -> Fallback.
Stretch: Working Analyzer -> Targeted Hint.
"""
from typing import Optional, List, Tuple
from schemas import ProblemInput, Hint, TutorResponse, Solution, Gate, LeakVerdict, WorkingAnalysis, Step
from llm import call_llm, call_json, ValidationFailure
from guardrails import input_gate_code_check, get_refusal, get_fallback_hint, leak_check_code
from arithmetic_check import find_first_arithmetic_error, check_working_against_solution, parse_expression
import json


def load_prompt(path: str) -> str:
    """Load prompt from file."""
    with open(path, 'r') as f:
        return f.read()


# --- Hidden Solver (runs twice, verifies consistency) ---

def solve_problem_v2(problem_text: str, model: Optional[str] = None) -> Optional[Solution]:
    """Run solver once."""
    system = load_prompt("prompts/v2/p1_solver.md")
    user = f"Problem: {problem_text}\n\nProvide a complete step-by-step solution."
    try:
        return call_json(system, user, Solution, model=model)
    except ValidationFailure:
        return None
    except Exception:
        return None


def solve_and_verify(problem_text: str) -> Optional[Solution]:
    """Run solver twice, return solution if answers match."""
    sol1 = solve_problem_v2(problem_text)
    sol2 = solve_problem_v2(problem_text)

    if sol1 and sol2:
        # Compare final answers (normalize)
        ans1 = sol1.final_answer.strip().lower()
        ans2 = sol2.final_answer.strip().lower()
        if ans1 == ans2:
            return sol1

    return None  # Unverifiable


# --- Hint Generator with Schema Validation (retry once) ---

def generate_hint_v2(
    problem: ProblemInput,
    solution: Solution,
    level: int,
    model: Optional[str] = None
) -> Hint:
    """Generate hint with schema validation retry."""
    system = load_prompt("prompts/v2/p2_hint_generator.md")

    level_names = {1: "Orient", 2: "Strategy", 3: "Walkthrough"}
    level_name = level_names.get(level, "Orient")

    solution_text = ""
    for i, step in enumerate(solution.steps):
        solution_text += f"Step {i+1}: {step.description}"
        if step.expression:
            solution_text += f" | {step.expression}"
        if step.result:
            solution_text += f" = {step.result}"
        solution_text += "\n"
    solution_text += f"Final Answer: {solution.final_answer}\n"

    user = f"""Problem: {problem.problem_text}
Hint Level: {level} ({level_name})
Reference Solution:
{solution_text}
Student Working: {problem.student_working or 'None provided'}

Generate a hint at the requested level. Follow the level constraints strictly.
Return ONLY valid JSON matching the Hint schema."""

    # First attempt
    try:
        hint = call_json(system, user, Hint, model=model)
        return hint
    except ValidationFailure as e:
        # Retry once with error feedback
        retry_user = f"{user}\n\nYour last output failed validation: {e}. Return valid JSON only matching the Hint schema."
        try:
            hint = call_json(system, retry_user, Hint, model=model)
            return hint
        except ValidationFailure:
            return get_fallback_hint(level, problem.problem_text)
    except Exception:
        return get_fallback_hint(level, problem.problem_text)


# --- Leak Guard (Code + LLM Judge) with Regeneration ---

def leak_check_llm(hint: Hint, problem_text: str, solution: Solution) -> LeakVerdict:
    """LLM-based leak detection for Levels 1-2."""
    system = load_prompt("prompts/v2/p3_leak_judge.md")

    level_names = {1: "Orient", 2: "Strategy"}
    level_name = level_names.get(hint.level, "Orient")

    # Build forbidden criteria
    if hint.level == 1:
        forbidden = (
            "Level 1 (Orient) FORBIDDEN: naming any operation (add/subtract/multiply/divide), "
            "any formula, any computed number, the final answer, or any mathematical expression with numbers."
        )
    else:
        forbidden = (
            "Level 2 (Strategy) FORBIDDEN: revealing the final answer, the result of the final step, "
            "or the complete solution. Naming the concept/approach and first sub-goal is ALLOWED."
        )

    user = f"""Problem: {problem_text}
Correct Final Answer: {solution.final_answer}

Hint to Evaluate (Level {hint.level} - {level_name}):
{hint.content}

{forbidden}

Does this hint leak forbidden information? Return LeakVerdict JSON."""

    try:
        return call_json(system, user, LeakVerdict)
    except Exception:
        # Default to safe: assume leak if LLM fails
        return LeakVerdict(
            has_leak=True,
            leak_type="other",
            explanation="LLM judge failed, defaulting to leak detection",
            severity="major"
        )


def regenerate_hint_with_feedback(
    problem: ProblemInput,
    solution: Solution,
    level: int,
    previous_hint: Hint,
    leak_verdict: LeakVerdict,
    attempt: int,
    model: Optional[str] = None
) -> Hint:
    """Regenerate hint with leak feedback."""
    system = load_prompt("prompts/v2/p2_hint_generator.md")

    level_names = {1: "Orient", 2: "Strategy", 3: "Walkthrough"}
    level_name = level_names.get(level, "Orient")

    solution_text = ""
    for i, step in enumerate(solution.steps):
        solution_text += f"Step {i+1}: {step.description}"
        if step.expression:
            solution_text += f" | {step.expression}"
        if step.result:
            solution_text += f" = {step.result}"
        solution_text += "\n"
    solution_text += f"Final Answer: {solution.final_answer}\n"

    feedback = (
        f"Your previous hint was rejected for leaking: {leak_verdict.leak_type} "
        f"({leak_verdict.explanation}). Severity: {leak_verdict.severity}. "
        f"Regenerate a STRICTLY compliant hint."
    )

    user = f"""Problem: {problem.problem_text}
Hint Level: {level} ({level_name})
Reference Solution:
{solution_text}
Student Working: {problem.student_working or 'None provided'}

REGENERATION ATTEMPT {attempt}/2
PREVIOUS HINT REJECTED: {previous_hint.content}
FEEDBACK: {feedback}

Generate a hint at the requested level. Follow the level constraints STRICTLY.
Return ONLY valid JSON matching the Hint schema."""

    try:
        return call_json(system, user, Hint, model=model)
    except Exception:
        return get_fallback_hint(level, problem.problem_text)


def apply_leak_guard(
    problem: ProblemInput,
    solution: Solution,
    hint: Hint,
    model: Optional[str] = None
) -> Tuple[Hint, bool]:
    """Apply code + LLM leak checks, regenerate up to 2 times, then fallback."""
    # Code check first
    code_verdict = leak_check_code(hint)
    if code_verdict.has_leak:
        return get_fallback_hint(problem.hint_level, problem.problem_text), False

    # LLM judge for levels 1-2
    if problem.hint_level in [1, 2]:
        for attempt in range(1, 3):  # Up to 2 regenerations
            llm_verdict = leak_check_llm(hint, problem.problem_text, solution)
            if not llm_verdict.has_leak:
                return hint, True
            # Regenerate with feedback
            hint = regenerate_hint_with_feedback(
                problem, solution, problem.hint_level, hint, llm_verdict, attempt, model
            )
            # Re-check code
            code_verdict = leak_check_code(hint)
            if code_verdict.has_leak:
                return get_fallback_hint(problem.hint_level, problem.problem_text), False

        # All regenerations failed
        return get_fallback_hint(problem.hint_level, problem.problem_text), False

    return hint, True


# --- Stretch: Working Analyzer + Targeted Hint ---

def analyze_working(
    problem: ProblemInput,
    solution: Solution
) -> Optional[WorkingAnalysis]:
    """Analyze student working for errors."""
    if not problem.student_working:
        return None

    system = load_prompt("prompts/v2/p4_working_analyzer.md")

    # Parse student working into steps
    student_steps = parse_student_working(problem.student_working)
    correct_steps = [
        {"description": s.description, "expression": s.expression, "result": s.result}
        for s in solution.steps
    ]

    # Deterministic arithmetic check first
    problem_givens = extract_givens(problem.problem_text)
    first_wrong, error_type, expected = find_first_arithmetic_error(student_steps, problem_givens)

    if first_wrong is None:
        # Check against correct solution
        first_wrong, error_type, expected = check_working_against_solution(student_steps, correct_steps)

    if first_wrong is None:
        return WorkingAnalysis(
            has_error=False,
            first_wrong_step_index=None,
            error_type=None,
            expected_step=None,
            explanation="No errors detected in student working."
        )

    # LLM analysis for classification
    student_text = format_steps(student_steps)
    correct_text = format_steps(correct_steps)

    user = f"""Problem: {problem.problem_text}
Correct Solution Steps:
{correct_text}

Student Working Steps:
{student_text}

First wrong step index (0-based): {first_wrong}
Error type hint: {error_type}
Expected correct step: {expected}

Analyze the student's working. Identify the FIRST wrong step, classify the error type,
and explain what the student should do differently. Return WorkingAnalysis JSON."""

    try:
        return call_json(system, user, WorkingAnalysis)
    except Exception:
        return WorkingAnalysis(
            has_error=True,
            first_wrong_step_index=first_wrong,
            error_type=error_type,
            expected_step=expected,
            explanation=f"Error at step {first_wrong + 1}: {error_type}. Expected: {expected}"
        )


def generate_targeted_hint(
    problem: ProblemInput,
    solution: Solution,
    analysis: WorkingAnalysis,
    model: Optional[str] = None
) -> Hint:
    """Generate targeted hint based on working analysis."""
    system = load_prompt("prompts/v2/p5_targeted_hint.md")

    level_names = {1: "Orient", 2: "Strategy"}
    level_name = level_names.get(problem.hint_level, "Orient")

    solution_text = ""
    for i, step in enumerate(solution.steps):
        solution_text += f"Step {i+1}: {step.description}"
        if step.expression:
            solution_text += f" | {step.expression}"
        if step.result:
            solution_text += f" = {step.result}"
        solution_text += "\n"
    solution_text += f"Final Answer: {solution.final_answer}\n"

    user = f"""Problem: {problem.problem_text}
Hint Level: {problem.hint_level} ({level_name})
Reference Solution:
{solution_text}

Student Working Analysis:
- First wrong step: {analysis.first_wrong_step_index + 1 if analysis.first_wrong_step_index is not None else 'N/A'}
- Error type: {analysis.error_type}
- Expected correct step: {analysis.expected_step}
- Explanation: {analysis.explanation}

Generate a TARGETED hint addressing this specific error at the requested level.
Follow level constraints strictly. Return ONLY valid JSON matching the Hint schema."""

    try:
        hint = call_json(system, user, Hint, model=model)
        return hint
    except Exception:
        return get_fallback_hint(problem.hint_level, problem.problem_text)


def parse_student_working(text: str) -> List[dict]:
    """Parse student working text into step dicts."""
    steps = []
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    for line in lines:
        # Try to split into description/expression/result
        step = {"description": line, "expression": None, "result": None}
        # Look for patterns like "3 + 4 = 7" or "x = 5"
        if '=' in line:
            parts = line.split('=')
            step["expression"] = parts[0].strip()
            step["result"] = parts[1].strip()
            step["description"] = f"Calculate {parts[0].strip()}"
        steps.append(step)
    return steps


def format_steps(steps: List[dict]) -> str:
    """Format steps for prompt."""
    out = ""
    for i, step in enumerate(steps):
        out += f"Step {i+1}: {step.get('description', '')}"
        if step.get('expression'):
            out += f" | {step['expression']}"
        if step.get('result'):
            out += f" = {step['result']}"
        out += "\n"
    return out


def extract_givens(text: str) -> List[float]:
    """Extract given numbers from problem text."""
    import re
    return [float(m) for m in re.findall(r'\b\d+\.?\d*\b', text)]


# --- Main Pipeline ---

def run_pipeline_v2(problem: ProblemInput) -> TutorResponse:
    """Run the V2 chained pipeline."""
    # Input gate (code)
    gate = input_gate_code_check(problem.problem_text)
    if not gate.allowed:
        fallback = get_fallback_hint(problem.hint_level, problem.problem_text)
        return TutorResponse(
            hint=fallback,
            leak_check_passed=False,
            working_analysis=None
        )

    # Hidden solver (x2 verification)
    solution = solve_and_verify(problem.problem_text)
    if not solution:
        fallback = get_fallback_hint(problem.hint_level, problem.problem_text)
        return TutorResponse(
            hint=fallback,
            leak_check_passed=False,
            working_analysis=None
        )

    # Generate hint with schema validation
    hint = generate_hint_v2(problem, solution, problem.hint_level)

    # Leak guard with regeneration
    hint, leak_passed = apply_leak_guard(problem, solution, hint)

    # Stretch: Working analysis + targeted hint
    working_analysis = None
    if problem.student_working and problem.hint_level in [1, 2]:
        working_analysis = analyze_working(problem, solution)
        if working_analysis and working_analysis.has_error:
            targeted_hint = generate_targeted_hint(problem, solution, working_analysis)
            # Apply leak guard to targeted hint too
            targeted_hint, _ = apply_leak_guard(problem, solution, targeted_hint)
            hint = targeted_hint

    return TutorResponse(
        hint=hint,
        leak_check_passed=leak_passed,
        working_analysis=working_analysis
    )