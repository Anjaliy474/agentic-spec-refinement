# ReqHQ: Agentic Specification Refinement

Course project for **Autonomous Software Engineering** (Build Your Own Harness), Team Req HQ.

ReqHQ turns a prose product requirements document (PRD) into a developer-ready specification. It finds what the PRD leaves out and asks about it, instead of filling the gaps with guesses.

## Architecture

```
Raw PRD ──► LLM Orchestrator ──► SLM critics (Security, Architecture, Performance)
            (draft FRs, routing)            │
                                            ▼
                                  Gap & conflict check ──► Targeted human questions
                                            │                        │
                                            ▼                        ▼
                                  Final spec with trace links ◄── answers fed back
```

1. **Orchestrator** (`src/reqhq/orchestrator`) extracts draft functional requirements (FRs) from the PRD and routes them to the critics.
2. **Critics** (`src/reqhq/critics`) are narrow, fine-tuned small language models. Each returns missing or vague non-functional requirements (NFRs) and ambiguity flags that point to the PRD sentence that caused them.
3. **Gap & conflict gate** (`src/reqhq/gating`) sends a question to the human only when a critic reports missing business context or two critics disagree.
4. **Traceability** (`src/reqhq/trace`) links every line of the final spec to a PRD sentence, a critic, or a human answer.
5. **Evaluation** (`src/reqhq/eval`) covers requirement matching, precision/recall/F1, completeness penalty, questions per PRD, and the simulated oracle human.

## Pre-registered hypotheses

- **H1**: The full pipeline (without human input) has higher NFR recall than a single LLM, with precision dropping by no more than 0.03.
- **H2**: SLM critics come within 0.05 NFR F1 of LLM critics in the same roles, at much lower token cost and latency.
- **H3**: Targeted questioning reaches at least 95% of the completeness of ask-everything review, with at least 50% fewer questions.

Baselines: B1 single LLM, B2 orchestrator + LLM critics, B3 our pipeline without human input, B4 our pipeline with ask-everything review, plus leave-one-critic-out ablations. See [`docs/proposal`](docs/proposal/).

## Repository layout

```
src/reqhq/        core package (orchestrator, critics, gating, trace, eval)
configs/          model and experiment configuration
data/             raw PRDs/specs, processed data, frozen splits (large files not committed)
experiments/      run outputs and result tables
scripts/          data preparation and experiment entry points
tests/            unit tests
docs/             proposal, reports, AI-usage log
```

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Models run locally through [Ollama](https://ollama.com) by default:

```bash
ollama pull qwen2.5:7b   # orchestrator and oracle
ollama pull qwen2.5:3b   # critics
```

To use another backend (LM Studio, vLLM, a hosted API), set `backend: openai` in `configs/default.yaml` and `OPENAI_BASE_URL` / `OPENAI_API_KEY`.

## Usage

```bash
# Interactive: the pipeline asks you only the questions it needs
reqhq run data/examples/clinic_booking_prd.md

# No human (baseline B3) and ask-everything review (baseline B4)
reqhq run data/examples/clinic_booking_prd.md --human none
reqhq run data/examples/clinic_booking_prd.md --mode all

# Simulated product owner that answers from a reference spec
reqhq run PRD.md --human oracle --reference REFERENCE_SPEC.md

# Ablation: drop a critic
reqhq run PRD.md --critics security,performance
```

Each run writes to `experiments/runs/<prd>/`:

| File | Contents |
|---|---|
| `spec.md` | Final spec; every line shows its PRD sentence, critic and/or answer |
| `spec.json` | Same spec, machine-readable |
| `findings.json` | Raw critic findings |
| `usage.json` | Calls, tokens and seconds per component |

## Team

| Name | Roll no. |
|---|---|
| Panem Chaitanya Pavan Kumar | 2025204023 |
| Anjali Yadav | 2025204015 |
| Anshul Agrawal | 2025901015 |

## AI usage

As the course requires, we document substantial AI-tool use (tools, prompts, outputs, and how we verified them) in [`docs/ai-usage/`](docs/ai-usage/).
