"""
Unit tests for pipeline_v2 with mocked call_llm.
"""
import pytest
import os
from dotenv import load_dotenv
from unittest.mock import patch, MagicMock

# Load .env for any tests that might need it
_here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_here, ".env"))

from pipeline_v2 import (
    start_problem,
    get_hint,
    can_unlock_level3,
    clear_debug_log,
)
from schemas import Solution, Step, Gate, Hint, LeakVerdict, WorkingAnalysis
from guardrails import SAFE_FALLBACK
from llm import ValidationFailure


# Mock solutions
MOCK_SOLUTION = Solution(
    steps=[
        Step(description="Subtract 4 from 15", expression="15 - 4", result="11"),
        Step(description="Add 7 to 11", expression="11 + 7", result="18"),
    ],
    final_answer="18",
    answer_rationale="15 - 4 + 7 = 18"
)

MOCK_HINT_L1 = Hint(
    level=1,
    content="What information is given? What are you asked to find?",
    guiding_question="What do you know and what do you need?",
    concept=None,
    sub_goal=None
)

MOCK_HINT_L2 = Hint(
    level=2,
    content="This is a multi-step addition and subtraction problem. First, find how many after giving away.",
    guiding_question=None,
    concept="multi-step arithmetic",
    sub_goal="15 - 4 = ?"
)

MOCK_HINT_L3 = Hint(
    level=3,
    content="Step 1: 15 - 4 = 11. Step 2: 11 + 7 = 18. Answer: 18.",
    guiding_question=None,
    concept=None,
    sub_goal=None
)


class MockCallLLM:
    """Mock call_llm to return predefined responses."""
    def __init__(self):
        self.responses = []
        self.call_count = 0

    def add_response(self, response):
        self.responses.append(response)

    def __call__(self, system, user, model=None, temperature=0.0, max_tokens=800):
        if self.call_count < len(self.responses):
            resp = self.responses[self.call_count]
            self.call_count += 1
            return resp
        return "{}"


class MockCallJSON:
    """Mock call_json to return predefined Pydantic objects or raise ValidationFailure."""
    def __init__(self):
        self.responses = []
        self.call_count = 0

    def add_response(self, response):
        self.responses.append(response)

    def __call__(self, system, user, schema_cls, model=None, temperature=0.0, max_tokens=800):
        if self.call_count < len(self.responses):
            resp = self.responses[self.call_count]
            self.call_count += 1
            if isinstance(resp, Exception):
                raise resp
            return resp
        # Default fallback
        if schema_cls.__name__ == "Solution":
            return MOCK_SOLUTION
        elif schema_cls.__name__ == "Gate":
            return Gate(allowed=True, reason="ok", category="math_word_problem")
        elif schema_cls.__name__ == "Hint":
            return MOCK_HINT_L1
        elif schema_cls.__name__ == "LeakVerdict":
            return LeakVerdict(has_leak=False, leak_type=None, explanation="clean", severity="none")
        elif schema_cls.__name__ == "WorkingAnalysis":
            return WorkingAnalysis(has_error=False, first_wrong_step_index=None, error_type=None, expected_step=None, explanation="ok")
        return MagicMock()


# ===== Tests for start_problem =====

@patch('pipeline_v2.call_json')
def test_start_problem_success(mock_call_json):
    """Test successful problem start with consistent solutions."""
    mock = MockCallJSON()
    mock.add_response(Gate(allowed=True, reason="ok", category="math_word_problem"))  # P0
    mock.add_response(MOCK_SOLUTION)  # P1 temp 0
    mock.add_response(MOCK_SOLUTION)  # P1 temp 0.7
    mock_call_json.side_effect = mock

    clear_debug_log()
    result = start_problem("Sarah has 15 apples. She gives 4 away and buys 7 more. How many?")

    assert result["status"] == "ok"
    assert "solution" in result
    assert result["solution"].final_answer == "18"


@patch('pipeline_v2.call_json')
def test_start_problem_code_gate_blocks(mock_call_json):
    """Test code gate blocks empty input."""
    clear_debug_log()
    result = start_problem("")
    assert result["status"] == "refused"
    assert "empty" in result["refusal_message"].lower()


@patch('pipeline_v2.call_json')
def test_start_problem_p0_blocks(mock_call_json):
    """Test P0 classifier blocks off-topic."""
    mock = MockCallJSON()
    mock.add_response(Gate(allowed=False, reason="off topic", category="off_topic"))
    mock_call_json.side_effect = mock

    clear_debug_log()
    result = start_problem("Write a poem about math")
    assert result["status"] == "refused"
    assert "math word problem" in result["refusal_message"].lower()


@patch('pipeline_v2.call_json')
def test_start_problem_inconsistent_solutions(mock_call_json):
    """Test inconsistent solutions returns unverifiable."""
    sol1 = Solution(steps=[], final_answer="18", answer_rationale="ok")
    sol2 = Solution(steps=[], final_answer="20", answer_rationale="ok")

    mock = MockCallJSON()
    mock.add_response(Gate(allowed=True, reason="ok", category="math_word_problem"))
    mock.add_response(sol1)
    mock.add_response(sol2)
    mock_call_json.side_effect = mock

    clear_debug_log()
    result = start_problem("Sarah has 15 apples. She gives 4 away and buys 7 more. How many?")
    assert result["status"] == "refused"
    assert "unverifiable" in result["refusal_message"].lower()


@patch('pipeline_v2.call_json')
def test_start_problem_p1_validation_failure(mock_call_json):
    """Test P1 validation failure returns unverifiable."""
    mock = MockCallJSON()
    mock.add_response(Gate(allowed=True, reason="ok", category="math_word_problem"))
    mock.add_response(ValidationFailure("bad json", "{}"))
    mock_call_json.side_effect = mock

    clear_debug_log()
    result = start_problem("Sarah has 15 apples. She gives 4 away and buys 7 more. How many?")
    assert result["status"] == "refused"
    assert "unverifiable" in result["refusal_message"].lower()


# ===== Tests for get_hint =====

@patch('pipeline_v2.call_json')
def test_get_hint_level1_passes(mock_call_json):
    """Test level 1 hint passes leak checks."""
    mock = MockCallJSON()
    mock.add_response(MOCK_HINT_L1)  # P2
    mock.add_response(LeakVerdict(has_leak=False, leak_type=None, explanation="clean", severity="none"))  # P3
    mock_call_json.side_effect = mock

    clear_debug_log()
    result = get_hint("Sarah has 15 apples...", MOCK_SOLUTION, 1)

    assert result["guard_status"] == "passed"
    assert result["attempts"] == 1
    assert "What information" in result["hint"]


@patch('pipeline_v2.call_json')
def test_get_hint_level1_leak_then_regenerate_then_pass(mock_call_json):
    """Test level 1: leak detected, regenerate, then pass."""
    mock = MockCallJSON()
    # First attempt: leak
    mock.add_response(Hint(level=1, content="Add 15 and 4 to get 19", guiding_question="Try adding"))
    mock.add_response(LeakVerdict(has_leak=True, leak_type="operation", explanation="names operation", severity="major"))
    # Second attempt: clean
    mock.add_response(MOCK_HINT_L1)
    mock.add_response(LeakVerdict(has_leak=False, leak_type=None, explanation="clean", severity="none"))
    mock_call_json.side_effect = mock

    clear_debug_log()
    result = get_hint("Sarah has 15 apples...", MOCK_SOLUTION, 1)

    assert result["guard_status"] == "regenerated_1"
    assert result["attempts"] == 2
    assert "information is given" in result["hint"]


@patch('pipeline_v2.call_json')
def test_get_hint_level1_leak_three_times_then_fallback(mock_call_json):
    """Test level 1: leak 3 times (2 regens + initial) then fallback."""
    mock = MockCallJSON()
    # 3 attempts all leaking
    for _ in range(3):
        mock.add_response(Hint(level=1, content="The answer is 18"))
        mock.add_response(LeakVerdict(has_leak=True, leak_type="final_answer", explanation="gives answer", severity="major"))
    mock_call_json.side_effect = mock

    clear_debug_log()
    result = get_hint("Sarah has 15 apples...", MOCK_SOLUTION, 1)

    assert result["guard_status"] == "fallback"
    assert result["attempts"] == 3
    assert result["hint"] == SAFE_FALLBACK[1]


@patch('pipeline_v2.call_json')
def test_get_hint_invalid_json_twice_then_fallback(mock_call_json):
    """Test invalid JSON twice (call_json retries once) then fallback."""
    mock = MockCallJSON()
    # First call: ValidationFailure (call_json retries once internally)
    # Second call: ValidationFailure again -> fallback
    mock.add_response(ValidationFailure("bad json", "{}"))
    mock.add_response(ValidationFailure("bad json again", "{}"))
    mock_call_json.side_effect = mock

    clear_debug_log()
    result = get_hint("Sarah has 15 apples...", MOCK_SOLUTION, 1)

    assert result["guard_status"] == "fallback"
    assert result["hint"] == SAFE_FALLBACK[1]


@patch('pipeline_v2.call_json')
def test_get_hint_level3_no_leak_check(mock_call_json):
    """Test level 3 has no leak check."""
    mock = MockCallJSON()
    mock.add_response(MOCK_HINT_L3)
    mock_call_json.side_effect = mock

    clear_debug_log()
    result = get_hint("Sarah has 15 apples...", MOCK_SOLUTION, 3)

    assert result["guard_status"] == "passed"
    assert result["attempts"] == 1
    assert "Step 1" in result["hint"]


# ===== Tests for can_unlock_level3 =====

def test_can_unlock_level3_both_shown():
    assert can_unlock_level3([1, 2], 0) is True

def test_can_unlock_level3_only_one_shown():
    assert can_unlock_level3([1], 0) is False
    assert can_unlock_level3([2], 0) is False

def test_can_unlock_level3_attempt_made():
    assert can_unlock_level3([], 1) is True
    assert can_unlock_level3([1], 1) is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])