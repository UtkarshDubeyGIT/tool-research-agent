# Phase 3 Implementation Plan: Research Agent, Jev Decisions & Code Composition

## Scope & Objective
1. Implement OpenRouter Decisions API client for TypeSafe Jev (`typesafe/jev-1.13`) with atomic Noul and Choice questions (`src/jev_client.py`).
2. Integrate OpenAI `gpt-6-luna` (configurable via `OPENAI_MODEL`) for bounded fact extraction and citation generation.
3. Implement code-owned composition rules in `src/rules.py` for API breadth and buildability verdicts.
4. Build resumable CLI orchestrator (`src/research.py`) with `--app-id`, `--all`, `--resume`, `--refresh`, and checkpointing after every record.

## Verification
- Test single app execution (`--app-id 1`).
- Test full 90-app batch execution with checkpointing.
- Verify that every record adheres to the data contract.
