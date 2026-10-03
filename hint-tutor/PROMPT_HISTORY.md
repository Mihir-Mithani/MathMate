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

*Commit after every prompt-file change using: `prompt(<card>): <what changed> | why: <failure it fixes> | vX.Y`*