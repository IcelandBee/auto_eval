---
name: vlm-qc-prompt-initialization
description: Use when generating an initial VLM-as-a-judge QC prompt from a universal template, human-labeled image-editing cases, and prompt design rules
---

# VLM QC Prompt Initialization

## Core Intent

Generate a task-specific initial QC prompt (`v0`) before the automatic tuning loop.

This skill covers the stage before `vlm-qc-auto-tuning`:

```text
universal template + human labels + prompt design rules
  -> annotation summary
  -> task-specific v0 prompt
  -> auto-tuning loop
```

Do not use this skill to tune `v1`, `v2`, or later prompts from FP/FN reports. Use `vlm-qc-auto-tuning` for that stage.

## Default Project Inputs

Universal template:

```text
prompts/universal/universal_qc_prompt_v0.txt
prompts/universal/universal_redlines_v0.txt
```

Human labels:

```text
data/<task>/<label_file>.json
```

Examples:

```text
data/texture_person/texture_person_label_sample.json
data/human_item/human_item_label_sample.json
```

Prompt design rules:

```text
rules/Prompt修改规范.txt
rules/prompt_initialization_rules_v0.txt
```

Target output:

```text
prompts/tasks/<task>/v0/system_prompt.txt
prompts/tasks/<task>/v0/user_prompt.txt
```

Recommended analysis output:

```text
runs/<task>/prompt_init_v0/annotation_summary.json
runs/<task>/prompt_init_v0/prompt_init_input.json
```

## Required Workflow

Always do two steps. Do not jump directly from raw labels to final prompt text.

1. Build an annotation summary.
2. Generate the v0 prompt from the summary and the universal template.

The annotation summary is the inspection surface. The user should be able to review why the dimensions and rules were chosen.

## Step 1: Summarize Human Labels

Read the human-label file and extract:

- task name,
- total case count,
- pass/fail counts,
- existing annotation dimensions,
- per-dimension pass/fail counts,
- all non-empty human reasons,
- recurring failure clusters,
- visible redline patterns,
- pass/tolerance clues when available,
- candidate QC dimensions,
- case-specific patterns that should not enter the main prompt.

Use existing annotation dimensions as strong hints, not as mandatory output. Failure reason clusters are more important than column names.

Important:

- Empty reasoning fields are common, especially on pass samples.
- Do not treat a dimension as useless only because the current sample has no failures for it; ask whether it is still a core risk for the task.
- Do not copy human reasons verbatim into the final prompt.
- Convert case-level reasons into task-level visual criteria.

## Step 2: Generate v0 Prompt

Generate a complete task-specific prompt, not an adapter fragment.

The v0 prompt should:

- keep universal input meanings for Image A, B, C, and P,
- preserve visible-evidence and occlusion/cropping tolerance rules,
- use task-specific dimensions inferred from labels,
- define `is_passed` as all dimensions passing,
- include task-specific redlines,
- output valid JSON,
- use concise Chinese reasons in model output,
- avoid case-specific examples unless the user explicitly asks for examples.

Recommended dimension count:

- simple tasks: 2-4 dimensions,
- typical tasks: 3-6 dimensions,
- complex tasks: up to 8 dimensions.

Do not default to the universal six dimensions if the human labels suggest a smaller, clearer task-specific schema.

## Output Contract

When asked to produce a v0 prompt, return or save:

```json
{
  "task": "<task>",
  "source_files": {
    "universal_prompt": "prompts/universal/universal_qc_prompt_v0.txt",
    "universal_redlines": "prompts/universal/universal_redlines_v0.txt",
    "human_labels": "<path>",
    "prompt_rules": "rules/Prompt修改规范.txt",
    "initialization_rules": "rules/prompt_initialization_rules_v0.txt"
  },
  "annotation_summary": {
    "case_count": 0,
    "label_counts": {},
    "existing_dimensions": [],
    "dimension_label_counts": {},
    "failure_clusters": [],
    "candidate_dimensions": [],
    "redlines": [],
    "tolerance_rules": [],
    "excluded_case_specific_patterns": []
  },
  "prompt_files": {
    "system_prompt": "prompts/tasks/<task>/v0/system_prompt.txt",
    "user_prompt": "prompts/tasks/<task>/v0/user_prompt.txt"
  }
}
```

If writing files, save `annotation_summary.json` as well as the final prompts.

## Prompt Design Rules

Follow the project prompt design rules:

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
- It is not allowed to invent task requirements unsupported by labels, the universal template, or the prompt text.

## Texture Transfer Guidance

For `texture_transfer` / `texture_person`, likely dimensions include:

- `instruction_following`: target garment/region coverage, no important target residue, correct target.
- `texture_consistency`: broad material identity, dominant color family, main pattern style from Image B.
- `clothes_consistency`: A-C garment structure and non-target preservation.

Common failure clusters:

- original texture, color, or pattern remains on target regions,
- target garment is only partially edited,
- texture leaks to non-target regions,
- target garment structure changes,
- structural anchors change: neckline, collar, cuffs, sleeve length, hem, zipper, buttons, cutouts, straps, laces, pockets, hood, openings, silhouette, fit, or layering.

Keep tolerance for:

- fold/perspective deformation of texture,
- lighting and shadow changes,
- minor blur or tiny unverifiable details,
- occluded/cropped regions.

## Human Item Guidance

For `human_item`, likely dimensions include:

- `instruction_following`: object identity, category, color, quantity, requested action, and correct reference object.
- `perceptual_quality`: physical plausibility, human-object contact, scale, anatomy, occlusion, and severe artifacts.

Common failure clusters:

- wrong object identity,
- wrong color or quantity,
- object not actually held/carried/cradled,
- floating object or no support/contact,
- hand-object penetration or fusion,
- duplicated or impossible limbs/hands,
- severe scale mismatch.

Keep tolerance for:

- minor hand awkwardness,
- partially hidden fingers,
- simplified thin object parts,
- occlusion by the inserted object,
- blurry or tiny unverifiable regions.

## Handoff to Auto Tuning

After v0 is generated and saved, switch to `vlm-qc-auto-tuning`.

The first auto-tuning run should evaluate:

```text
--mode task_prompt --prompt-version v0
```

Do not continue modifying v0 blindly. Let the automatic tuning loop produce metrics, bad cases, and optimizer input before writing v1.

## Do Not Do

- Do not skip annotation summary.
- Do not copy individual human reasons directly into the prompt.
- Do not preserve universal six dimensions by default.
- Do not generate an adapter instead of a full task prompt.
- Do not overwrite an existing v0 without explicit instruction.
- Do not make the prompt stricter on invisible, cropped, occluded, blurry, or ambiguous details.
