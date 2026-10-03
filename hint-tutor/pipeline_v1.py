"""
V1 Naive Baseline Pipeline.
Single prompt with template filling, no gates, no hidden solution, no leak check.
"""
import os
from llm import call_llm

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROMPTS_DIR = os.path.join(_HERE, "prompts")


def load_prompt(relative_path: str) -> str:
    """Load prompt from file using absolute path."""
    full_path = os.path.join(_PROMPTS_DIR, relative_path)
    with open(full_path, 'r') as f:
        return f.read()


def get_hint_v1(problem: str, level: int) -> str:
    """Fill template and call LLM once. Intentionally naive baseline."""
    template = load_prompt("v1/hint_naive.md")
    prompt = template.replace("{{problem}}", problem).replace("{{level}}", str(level))
    return call_llm("", prompt)