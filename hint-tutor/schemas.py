"""
Pydantic models for the Hint-Based Math Tutor.
"""
from typing import Literal, Optional, List
from pydantic import BaseModel, Field


class Step(BaseModel):
    """A single step in a solution."""
    description: str = Field(..., description="What this step does")
    expression: Optional[str] = Field(None, description="Mathematical expression if applicable")
    result: Optional[str] = Field(None, description="Result of this step")


class Solution(BaseModel):
    """Complete solution to a problem."""
    steps: List[Step] = Field(..., description="Ordered solution steps")
    final_answer: str = Field(..., description="The final answer")
    answer_rationale: str = Field(..., description="Why this is the answer")


class Gate(BaseModel):
    """Input gate decision."""
    allowed: bool = Field(..., description="Whether input passes the gate")
    reason: str = Field(..., description="Reason for decision")
    category: Literal["math_word_problem", "off_topic", "invalid", "incomplete"] = Field(
        ..., description="Input category"
    )


class Hint(BaseModel):
    """A hint at a specific level."""
    level: Literal[1, 2, 3] = Field(..., description="Hint level (1=Orient, 2=Strategy, 3=Walkthrough)")
    content: str = Field(..., description="The hint text")
    guiding_question: Optional[str] = Field(None, description="Guiding question for Level 1")
    concept: Optional[str] = Field(None, description="Named concept for Level 2")
    sub_goal: Optional[str] = Field(None, description="First sub-goal for Level 2")


class LeakVerdict(BaseModel):
    """Leak detection verdict for Levels 1-2."""
    has_leak: bool = Field(..., description="Whether the hint leaks forbidden info")
    leak_type: Optional[Literal["operation", "formula", "computed_number", "final_answer", "other"]] = Field(
        None, description="Type of leak if any"
    )
    explanation: str = Field(..., description="Explanation of the verdict")
    severity: Literal["none", "minor", "major"] = Field(..., description="Severity of leak")


class WorkingAnalysis(BaseModel):
    """Analysis of student's working."""
    has_error: bool = Field(..., description="Whether an error was found")
    first_wrong_step_index: Optional[int] = Field(None, description="Index of first wrong step (0-based)")
    error_type: Optional[Literal["arithmetic", "conceptual", "setup", "unit", "other"]] = Field(
        None, description="Type of error"
    )
    expected_step: Optional[str] = Field(None, description="What the correct step should be")
    explanation: str = Field(..., description="Explanation of the analysis")


class ProblemInput(BaseModel):
    """Input problem from student."""
    problem_text: str = Field(..., description="The word problem text")
    student_working: Optional[str] = Field(None, description="Student's working if provided")
    hint_level: int = Field(default=1, ge=1, le=3, description="Requested hint level")


class TutorResponse(BaseModel):
    """Complete response from the tutor."""
    hint: Hint
    leak_check_passed: bool
    working_analysis: Optional[WorkingAnalysis] = None