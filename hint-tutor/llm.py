"""
LLM wrapper for NVIDIA NIM API (OpenAI-compatible) with retry, timeout, and JSON validation.
"""
import os
import time
from typing import Type, TypeVar, Optional
from openai import OpenAI, APIError, APITimeoutError, RateLimitError
from pydantic import BaseModel, ValidationError
from dotenv import load_dotenv

# Load .env from the package directory (where this file lives)
_here = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_here, ".env"))

T = TypeVar('T', bound=BaseModel)

# Module-level counters for Format-Validity metric
_total_calls = 0
_first_try_validations = 0


def get_counters() -> tuple[int, int]:
    """Return (total_calls, first_try_validations)."""
    return _total_calls, _first_try_validations


def reset_counters() -> None:
    """Reset the module-level counters."""
    global _total_calls, _first_try_validations
    _total_calls = 0
    _first_try_validations = 0


def _get_client() -> OpenAI:
    api_key = os.getenv("NVIDIA_API_KEY")
    if not api_key:
        raise RuntimeError("NVIDIA_API_KEY not set in environment")
    return OpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=api_key
    )


def _get_model(model: Optional[str] = None) -> str:
    if model:
        return model
    return os.getenv("MODEL_MAIN", "nvidia/nemotron-3-ultra-550b-a55b")


def call_llm(
    system: str,
    user: str,
    model: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: int = 800,
) -> str:
    """
    Call the LLM with retry logic.
    Retries twice on API errors with 30s timeout.
    Returns the text response.
    """
    global _total_calls
    _total_calls += 1

    client = _get_client()
    model_name = _get_model(model)

    for attempt in range(3):  # 1 initial + 2 retries
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user}
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=30.0,
                stream=False
            )
            # Extract text from response
            if response.choices and len(response.choices) > 0:
                return response.choices[0].message.content or ""
            return ""
        except (APIError, APITimeoutError, RateLimitError) as e:
            if attempt == 2:  # Last attempt
                raise
            time.sleep(1.0 * (attempt + 1))  # Brief backoff

    return ""


def _strip_code_fences(text: str) -> str:
    """Remove markdown code fences from text."""
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


class ValidationFailure(Exception):
    """Raised when JSON validation fails after retry."""
    def __init__(self, message: str, raw_output: str):
        super().__init__(message)
        self.raw_output = raw_output


def call_json(
    system: str,
    user: str,
    schema_cls: Type[T],
    model: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: int = 800,
) -> T:
    """
    Call LLM and parse/validate JSON against a Pydantic model.
    Strips markdown code fences.
    On validation failure, retries ONCE with error feedback.
    Returns validated model instance.
    Raises ValidationFailure if still invalid after retry.
    """
    global _first_try_validations

    # First attempt
    raw = call_llm(system, user, model, temperature, max_tokens)
    cleaned = _strip_code_fences(raw)

    try:
        parsed = schema_cls.model_validate_json(cleaned)
        _first_try_validations += 1
        return parsed
    except ValidationError as e:
        # Retry once with error feedback
        retry_user = (
            f"{user}\n\n"
            f"Your last output failed validation: {e}. "
            f"Return valid JSON only matching the schema."
        )
        raw2 = call_llm(system, retry_user, model, temperature, max_tokens)
        cleaned2 = _strip_code_fences(raw2)

        try:
            parsed2 = schema_cls.model_validate_json(cleaned2)
            return parsed2
        except ValidationError as e2:
            raise ValidationFailure(
                f"JSON validation failed after retry: {e2}",
                raw2
            )