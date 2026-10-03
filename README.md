# 🧮 MathMate -- Hint-Based Math Tutor

> **Problem 13 -- Hint-Based Math Tutor \| Team 17 \| Marwadi University
> \| 3 October 2026**

## 🚀 Live Demo

**[Open MathMate Live App](https://ectocranial-unhandily-delila.ngrok-free.dev/)**


> Streamlit URL before submission.

**GitHub Repository:** https://github.com/Mihir-Mithani/MathMate

## 📌 Overview

MathMate is an AI-powered mathematics tutor that helps students solve
word problems through **progressive hints instead of revealing the final
answer immediately**.

The three-level hint workflow is:

-   **Level 1 -- Orient:** Restate what is being asked and ask one
    guiding question.
-   **Level 2 -- Strategy:** Identify the method and help set up the
    first step.
-   **Level 3 -- Walkthrough:** Provide the complete step-by-step
    solution.

MathMate also supports a stretch challenge where students submit their
working. The system checks the working, identifies the **first wrong
step**, classifies the error, and provides a targeted hint.

## 🎯 Objectives

1.  Guide students rather than immediately solve the problem.
2.  Increase assistance progressively.
3.  Prevent premature answer leakage.
4.  Detect the student's first wrong step.
5.  Give targeted feedback based on the mistake.
6.  Validate and guard generated outputs.
7.  Compare a naive V1 prompt with the final V2 workflow.

## ✨ Key Features

### Three-Level Hint System

  -----------------------------------------------------------------------
  Level                               Purpose
  ----------------------------------- -----------------------------------
  **Level 1 -- Orient**               Restate the problem and ask one
                                      guiding question

  **Level 2 -- Strategy**             Name the method and suggest the
                                      first setup step

  **Level 3 -- Walkthrough**          Provide the complete solution and
                                      final answer
  -----------------------------------------------------------------------

### Wrong-Step Detection

Students can submit their working. MathMate: - Checks equations using
SymPy. - Identifies the first wrong step. - Classifies the error. -
Generates a targeted hint. - Praises the student when the working is
correct.

### Answer-Leak Protection

Levels 1 and 2 are checked using code-based leak checking and an LLM
leak judge. Leaking hints can be regenerated up to two times before a
safe generic hint is shown.

### V1 vs V2

The application compares: - **V1 -- Naive** - **V2 -- Chained**

The same problem can be tested with both versions and compared side by
side.

## 🧠 Prompt Engineering Techniques

MathMate combines: - **Few-shot prompting** - **Role prompting** -
**Prompt chaining** - **Structured output prompting** - **Negative
constraints** - **Self-critique / LLM judging**

### Prompt Chain

``` text
Student Problem
      ↓
Hidden Solver
      ↓
Hint Writer
      ↓
Leak Judge
      ↓
Student Working
      ↓
Step Finder
      ↓
Targeted Hint
```

## 🧩 Prompt Architecture

``` text
prompts/
├── solver.txt
├── hint_writer.txt
├── leak_judge.txt
└── step_finder.txt
```

-   **solver.txt:** Creates a hidden mathematical solution.
-   **hint_writer.txt:** Generates Level 1, 2, or 3 hints.
-   **leak_judge.txt:** Checks whether a hint reveals the final answer
    or last-step result.
-   **step_finder.txt:** Finds the first wrong step and classifies the
    error.

## 🔐 Guardrails

MathMate handles: - Invalid or unsolvable problems - Off-topic
questions - Prompt injection - Answer-demand-only requests - Answer
leakage - Invalid JSON - Incorrect student calculations

LLM outputs are validated with Pydantic. Invalid output is retried once
and then handled with a fallback.

## 🧮 Arithmetic Verification

Student equations are checked using **SymPy**. The arithmetic results
are supplied to the step-finding prompt so the system can identify the
first meaningful mistake.

## 📊 Evaluation

The project includes: - **12 labelled math word problems** -
Wrong-working cases with known wrong steps - Guardrail/adversarial cases

### Metrics

**Leak Rate**

``` text
Leaked Hint 1 + Hint 2 outputs
--------------------------------
Total Hint 1 + Hint 2 outputs
```

**Wrong-Step Accuracy**

``` text
Correctly identified first wrong steps
--------------------------------------
Total wrong-working cases
```

> Add only the real measured V1/V2 results after running the evaluation.

## 🖥️ Application Workflow

``` text
Enter Problem
     ↓
Start Problem
     ↓
Hint 1
     ↓
Hint 2
     ↓
Hint 3
     ↓
Show Your Working
     ↓
Check My Working
     ↓
Wrong Step / Targeted Hint
     ↓
Final Answer
```

## 🏗️ Project Structure

``` text
MathMate/
├── app.py
├── tutor.py
├── prompts/
│   ├── solver.txt
│   ├── hint_writer.txt
│   ├── leak_judge.txt
│   └── step_finder.txt
├── eval/
│   ├── problems.json
│   ├── wrong_working.json
│   ├── run_eval.py
│   └── results/
├── PROMPT_HISTORY.md
├── README.md
└── requirements.txt
```

## 🛠️ Technology Stack

-   Python
-   Streamlit
-   Anthropic Python SDK
-   Pydantic
-   SymPy
-   Git / GitHub

## ▶️ How to Run Locally

``` bash
git clone https://github.com/Mihir-Mithani/MathMate.git
cd MathMate
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Configure the required API settings in `.env`. **Never commit API keys
to GitHub.**

## 🧪 Evaluation

Run:

``` bash
python eval/run_eval.py
```

Use only the generated real results for the final V1 vs V2 comparison.

## 📝 Prompt History

Prompt changes are documented in:

``` text
PROMPT_HISTORY.md
```

Record the prompt/version, time, failure observed, change, reason,
before/after metric, and responsible team member.

## 👥 Team 17

  Team Member                   Role
  ----------------------------- -------------------------------------
  **Happy Limbasiya**           UI, workflow, documentation/demo
  **Mihir Mithani**             Prototype development/integration
  **Karmadipsinh Jadeja**       Prompt design, testing, refinement
  **MARIAL MEEN MAGER MAKOI**   Research, problem analysis, testing
  **HARSH THAKAR**              Research, problem analysis, testing

## ⚠️ Limitations

-   The system depends on the underlying LLM's mathematical reasoning.
-   Complex or ambiguous problems may require additional verification.
-   LLM-generated hints require leak checking.
-   The current prototype focuses on text-based school mathematics.
-   Wrong-step detection depends on the quality and structure of
    submitted student working.

## 🔮 Future Scope

-   Image-based mathematical problem solving
-   Diagram understanding
-   More mathematical topics
-   Multilingual tutoring
-   Personalized difficulty levels
-   Student progress tracking
-   Larger evaluation datasets

## 🎬 Hackathon Demo Flow

1.  Open the Live Demo.
2.  Enter an unseen math problem.
3.  Show Hint 1.
4.  Show Hint 2.
5.  Show Hint 3.
6.  Submit incorrect working.
7.  Show the flagged wrong step.
8.  Show the targeted hint.
9.  Correct the answer.
10. Compare V1 vs V2.
11. Show evaluation results.
12. Show prompt history / Git history.

## 📌 Submission Checklist

-   [ ] Working Streamlit application
-   [ ] Live deployment link added at the top
-   [ ] Three-level hint system
-   [ ] Level 1--2 leak protection
-   [ ] Wrong-step detection
-   [ ] Targeted hints
-   [ ] V1 vs V2 comparison
-   [ ] Real evaluation results
-   [ ] Prompt history
-   [ ] GitHub repository
-   [ ] Team contribution documentation
-   [ ] Demo prepared

## 💡 MathMate

**Learn. Think. Solve.**
