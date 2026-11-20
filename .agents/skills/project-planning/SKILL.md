---
name: project-planning
description: >-
  Use this skill when planning new development phases, creating architectural proposals,
  breaking down features into tasks, or establishing project checkpoints for ClipForge AI.
---

# Project Planning & Task Breakdown Skill

This skill guides the structured planning of ClipForge AI features, ensuring strict adherence to the project roadmap, approved MVP scope, and laptop hardware constraints.

## When to Use This Skill
- Before implementing any new development phase (e.g., Phase 2, Phase 3).
- When scoping a new feature, API route, or pipeline modification.
- When evaluating architectural trade-offs or technical risks.
- When creating structured task breakdowns for user review and approval.

## Step-by-Step Planning Procedure

1. **Review Context & Constraints:**
   - Inspect [AGENTS.md](file:///c:/Users/25194/Desktop/New%20folder/work/clipforge-ai/AGENTS.md) and [IMPLEMENTATION_ROADMAP.md](file:///c:/Users/25194/Desktop/New%20folder/work/clipforge-ai/IMPLEMENTATION_ROADMAP.md).
   - Verify whether the proposed task falls strictly within the approved MVP scope.
   - Confirm compatibility with the host hardware (Intel Core i7-1255U, Iris Xe, ~22GB free disk space).

2. **Define Scope & Boundaries:**
   - Clearly delineate:
     - **In-Scope:** The exact components, models, schemas, or views being created.
     - **Out-of-Scope:** Any deferred features (e.g. YouTube downloading, multi-speaker split layouts, cloud publishing).

3. **Break Down Implementation Steps:**
   - Sequence tasks logically: Data models -> Core engine -> Service layer -> API/UI.
   - Ensure each task is small enough to be implemented and tested within a single development turn.

4. **Identify Dependencies & Artifacts:**
   - List any new Python/NPM packages needed.
   - Specify the input and output disk artifacts for any media step.

5. **Formulate Verification Criteria:**
   - Define exact automated unit/integration tests to prove completion.
   - Define expected tangible outputs (e.g., generated files, API response schemas).

6. **Seek User Approval:**
   - Present the concise plan to the user and wait for explicit confirmation before writing application code.

## Technical Standards
- Never plan parallel heavy compute tasks (transcription + video encoding).
- Keep proposed models quantized (`int8`) and under 500 MB (Whisper `base` or `small`).
- Ensure all planned filesystem interactions write within `projects/{id}/work/` or `clipforge-data/`.

## Common Mistakes to Avoid
- **Scope Creep:** Adding nice-to-have features (e.g., animated emoji overlays, generative B-roll) during MVP phases.
- **Premature Implementation:** Writing code while the planning proposal is still pending user feedback.
- **Ignoring Disk Headroom:** Planning tasks that produce massive intermediate video caches on an SSD with ~22 GB free space.

## Verification Checklist
- [ ] Plan aligns with the current Phase in `IMPLEMENTATION_ROADMAP.md`.
- [ ] No out-of-scope features are included.
- [ ] Hardware impact (CPU, RAM, disk) has been assessed.
- [ ] Test strategy and Definition of Done are explicitly stated.
- [ ] Plan is presented to the user for formal approval.

