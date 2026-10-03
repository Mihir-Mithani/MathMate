"""
Deterministic arithmetic checker for student working steps.
Uses sympy for safe expression evaluation.
"""
import re
from typing import List, Dict, Optional
from sympy import sympify, SympifyError, N


def _preprocess_expression(expr: str) -> str:
    """Convert common math notation to sympy-compatible."""
    expr = expr.strip()
    # Replace multiplication signs
    expr = expr.replace('×', '*').replace('·', '*')
    # Replace division signs
    expr = expr.replace('÷', '/')
    # Handle "of" as multiplication (e.g., "20% of 100")
    expr = re.sub(r'\bof\b', '*', expr, flags=re.IGNORECASE)
    # Handle percent
    expr = re.sub(r'(\d+(?:\.\d+)?)\s*%', r'(\1/100)', expr)
    # Handle implicit multiplication (e.g., "2x" -> "2*x")
    expr = re.sub(r'(\d)([a-zA-Z])', r'\1*\2', expr)
    # Handle spaces as multiplication between number and variable/paren
    expr = re.sub(r'(\d)\s+([a-zA-Z\(])', r'\1*\2', expr)
    return expr


def check_working(working_text: str) -> List[Dict[str, any]]:
    """
    Check each equation line in student working.
    Returns list of {line, correct, expected} for each line.
    """
    results = []

    # Split on newlines, semicolons, commas (but not inside numbers)
    # First, normalize line breaks
    text = working_text.replace(';', '\n').replace(',', '\n')
    lines = [line.strip() for line in text.split('\n') if line.strip()]

    for line in lines:
        # Check if line looks like an equation with =
        if '=' not in line:
            results.append({
                "line": line,
                "correct": None,
                "expected": None,
                "reason": "Not an equation"
            })
            continue

        parts = line.split('=')
        if len(parts) != 2:
            results.append({
                "line": line,
                "correct": None,
                "expected": None,
                "reason": "Multiple equals signs"
            })
            continue

        lhs = parts[0].strip()
        rhs = parts[1].strip()

        # Try to evaluate both sides
        try:
            lhs_processed = _preprocess_expression(lhs)
            rhs_processed = _preprocess_expression(rhs)

            lhs_val = sympify(lhs_processed, evaluate=True)
            rhs_val = sympify(rhs_processed, evaluate=True)

            # Check if both are numeric
            if lhs_val.is_number and rhs_val.is_number:
                lhs_float = float(N(lhs_val))
                rhs_float = float(N(rhs_val))
                correct = abs(lhs_float - rhs_float) < 1e-6
                expected = str(rhs_float) if not correct else None
                results.append({
                    "line": line,
                    "correct": correct,
                    "expected": expected,
                    "reason": "Numeric mismatch" if not correct else "OK"
                })
            else:
                # Non-numeric (has variables) - can't verify
                results.append({
                    "line": line,
                    "correct": None,
                    "expected": None,
                    "reason": "Contains variables"
                })
        except (SympifyError, TypeError, ValueError, ZeroDivisionError) as e:
            results.append({
                "line": line,
                "correct": None,
                "expected": None,
                "reason": f"Parse error: {str(e)}"
            })

    return results