"""
Guardrails: input gate, leak check, refusal and fallback templates.
"""
import re
from typing import Optional, Tuple, List, Dict, Any


# --- Input Gate (code checks) ---

INJECTION_PATTERNS = [
    r"ignore\s+previous\s+instructions",
    r"ignore\s+all\s+instructions",
    r"system\s+prompt",
    r"reveal\s+the\s+solution",
    r"reveal\s+hidden",
    r"just\s+give\s+me\s+the\s+answer",
    r"act\s+as\s+",
]

NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
    "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
    "eighty": 80, "ninety": 90, "hundred": 100, "thousand": 1000,
    "million": 1000000, "billion": 1000000000,
}

# Refusal messages (to be used verbatim)
REFUSALS = {
    "empty": "I can't help with an empty problem. Please provide a math word problem.",
    "off_topic": "This doesn't look like a math word problem. Please provide a problem with numbers and a question.",
    "prompt_injection": "I can't process that request. Please provide a genuine math word problem.",
}

# Safe fallback hints
SAFE_FALLBACK = {
    1: "What information is given in the problem? What are you being asked to find?",
    2: "What mathematical concept or formula might apply here? What's the first step?",
    3: "Let me walk through the solution step by step.",
}


def input_gate_code(text: str) -> Optional[str]:
    """
    Code-based input gate checks.
    Returns rejection category ("empty", "off_topic", "prompt_injection") or None if allowed.
    """
    if not text or not text.strip():
        return "empty"

    text_stripped = text.strip()

    # Length checks
    if len(text_stripped) < 15:
        return "off_topic"
    if len(text_stripped) > 1500:
        return "off_topic"

    # Prompt injection check
    text_lower = text_stripped.lower()
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return "prompt_injection"

    # Check for at least one digit or number word
    has_digit = bool(re.search(r"\d", text_stripped))
    has_number_word = any(word in text_lower for word in NUMBER_WORDS.keys())

    if not has_digit and not has_number_word:
        return "off_topic"

    return None


# --- Leak Check (code checks) ---

PHRASE_BLOCKLIST = [
    "the answer is",
    "answer:",
    "so the result is",
    "final answer",
]


def _normalize_number_text(text: str) -> str:
    """Normalize numeric text: strip units, commas, currency symbols."""
    # Remove currency symbols
    text = re.sub(r"[\$\£\€\¥]", "", text)
    # Remove commas
    text = text.replace(",", "")
    # Remove units (anything after a number that's letters)
    text = re.sub(r"(\d+(?:\.\d+)?)\s*[a-zA-Z]+", r"\1", text)
    return text.strip()


def _extract_numbers_from_text(text: str) -> List[str]:
    """Extract all numbers (integers, decimals, fractions) as normalized strings."""
    numbers = []
    # Pattern for fractions (e.g., 3/4, 15/8)
    for match in re.finditer(r"\b(\d+)\s*/\s*(\d+)\b", text):
        num = int(match.group(1))
        den = int(match.group(2))
        if den != 0:
            numbers.append(f"{num}/{den}")
            # Also add decimal equivalent
            numbers.append(f"{num/den:.10f}".rstrip('0').rstrip('.'))
    # Pattern for decimals and integers
    for match in re.finditer(r"\b(\d+(?:\.\d+)?)\b", text):
        val = match.group(1)
        # Normalize: strip leading zeros but keep at least one digit
        val_norm = val.lstrip('0')
        if val_norm == '' or val_norm.startswith('.'):
            val_norm = '0' + val_norm
        numbers.append(val_norm)
    return numbers


def _number_to_words(n: float) -> List[str]:
    """Convert a number to possible word forms."""
    words = []
    # Integer form
    if n == int(n):
        words.append(str(int(n)))
    # Decimal form
    words.append(f"{n:.10f}".rstrip('0').rstrip('.'))
    # Word form for small integers
    if n == int(n) and 0 <= int(n) <= 20:
        for word, val in NUMBER_WORDS.items():
            if val == int(n):
                words.append(word)
    return words


def _get_answer_variants(answer: str) -> List[str]:
    """Build all variants of the answer for matching."""
    variants = set()
    normalized = _normalize_number_text(answer)
    variants.add(normalized)

    # Try to parse as number
    try:
        # Handle fractions
        if '/' in normalized:
            parts = normalized.split('/')
            num = float(parts[0])
            den = float(parts[1])
            if den != 0:
                val = num / den
                variants.update(_number_to_words(val))
                # Add fraction variants
                variants.add(f"{int(num)}/{int(den)}")
        else:
            val = float(normalized)
            variants.update(_number_to_words(val))
    except (ValueError, ZeroDivisionError):
        pass

    return list(variants)


def _get_last_step_result(solution: str) -> Optional[str]:
    """Extract the last step's result from a solution."""
    lines = solution.strip().split('\n')
    for line in reversed(lines):
        line = line.strip()
        if '=' in line:
            # Get RHS of last equation
            rhs = line.split('=')[-1].strip()
            return _normalize_number_text(rhs)
    return None


def leak_check_code(hint_text: str, solution: str, problem_text: str) -> Tuple[bool, str]:
    """
    Check if hint leaks the answer.
    Returns (is_leak, reason).
    """
    hint_lower = hint_text.lower()

    # Phrase blocklist check (always applies)
    for phrase in PHRASE_BLOCKLIST:
        if phrase.lower() in hint_lower:
            return True, f"Forbidden phrase detected: '{phrase}'"

    # Get answer variants
    answer_variants = _get_answer_variants(solution)

    # Get problem numbers (to allow numbers that appear in the problem)
    problem_numbers = set(_extract_numbers_from_text(problem_text))
    problem_normalized = _normalize_number_text(problem_text)

    # Check if answer number appears as standalone token in hint
    hint_numbers = set(_extract_numbers_from_text(hint_text))

    for variant in answer_variants:
        if variant in hint_numbers:
            # Check if this number appears in the problem text
            if variant not in problem_numbers:
                return True, f"Answer number '{variant}' appears in hint but not in problem"

    # Level 2 check: last step's result
    last_step_result = _get_last_step_result(solution)
    if last_step_result:
        last_step_variants = _get_answer_variants(last_step_result)
        for variant in last_step_variants:
            if variant in hint_numbers:
                if variant not in problem_numbers:
                    return True, f"Last step result '{variant}' appears in hint but not in problem"

    return False, "No leak detected"


def normalise_numeric_equal(a: str, b: str) -> bool:
    """
    Compare two solver outputs numerically.
    Normalizes both and checks if they represent the same value within tolerance.
    """
    try:
        a_norm = _normalize_number_text(a)
        b_norm = _normalize_number_text(b)

        # Try parsing as fractions first
        def parse_val(s: str) -> Optional[float]:
            if '/' in s:
                parts = s.split('/')
                return float(parts[0]) / float(parts[1])
            return float(s)

        a_val = parse_val(a_norm)
        b_val = parse_val(b_norm)

        if a_val is not None and b_val is not None:
            return abs(a_val - b_val) < 1e-6

        # Fallback to string comparison
        return a_norm == b_norm
    except (ValueError, ZeroDivisionError):
        return a == b