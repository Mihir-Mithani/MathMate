"""
Evaluation runner for Hint-Based Math Tutor.
Compares V1 vs V2 on leak rate, hint quality, and guardrail accuracy.
"""
import json
import os
import sys
from typing import List, Dict, Any
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline_v1 import run_pipeline_v1
from pipeline_v2 import run_pipeline_v2
from schemas import ProblemInput, Gate
from guardrails import input_gate_code_check
from llm import get_counters, reset_counters


def load_json(path: str) -> List[Dict]:
    with open(path, 'r') as f:
        return json.load(f)


def evaluate_guardrails() -> Dict[str, Any]:
    """Evaluate input gate accuracy."""
    cases = load_json("eval/guardrail_cases.json")
    results = []

    for case in cases:
        gate = input_gate_code_check(case["text"])
        passed = gate.category == case["expected_category"]
        results.append({
            "id": case["id"],
            "input": case["text"][:50],
            "expected": case["expected_category"],
            "got": gate.category,
            "passed": passed
        })

    accuracy = sum(r["passed"] for r in results) / len(results)
    return {
        "accuracy": accuracy,
        "details": results
    }


def evaluate_leak_rate(pipeline_func, problems: List[Dict], version: str) -> Dict[str, Any]:
    """Evaluate leak rate for Levels 1-2."""
    results = []
    leaks = 0
    total_hints = 0

    for prob in problems:
        for level in [1, 2]:
            problem = ProblemInput(
                problem_text=prob["text"],
                hint_level=level
            )
            response = pipeline_func(problem)
            total_hints += 1
            leaked = not response.leak_check_passed
            if leaked:
                leaks += 1
            results.append({
                "problem_id": prob["id"],
                "level": level,
                "leaked": leaked,
                "hint_preview": response.hint.content[:100]
            })

    leak_rate = leaks / total_hints if total_hints > 0 else 0
    return {
        "version": version,
        "leak_rate": leak_rate,
        "leaks": leaks,
        "total_hints": total_hints,
        "details": results
    }


def evaluate_hint_quality(pipeline_func, problems: List[Dict], version: str) -> Dict[str, Any]:
    """Evaluate hint quality via LLM judge (simplified: checks constraints)."""
    results = []
    quality_scores = []

    for prob in problems:
        for level in [1, 2, 3]:
            problem = ProblemInput(
                problem_text=prob["text"],
                hint_level=level
            )
            response = pipeline_func(problem)
            hint = response.hint

            # Check level-specific constraints
            score = 1.0
            issues = []

            if level == 1:
                # Should have guiding question
                if not hint.guiding_question:
                    score -= 0.3
                    issues.append("missing_guiding_question")
                # Should not have concept/sub_goal
                if hint.concept:
                    score -= 0.2
                    issues.append("has_concept")
                if hint.sub_goal:
                    score -= 0.2
                    issues.append("has_sub_goal")

            elif level == 2:
                # Should have concept and sub_goal
                if not hint.concept:
                    score -= 0.3
                    issues.append("missing_concept")
                if not hint.sub_goal:
                    score -= 0.3
                    issues.append("missing_sub_goal")
                # Should not have guiding_question
                if hint.guiding_question:
                    score -= 0.1
                    issues.append("has_guiding_question")

            elif level == 3:
                # Should have full content
                if len(hint.content) < 50:
                    score -= 0.5
                    issues.append("too_short")

            quality_scores.append(max(0, score))
            results.append({
                "problem_id": prob["id"],
                "level": level,
                "score": max(0, score),
                "issues": issues
            })

    avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0
    return {
        "version": version,
        "avg_quality": avg_quality,
        "details": results
    }


def evaluate_working_analysis(pipeline_func, wrong_working: List[Dict]) -> Dict[str, Any]:
    """Evaluate working analysis accuracy (V2 only)."""
    results = []
    correct_detections = 0
    total_with_errors = 0

    for case in wrong_working:
        if case["error_type"] == "none":
            continue

        total_with_errors += 1

        # Find the problem text
        problems = load_json("eval/problems.json")
        prob_text = next((p["text"] for p in problems if p["id"] == case["problem_id"]), "")

        problem = ProblemInput(
            problem_text=prob_text,
            student_working=case["working"],
            hint_level=2  # Use level 2 for targeted hints
        )
        response = pipeline_func(problem)

        analysis = response.working_analysis
        if analysis and analysis.has_error:
            # Check if detected error type matches
            type_match = analysis.error_type == case["error_type"]
            step_match = analysis.first_wrong_step_index is not None
            if type_match and step_match:
                correct_detections += 1
                results.append({
                    "problem_id": case["problem_id"],
                    "detected": True,
                    "error_type_match": type_match,
                    "expected_type": case["error_type"],
                    "detected_type": analysis.error_type
                })
            else:
                results.append({
                    "problem_id": case["problem_id"],
                    "detected": False,
                    "error_type_match": type_match,
                    "expected_type": case["error_type"],
                    "detected_type": analysis.error_type if analysis else None
                })
        else:
            results.append({
                "problem_id": case["problem_id"],
                "detected": False,
                "error_type_match": False,
                "expected_type": case["error_type"],
                "detected_type": None
            })

    detection_rate = correct_detections / total_with_errors if total_with_errors > 0 else 0
    return {
        "detection_rate": detection_rate,
        "correct_detections": correct_detections,
        "total_with_errors": total_with_errors,
        "details": results
    }


def evaluate_format_validity() -> Dict[str, Any]:
    """Get format validity metrics from LLM counters."""
    total, first_try = get_counters()
    return {
        "total_calls": total,
        "first_try_validations": first_try,
        "format_validity_rate": first_try / total if total > 0 else 0
    }


def main():
    print("=" * 60)
    print("HINT-BASED MATH TUTOR - EVALUATION")
    print("=" * 60)

    problems = load_json("eval/problems.json")
    wrong_working = load_json("eval/wrong_working.json")

    # Reset counters
    reset_counters()

    # 1. Guardrails (same for both versions)
    print("\n[1/5] Evaluating Guardrails...")
    guardrail_results = evaluate_guardrails()
    print(f"  Guardrail Accuracy: {guardrail_results['accuracy']:.2%}")

    # 2. V1 Leak Rate
    print("\n[2/5] Evaluating V1 Leak Rate...")
    reset_counters()
    v1_leak = evaluate_leak_rate(run_pipeline_v1, problems, "V1")
    print(f"  V1 Leak Rate: {v1_leak['leak_rate']:.2%} ({v1_leak['leaks']}/{v1_leak['total_hints']})")

    # 3. V2 Leak Rate
    print("\n[3/5] Evaluating V2 Leak Rate...")
    reset_counters()
    v2_leak = evaluate_leak_rate(run_pipeline_v2, problems, "V2")
    print(f"  V2 Leak Rate: {v2_leak['leak_rate']:.2%} ({v2_leak['leaks']}/{v2_leak['total_hints']})")

    # 4. V1 Hint Quality
    print("\n[4/5] Evaluating V1 Hint Quality...")
    reset_counters()
    v1_quality = evaluate_hint_quality(run_pipeline_v1, problems, "V1")
    print(f"  V1 Avg Quality: {v1_quality['avg_quality']:.2f}")

    # 5. V2 Hint Quality
    print("\n[5/5] Evaluating V2 Hint Quality...")
    reset_counters()
    v2_quality = evaluate_hint_quality(run_pipeline_v2, problems, "V2")
    print(f"  V2 Avg Quality: {v2_quality['avg_quality']:.2f}")

    # 6. Working Analysis (V2 only)
    print("\n[6/6] Evaluating V2 Working Analysis...")
    reset_counters()
    working_results = evaluate_working_analysis(run_pipeline_v2, wrong_working)
    print(f"  V2 Detection Rate: {working_results['detection_rate']:.2%}")

    # Format Validity
    fmt = evaluate_format_validity()
    print(f"\nFormat Validity: {fmt['format_validity_rate']:.2%} ({fmt['first_try_validations']}/{fmt['total_calls']})")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Guardrail Accuracy:     {guardrail_results['accuracy']:.2%}")
    print(f"V1 Leak Rate:           {v1_leak['leak_rate']:.2%}")
    print(f"V2 Leak Rate:           {v2_leak['leak_rate']:.2%}")
    print(f"V1 Hint Quality:        {v1_quality['avg_quality']:.2f}")
    print(f"V2 Hint Quality:        {v2_quality['avg_quality']:.2f}")
    print(f"V2 Working Detection:   {working_results['detection_rate']:.2%}")
    print(f"Format Validity:        {fmt['format_validity_rate']:.2%}")

    # Save results
    os.makedirs("eval/results", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results = {
        "timestamp": timestamp,
        "guardrails": guardrail_results,
        "v1_leak": v1_leak,
        "v2_leak": v2_leak,
        "v1_quality": v1_quality,
        "v2_quality": v2_quality,
        "working_analysis": working_results,
        "format_validity": fmt
    }
    output_path = f"eval/results/eval_{timestamp}.json"
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {output_path}")

    # Also save CSV for easy viewing
    import csv
    csv_path = f"eval/results/eval_{timestamp}.csv"
    with open(csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Metric", "V1", "V2"])
        writer.writerow(["Leak Rate", f"{v1_leak['leak_rate']:.2%}", f"{v2_leak['leak_rate']:.2%}"])
        writer.writerow(["Hint Quality", f"{v1_quality['avg_quality']:.2f}", f"{v2_quality['avg_quality']:.2f}"])
        writer.writerow(["Working Detection", "N/A", f"{working_results['detection_rate']:.2%}"])
        writer.writerow(["Format Validity", f"{fmt['format_validity_rate']:.2%}", f"{fmt['format_validity_rate']:.2%}"])
    print(f"CSV saved to {csv_path}")


if __name__ == "__main__":
    main()