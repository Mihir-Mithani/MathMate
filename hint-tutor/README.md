# Hint-Based Math Tutor

A progressive hint system for math word problems that guides students without revealing answers early.

## Setup

```bash
cd hint-tutor
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your NVIDIA_API_KEY (from NVIDIA NIM)
```

## Run

```bash
streamlit run app.py
```

## Tabs

1. **Tutor** — Interactive hint ladder (Level 1 Orient → Level 2 Strategy → Level 3 Walkthrough)
2. **Compare** — Side-by-side V1 (naive) vs V2 (chained pipeline) on same input
3. **Evaluate** — Run evaluation suite on test cases
4. **Prompt History** — Timestamped prompt versions from Git

## Project Structure

```
hint-tutor/
├── app.py                 # Streamlit app (4 tabs)
├── llm.py                 # NVIDIA NIM (OpenAI-compatible) wrapper (retry, timeout, JSON validation)
├── schemas.py             # Pydantic models
├── pipeline_v1.py         # Naive baseline pipeline
├── pipeline_v2.py         # Final chained pipeline
├── guardrails.py          # Input gate, leak check, fallbacks
├── arithmetic_check.py    # Deterministic step verification
├── prompts/
│   ├── v1/hint_naive.md
│   └── v2/p0_input_gate.md p1_solver.md p2_hint_generator.md p3_leak_judge.md
│       p4_working_analyzer.md p5_targeted_hint.md
├── eval/
│   ├── problems.json          # 10+ test problems
│   ├── wrong_working.json     # Student working with errors
│   ├── guardrail_cases.json   # Off-topic, invalid inputs
│   └── run_eval.py            # Evaluation runner
├── results/                 # Evaluation outputs
├── PROMPT_HISTORY.md        # Timestamped prompt changes
└── tests/test_guardrails.py
```

## Hint Ladder

- **Level 1 (Orient)**: Restate problem, identify givens, ask one guiding question. No operations, formulas, numbers, or answer.
- **Level 2 (Strategy)**: Name concept/approach, first sub-goal or equation setup using givens. No final step result or answer.
- **Level 3 (Walkthrough)**: Full step-by-step solution with final answer. Unlocks only after Levels 1-2 shown or student attempt.

## Pipeline V2

```
Input Gate (code + LLM) → Hidden Solver (×2, verify consistency)
    → Hint Generator (level N) → Schema Validation (retry once)
    → Leak Guard (code + LLM judge) → Regenerate ≤2× with feedback → Fallback
    → Show Hint
```

**Stretch branch**: Student working → Arithmetic Checker + Working Analyzer (first wrong step, error type) → Targeted Hint (same leak guard).

## Evaluation

Primary metric: **Leak Rate** (fraction of Level 1-2 hints that reveal answer/operation/number) + **Hint Quality** (LLM judge on helpfulness).

Run: `python eval/run_eval.py`