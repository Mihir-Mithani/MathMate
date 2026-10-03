"""
V1 Naive Baseline Pipeline.
Single prompt with template filling, no gates, no hidden solution, no leak check.
"""
from llm import call_llm


def load_prompt(path: str) -> str:
    """Load prompt from file."""
    with open(path, 'r') as f:
        return f.read()


def get_hint_v1(problem: str, level: int) -> str:
    """Fill template and call LLM once. Intentionally naive baseline."""
    template = load_prompt("prompts/v1/hint_naive.md")
    prompt = template.replace("{{problem}}", problem).replace("{{level}}", str(level))
    return call_llm("", prompt)