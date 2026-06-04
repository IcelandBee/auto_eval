---
name: vlm-qc-prompt-initialization
description: Use when generating an initial VLM-as-a-judge QC prompt from executable prompt templates, human-labeled image-editing cases, and prompt design rules
---

# VLM QC Prompt Initialization

## Core Intent

Generate a task-specific initial QC prompt (`v0`) before the automatic tuning loop.

This skill covers only initialization:

```text
explicit inputs + human labels + prompt design rules
  -> annotation summary with task definition
  -> user-reviewed prompt proposal
  -> task-specific v0 prompt
  -> auto-tuning loop
```

Use `vlm-qc-auto-tuning` for `v1`, `v2`, or later prompts created from FP/FN evaluation reports.

## Required Inputs

Do not use default paths, default tasks, or default prompt versions as substitutes for missing information.

Before starting, identify these inputs from the user request or repository context:

- task name,
- human-label file path,
- executable system prompt template or source system prompt path,
- executable user prompt template or source user prompt path,
- prompt design rule file path or explicit design rules,
- target prompt version and output directory,
- whether the run is interactive or explicitly batch/non-interactive.

If any required input is still missing after checking the request and local context, stop and ask the user for the missing information. Ask only for blocker information. Do not silently fall back to a project-specific example.

Reference files may be consulted only when explicitly provided or clearly relevant from local context. Treat them as evidence, not defaults.

Repository examples, historical sample files, and removed `code/` or `data/` assets are not defaults. If labels, source prompts, prompt rules, target task, target version, output directory, or interaction mode are missing, ask the user instead of substituting example paths or prior project habits.

## Required Workflow

Always follow this sequence:

1. Collect and confirm required inputs.
2. Read human labels and summarize annotations.
3. Infer the editing task definition from the prompt field(s) in the human-label file.
4. Propose QC dimensions and redlines from the task definition, human labels, existing dimensions, and rules.
5. In interactive mode, ask the user to confirm the task definition and dimension plan before writing final prompts.
6. Generate the complete v0 system/user prompt only after confirmation or explicit non-interactive authorization.
7. Save the annotation summary with evidence sources.
8. Hand off to the auto-tuning loop.

Do not jump directly from raw labels to final prompt text.

## Step 1: Build Annotation Summary

Read the human-label file and extract:

- task name or inferred task label,
- total case count,
- pass/fail counts,
- existing annotation dimensions,
- per-dimension pass/fail counts,
- prompt field values and prompt pattern clusters,
- all non-empty human reasons,
- recurring failure clusters,
- visible redline patterns,
- pass/tolerance clues when available,
- candidate QC dimensions,
- case-specific patterns that should not enter the main prompt.

The summary must include a task definition inferred primarily from the prompt field(s):

```json
{
  "task_definition": {
    "task_goal": "",
    "input_roles": {
      "image_a": "",
      "image_b": "",
      "image_c": "",
      "prompt": ""
    },
    "edit_operation": "",
    "target_scope": "",
    "reference_usage": "",
    "source_preservation_scope": "",
    "success_boundary": "",
    "failure_boundary": "",
    "out_of_scope_or_tolerated_variations": [],
    "prompt_pattern_clusters": []
  }
}
```

If the prompt field appears to contain multiple distinct task families, stop and ask the user whether to split the labels or create a broader prompt. Do not merge incompatible task definitions without confirmation.

Important:

- Empty reasoning fields are common, especially on pass samples.
- Use existing annotation dimensions as strong hints, not as mandatory output.
- Failure reason clusters and prompt patterns are more important than column names.
- Do not copy human reasons verbatim into the final prompt.
- Convert case-level reasons into task-level visual criteria.
- Keep a separate list of case-specific patterns excluded from the main prompt.

## Step 2: Design Dimensions

Propose dimensions from the task definition, recurring human-label failures, existing dimensions, templates, and design rules.

Dimension rules:

- Each dimension must cover a visible, judgeable class of quality issues.
- Keep dimensions small and task-specific; prefer 2-6 dimensions when possible.
- Prefer reusing, merging, or renaming existing dimensions before adding new ones.
- Add a new dimension only when the task definition and recurring evidence reveal a quality class not covered by existing dimensions.
- Usually add at most 1-2 new dimensions. If more seem necessary, ask the user before expanding.
- Do not add a dimension for a one-off case.
- The final JSON schema and downstream task configuration must match the selected dimensions.

For every proposed dimension, record evidence:

```json
{
  "name": "",
  "purpose": "",
  "status": "kept|renamed|merged|added|removed",
  "evidence_sources": [
    {
      "type": "prompt_pattern|human_reason|existing_dimension|template|rule|reference_prompt",
      "source": "",
      "summary": ""
    }
  ]
}
```

## Step 3: User Review Gate

Before writing final `system_prompt.txt` or `user_prompt.txt`, present a concise proposal to the user:

- inferred editing task definition,
- image/input role meanings,
- proposed dimensions with one-sentence purpose for each,
- dimensions kept, renamed, merged, added, or removed,
- main fail redlines,
- tolerance rules,
- any uncertainties or mixed-task signals.

In interactive mode, stop here and ask the user to confirm or revise the proposal. Do not write final prompt files until the user confirms.

In batch/non-interactive mode, proceed only if the user explicitly requested a non-interactive run or provided a pre-approved task definition and dimension plan. Record that confirmation in the summary.

It is acceptable to save review artifacts before confirmation, such as:

```text
annotation_summary.json
prompt_init_proposal.json
```

## Step 4: Generate v0 Prompt

Generate a complete task-specific prompt, not an adapter fragment.

The v0 prompt should:

- preserve the confirmed input meanings for Image A, B, C, and P,
- preserve visible-evidence and occlusion/cropping tolerance rules,
- use the confirmed task-specific dimensions,
- define `is_passed` as all dimensions passing,
- include task-specific redlines,
- output valid JSON,
- use concise Chinese reasons in model output,
- avoid case-specific examples unless the user explicitly asks for examples.

Do not default to a template's dimensions if the confirmed task definition and labels suggest a smaller or clearer schema. Templates are baselines, not contracts.

## Output Contract

When asked to produce a v0 prompt, return or save:

```json
{
  "task": "<task>",
  "mode": "interactive|batch",
  "source_files": {
    "system_prompt_template_or_source": "<path>",
    "user_prompt_template_or_source": "<path>",
    "human_labels": "<path>",
    "prompt_rules": ["<path-or-inline-rule>"]
  },
  "annotation_summary": {
    "case_count": 0,
    "label_counts": {},
    "existing_dimensions": [],
    "dimension_label_counts": {},
    "task_definition": {},
    "failure_clusters": [],
    "candidate_dimensions": [],
    "dimension_plan": [],
    "redlines": [],
    "tolerance_rules": [],
    "excluded_case_specific_patterns": [],
    "evidence_sources": [],
    "user_confirmation": {
      "required": true,
      "status": "pending|confirmed|batch-authorized",
      "notes": ""
    }
  },
  "prompt_files": {
    "system_prompt": "prompts/tasks/<task>/<version>/system_prompt.txt",
    "user_prompt": "prompts/tasks/<task>/<version>/user_prompt.txt"
  }
}
```

If writing files, save `annotation_summary.json` with the final prompts. Prefer also saving `prompt_init_proposal.json` for the user-review gate.

## Prompt Design Rules

Follow the project prompt design rules supplied by the user or local context:

- prefer clear visual criteria,
- avoid subjective wording,
- avoid overfitting one case,
- keep rules at type/structure level,
- keep prompt length controlled,
- combine overlapping rules,
- do not add rules without considering compression,
- prioritize serious and recurring failures,
- preserve visible-evidence constraints.

For initialization, these rules apply differently than iterative tuning:

- It is allowed to reorganize dimensions because there is no task prompt yet.
- It is allowed to write a complete prompt rather than a patch.
- It is not allowed to invent task requirements unsupported by labels, templates, rules, or provided reference prompts.

## Handoff to Auto Tuning

After v0 is generated and saved, switch to `vlm-qc-auto-tuning`.

The first auto-tuning run should evaluate:

```text
--mode task_prompt --prompt-version <version>
```

Do not continue modifying v0 blindly. Let the automatic tuning loop produce metrics, bad cases, and optimizer input before writing v1.

## Do Not Do

- Do not use hard-coded defaults when required inputs are missing.
- Do not skip the task definition.
- Do not skip annotation summary.
- Do not skip the user review gate in interactive mode.
- Do not copy individual human reasons directly into the prompt.
- Do not preserve template dimensions by default.
- Do not add dimensions without evidence.
- Do not generate an adapter instead of a full task prompt.
- Do not overwrite an existing v0 without explicit instruction.
- Do not make the prompt stricter on invisible, cropped, occluded, blurry, or ambiguous details.
