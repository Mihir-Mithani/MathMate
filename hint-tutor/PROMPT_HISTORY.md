# Prompt History

Timestamped log of all prompt changes. Format: `prompt(<card>): <what changed> | why: <failure it fixes> | vX.Y`

---

## 2024-10-03 11:00 - Initial Scaffold

### prompt(v1/hint_naive): Initial naive hint prompt | why: baseline for comparison | v1.0
### prompt(v1/solver): Initial solver prompt | why: baseline for comparison | v1.0

### prompt(v2/p0_input_gate): Initial input gate classifier | why: guardrail for invalid/off-topic input | v2.0
### prompt(v2/p1_solver): Initial solver for V2 | why: hidden solver with consistent output | v2.0
### prompt(v2/p2_hint_generator): Initial hint generator with level constraints | why: structured hint generation | v2.0
### prompt(v2/p3_leak_judge): Initial LLM leak detector | why: catch leaks code checks miss | v2.0
### prompt(v2/p4_working_analyzer): Initial working analyzer | why: stretch goal - targeted hints | v2.0
### prompt(v2/p5_targeted_hint): Initial targeted hint generator | why: stretch goal - address specific errors | v2.0

---

## 2024-10-03 11:15 - Model Migration to NVIDIA NIM

### prompt(llm): Migrated from Anthropic SDK to NVIDIA NIM (OpenAI-compatible) | why: use nemotron-3-super-120b-a12b via NIM API | v2.1
### prompt(.env.example): Updated to NVIDIA_API_KEY and nemotron model | why: match new provider | v2.1
### prompt(requirements.txt): Replaced anthropic with openai package | why: NIM uses OpenAI-compatible API | v2.1

---

## 2024-10-03 11:30 - V1 Naive Baseline Simplification

### prompt(v1/hint_naive): Simplified to exact template with {{problem}} and {{level}} placeholders | why: per spec, intentionally naive baseline | v1.0
### prompt(pipeline_v1): get_hint_v1(problem, level) fills template, calls call_llm once, no gate/solver/leak check | why: V1 baseline for comparison | v1.0
### prompt(app): Added V1 tab with Hint 1/2/3 buttons using get_hint_v1 | why: demo V1 working | v1.0

---

## 2024-10-03 11:45 - Guardrails & Arithmetic Checker Implementation

### code(guardrails): input_gate_code (empty/short/long/no-digits/injection), leak_check_code (numeric variants + phrase blocklist), normalise_numeric_equal | why: G1-G5 spec requirements | v2.0-pre
### code(arithmetic_check): check_working with sympy, handles × ÷ % of implicit-multiplication | why: stretch challenge deterministic checking | v2.0-pre
### test(guardrails): pytest cases for all gate categories, 6+ leak/clean strings, false-positive case | why: verify guardrails | v2.0-pre

---

## 2024-10-03 12:00 - V2 Pipeline Implementation

### code(pipeline_v2): start_problem (gate -> P0 -> P1x2 consistency), get_hint (P2 -> code leak -> P3 judge -> regen 2x -> fallback), level lock helper, debug logging | why: V2 chained pipeline per spec | v2.1
### test(pipeline_v2): mocked tests for leak-regen-pass, leak-3x-fallback, invalid-json-fallback | why: verify pipeline behavior | v2.1

---

## 2024-10-03 12:30 - UI Implementation (4 tabs)

### code(app): 4 tabs (Tutor, Compare, Evaluate, Prompt History) with sidebar (model selector, version, debug), level lock, working check, random problems | why: demo interface | v2.4

---

## 2024-10-03 13:00 - UI Simplification (Single Tutor Tab)

### code(app): Removed Compare, Evaluate, Prompt History tabs; removed V1/V2 selector; single Tutor tab with V2 pipeline only | why: align with Problem 13 spec (single production pipeline) | v2.5

---

## 2024-10-03 13:30 - Deploy Configuration

### code(.streamlit/config.toml): Theme, server, browser settings for Streamlit Cloud | why: production deploy config | v2.5
### code(.streamlit/secrets.toml.example): Template for Streamlit Secrets (NVIDIA_API_KEY, MODEL_MAIN, MODEL_FAST) | why: secure deploy without .env | v2.5
### code(.gitignore): Added .streamlit/secrets.toml | why: prevent committing secrets | v2.5
### doc(README): Deploy instructions, project structure, eval metrics | why: documentation for hackathon | v2.5

---

*Commit after every prompt-file change using: `prompt(<card>): <what changed> | why: <failure it fixes> | vX.Y`*