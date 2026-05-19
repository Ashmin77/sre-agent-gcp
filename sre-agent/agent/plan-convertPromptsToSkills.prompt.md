# Plan: Convert prompts.py to skills.md

Convert `agent/prompts.py` (6 LLM prompt pairs) into a Markdown skill reference document at `skills.md` in the project root. Each prompt pair becomes a named skill section with role, inputs, and output schema. The original file is left unchanged.

## Steps

1. Create `skills.md` at project root with a title and brief intro describing the GCP SRE Agent's skill set.
2. Add 6 sections (one per prompt pair), each with:
   - **H2 heading** — skill name (e.g., `## Input Normalizer`)
   - **Role** — one-line description from the system prompt
   - **Constraints** — key behavioral rules from `_SYSTEM` prompt as bullet list
   - **Inputs** — table of template variables from `_USER` prompt (e.g., `{query}`, `{namespace}`) with descriptions
   - **Output Schema** — expected JSON structure from `_USER` prompt in a fenced code block

## Skills to Document

| # | Skill | Source constants |
|---|-------|-----------------|
| 1 | Input Normalizer | `INPUT_NORMALIZER_SYSTEM/USER` |
| 2 | Task Planner | `TASK_PLANNER_SYSTEM/USER` |
| 3 | MCP Router | `MCP_ROUTER_SYSTEM/USER` |
| 4 | Evidence Extractor | `EVIDENCE_EXTRACTOR_SYSTEM/USER` |
| 5 | Task Evaluator | `TASK_EVALUATOR_SYSTEM/USER` |
| 6 | RCA Builder | `RCA_BUILDER_SYSTEM/USER` |

## Relevant Files

- `agent/prompts.py` — source; all 6 prompt pairs to convert (read-only)
- `skills.md` — new file to create at project root

## Verification

1. All 6 skills present as H2 sections
2. Every `{template_variable}` from each `_USER` prompt listed in the Inputs table
3. Every JSON output field from each `_USER` prompt present in the Output Schema block
4. No Python string artifacts (triple-quotes, `\n`, raw braces) in the output

## Decisions

- `agent/prompts.py` stays unchanged — `skills.md` is a documentation artifact
- Location: project root
- Format: structured skill reference doc
