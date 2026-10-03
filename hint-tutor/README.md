# Hint-Based Math Tutor (Problem 13)

A progressive hint system for math word problems that guides students without revealing answers early.

## Quick Start (Local)

```bash
cd hint-tutor
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your NVIDIA_API_KEY (from NVIDIA NIM)
streamlit run app.py
```

## Deploy to Streamlit Community Cloud

1. **Push this folder (`hint-tutor/`) to a GitHub repo**
2. Go to https://share.streamlit.io → **New app**
3. Select your repo, branch `main`, main file: `hint-tutor/app.py`
4. Click **Advanced settings** → **Secrets** and add:
   ```toml
   NVIDIA_API_KEY = "nvapi-xxxxxxxxxxxx"
   MODEL_MAIN = "nvidia/nemotron-3-super-120b-a12b"
   MODEL_FAST = "nvidia/nemotron-3-super-120b-a12b"
   ```
5. **Deploy** — Streamlit installs from `requirements.txt` and launches.

> **Note**: The `.env` file is in `.gitignore` and should NOT be committed. Use Streamlit Secrets for API keys.

## App Features

**Single Tutor tab** with V2 chained pipeline:
- **Progressive hints**: Level 1 (Orient) → Level 2 (Strategy) → Level 3 (Walkthrough)
- **Level locking**: L2 requires L1; L3 requires L1+L2 or student attempt
- **Guard badges**: Passed / Regenerated N× / Safe fallback
- **Working check** (stretch): Paste working → analyzes first wrong step → targeted hint
- **Final answer check**: Normalized numeric comparison
- **History sidebar**: Timestamped log of all problems + hints in this session
- **Random problems**: 6 extra problems not in eval set
- **Debug panel**: Hidden solution + LLM call log (toggle in sidebar)

## Project Structure

```
hint-tutor/
├── app.py                      # Streamlit app (Tutor tab + history sidebar)
├── .streamlit/config.toml      # Streamlit theme/server config
├── llm.py                      # NVIDIA NIM wrapper (retry, timeout, JSON validation)
├── schemas.py                  # Pydantic models
├── pipeline_v1.py              # Naive baseline (for eval only)
├── pipeline_v2.py              # Production V2 chained pipeline
├── guardrails.py               # Input gate, leak check, fallbacks
├── arithmetic_check.py         # Deterministic step verification (sympy)
├── prompts/
│   ├── v1/hint_naive.md
│   └── v2/p0_input_gate.md p1_solver.md p2_hint_generator.md p3_leak_judge.md
│       p4_working_analyzer.md p5_targeted_hint.md
├── eval/
│   ├── problems.json           # 12 test problems
│   ├── wrong_working.json      # 12 labeled working cases
│   ├── guardrail_cases.json    # 7 guardrail tests
│   └── run_eval.py             # Evaluation runner (--version v1|v2|both)
├── results/                    # Evaluation outputs
├── PROMPT_HISTORY.md           # Timestamped prompt changes (git log format)
├── requirements.txt
├── .env.example
├── .gitignore
└── tests/
    ├── test_guardrails.py
    └── test_pipeline_v2.py
```

## Hint Ladder

| Level | Name | Allowed | Forbidden |
|-------|------|---------|-----------|
| 1 | Orient | Restate givens/ask, one guiding question | Operations, formulas, computed numbers, answer |
| 2 | Strategy | Concept name, first sub-goal/equation setup | Final step result, answer |
| 3 | Walkthrough | Full solution + answer | — |

## Pipeline V2 (Chained)

```
Input Gate (code + LLM P0)
    → Hidden Solver P1 (×2, temp 0 & 0.7, verify final_answer)
    → Hint Generator P2 (level N, schema validation retry)
    → Leak Guard: Code check → LLM Judge P3 (if L1/L2)
        → Regenerate ≤2× with feedback → Safe Fallback
    → Show Hint
```

**Stretch**: Student working → Arithmetic Checker + Working Analyzer P4 → Targeted Hint P5 (same leak guard)

## Evaluation

Run locally:
```bash
python eval/run_eval.py --version both
```

Metrics:
- **M1 Leak Rate L1-L2** (V1 vs V2, with/without guard)
- **M2 Wrong-Step Accuracy** (V2 analyze_working vs labels; V1 baseline)
- **M3 Format-Validity Rate** (first-try Pydantic success / total LLM calls)
- **Guardrail Suite** (code + P0 on 7 cases)

Outputs: `eval/results/leak_v1.csv`, `leak_v2.csv`, `wrong_step_v1.csv`, `wrong_step_v2.csv`, `guardrails.csv`, `summary_HHMM.md`

## Prompt Discipline

All prompts live in versioned `.md` files under `prompts/`. Changes logged in `PROMPT_HISTORY.md` with format:
```
prompt(<card>): <what changed> | why: <failure it fixes> | vX.Y
```