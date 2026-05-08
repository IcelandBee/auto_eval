# Universal Prompt QC Assets and Scripts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a staged multi-task image-editing QC prompt system where Phase 1 produces reviewable prompt/config/optimizer assets and Phase 2 adds reusable scripts for prompt composition, validation, offline metrics, and report comparison.

**Architecture:** Prompt assets live under `prompts/`, machine-readable task/schema/taxonomy configuration lives under `configs/`, optimizer constraints live under `optimizer/`, and reusable local tooling lives under `scripts/`. Phase 1 must pause after asset validation so the user can run real VLM experiments on the work computer before Phase 2 begins.

**Tech Stack:** Plain text prompts, JSON schemas/configs, Python 3 standard library, existing project data conventions from `code/texture_person/check_and_eval.py`.

---

## Phase Gates

Phase 1 delivers prompt assets only:

- Universal Prompt v0
- Universal redlines v0
- Universal user prompt v0
- `human_item` Adapter v0
- `texture_transfer` Adapter v0
- output schema
- error taxonomy
- task adapter config
- optimizer skill spec
- prompt patch schema
- a small asset validation script

Stop after Phase 1. The user will move assets to the work computer, run experiments, and provide feedback before Phase 2.

Phase 2 delivers script generalization:

- prompt composition and config validation
- prompt preview
- offline output validation and metrics
- report comparison across original, universal only, and universal + adapter

## File Map

Create:

- `D:\Project\auto_eval\prompts\universal\universal_qc_prompt_v0.txt`: task-agnostic VLM judge system prompt.
- `D:\Project\auto_eval\prompts\universal\universal_redlines_v0.txt`: standalone cross-task redline list.
- `D:\Project\auto_eval\prompts\user\universal_user_prompt_v0.txt`: shared user prompt template with `{PROMPT}` placeholder.
- `D:\Project\auto_eval\prompts\adapters\human_item_adapter_v0.txt`: task-specific rules for person-object holding/carrying edits.
- `D:\Project\auto_eval\prompts\adapters\texture_transfer_adapter_v0.txt`: task-specific rules for clothing texture transfer.
- `D:\Project\auto_eval\configs\output_schema.json`: schema for universal QC output.
- `D:\Project\auto_eval\configs\error_taxonomy.json`: common and task-specific error types.
- `D:\Project\auto_eval\configs\task_adapter_config.json`: task-to-prompt/config mapping.
- `D:\Project\auto_eval\optimizer\prompt_optimizer_skill.md`: constrained prompt optimizer workflow.
- `D:\Project\auto_eval\optimizer\prompt_patch_schema.json`: schema for optimizer output patches.
- `D:\Project\auto_eval\scripts\validate_prompt_assets.py`: Phase 1 validation CLI.

Create in Phase 2:

- `D:\Project\auto_eval\scripts\prompt_assets.py`: prompt/config loading and composition library.
- `D:\Project\auto_eval\scripts\evaluate_prompt_suite.py`: offline metrics and optional future inference entrypoint.
- `D:\Project\auto_eval\scripts\compare_prompt_reports.py`: comparison report builder.
- `D:\Project\auto_eval\tests\test_prompt_assets.py`: tests for prompt composition/config validation.
- `D:\Project\auto_eval\tests\test_metrics.py`: tests for metrics and comparison behavior.

Do not modify in Phase 1:

- `D:\Project\auto_eval\code\human_item\prompts\system_prompt.txt`
- `D:\Project\auto_eval\code\human_item\prompts\user_prompt.txt`
- `D:\Project\auto_eval\code\texture_person\check_and_eval.py`
- `D:\Project\auto_eval\code\texture_person\prompts\system_prompt.txt`
- `D:\Project\auto_eval\code\texture_person\prompts\user_prompt.txt`

---

### Task 1: Create Phase 1 Directories

**Files:**
- Create: `D:\Project\auto_eval\prompts\universal\`
- Create: `D:\Project\auto_eval\prompts\user\`
- Create: `D:\Project\auto_eval\prompts\adapters\`
- Create: `D:\Project\auto_eval\configs\`
- Create: `D:\Project\auto_eval\optimizer\`
- Create: `D:\Project\auto_eval\scripts\`

- [ ] **Step 1: Create directories**

Run:

```powershell
New-Item -ItemType Directory -Force -Path .\prompts\universal, .\prompts\user, .\prompts\adapters, .\configs, .\optimizer, .\scripts | Out-Null
```

Expected: command exits with code 0 and the directories exist.

- [ ] **Step 2: Verify directories**

Run:

```powershell
Get-ChildItem -Directory .\prompts, .\configs, .\optimizer, .\scripts | Select-Object FullName
```

Expected: output includes `prompts\universal`, `prompts\user`, `prompts\adapters`, `configs`, `optimizer`, and `scripts`.

---

### Task 2: Add Universal Prompt Assets

**Files:**
- Create: `D:\Project\auto_eval\prompts\universal\universal_qc_prompt_v0.txt`
- Create: `D:\Project\auto_eval\prompts\universal\universal_redlines_v0.txt`
- Create: `D:\Project\auto_eval\prompts\user\universal_user_prompt_v0.txt`

- [ ] **Step 1: Create `universal_qc_prompt_v0.txt`**

Write this content:

```text
You are a strict image-editing quality inspector.

You will receive:
- image 1: source image (Image A)
- image 2: reference image (Image B)
- image 3: edited image (Image C)
- prompt: edit instruction (P)

Your task is to judge whether Image C is a high-quality edited result for the instruction P, using Image A and Image B as evidence.

This is a high-quality training-data filter. Clear visible failures must fail. However, all judgments must be based on visible evidence. Do not invent defects in regions that are fully occluded, cropped, too small, or too blurry to verify.

Important input meanings:
- Image A is the source image. Its non-target identity, pose, layout, background, and non-target regions should be preserved unless P clearly requires a minimal necessary change.
- Image B is the reference image. It may provide an object, texture, style, local attribute, or visual feature that should be transferred or followed.
- Image C is the edited result to evaluate.
- P describes the requested edit and the intended target region or target object.

Overall decision rule:
- Return "is_passed": true only if all six dimensions pass.
- If any dimension fails, "is_passed" must be false.
- Prefer precision for training-data filtering: a clear important failure should fail.
- Do not fail for tiny, ambiguous, invisible, naturally occluded, or unverifiable differences.
- Allow minimal necessary changes that are required to complete P, but fail if those changes introduce visible unrelated errors.

Dimensions:

1. instruction_following
Check whether Image C completes the core edit requested by P.
PASS if the requested target, action, attribute, object, or region is visibly edited in the correct place.
FAIL if the core edit is missing, applied to the wrong target, incomplete in an important visible area, or contradicts P.

2. reference_fidelity
Check whether Image C correctly uses the relevant visual content from Image B.
Consider the reference object's category, quantity, main shape, dominant color, visible texture, pattern, material, style, and task-relevant local features.
FAIL if Image C uses the wrong reference content, loses the main visual identity of Image B, or copies irrelevant Image B content.

3. source_preservation
Check whether Image C preserves the parts of Image A that should not change.
Consider person identity, body pose, face, hair, clothing outside the target, background, scene layout, non-target objects, and overall composition.
FAIL if non-target content is visibly deleted, added, replaced, distorted, retextured, recolored, or structurally changed.

4. edit_localization
Check whether the edit is limited to the target object or target region implied by P.
PASS if only the target area and minimal necessary adjacent interaction areas change.
FAIL if the edit spills into non-target clothing, skin, face, hair, accessories, props, background, or other unrelated regions.

5. physical_and_structural_realism
Check whether Image C is physically and structurally plausible.
Consider human anatomy, object support, contact, occlusion, layering, perspective, scale, garment structure, object structure, and scene logic.
FAIL if there are clear extra limbs, duplicated body parts, impossible joints, floating objects, physical penetration, wrong layering, severe scale errors, changed garment structure, or impossible contact/support relationships.

6. image_quality_and_artifacts
Check whether Image C has acceptable visual quality.
FAIL if Image C contains obvious artifacts, broken boundaries, severe blur, low-quality repainting traces, unnatural seams, corrupted regions, deformed objects, or generation collapse that affects the edited result or important visible content.

Universal redlines:
- The core requested edit is missing or applied to the wrong target.
- The reference content from Image B is clearly mismatched.
- Image A's non-target person, identity, pose, background, or scene is clearly changed.
- The edit visibly affects non-target regions.
- Image B's background, person, display environment, or unrelated elements leak into Image C.
- Physical structure, contact, support, occlusion, perspective, or scale is clearly impossible.
- The result contains obvious artifacts or severe quality degradation.

Reasoning rules:
- Output only visible, verifiable issues.
- If a sample fails, the reason should mention the most important visible failure, not a minor secondary issue.
- If multiple dimensions fail, each failing dimension should give a concise Chinese reason for that dimension.
- For passed dimensions, give a short Chinese reason that states what was checked.
- Do not output markdown, code fences, comments, or extra text.

Output format: Return ONLY a valid JSON object matching this shape:
{
  "is_passed": true,
  "instruction_following": {"passed": true, "reason": "中文一句话", "error_types": []},
  "reference_fidelity": {"passed": true, "reason": "中文一句话", "error_types": []},
  "source_preservation": {"passed": true, "reason": "中文一句话", "error_types": []},
  "edit_localization": {"passed": true, "reason": "中文一句话", "error_types": []},
  "physical_and_structural_realism": {"passed": true, "reason": "中文一句话", "error_types": []},
  "image_quality_and_artifacts": {"passed": true, "reason": "中文一句话", "error_types": []}
}
```

- [ ] **Step 2: Create `universal_redlines_v0.txt`**

Write this content:

```text
Universal redlines for image-editing QC:

1. wrong_target
The requested edit is applied to the wrong object, wrong person, or wrong region.

2. missing_core_edit
The main edit requested by P is missing or visibly incomplete.

3. reference_mismatch
Image C does not match the task-relevant object, texture, style, color, shape, quantity, or visual identity from Image B.

4. source_preservation_failure
Image A's non-target person, identity, pose, face, hair, clothing, background, scene layout, or non-target object is visibly changed.

5. edit_overreach
The edit affects visible non-target regions such as skin, face, hair, accessories, props, background, nearby garments, or unrelated objects.

6. physical_implausibility
Image C contains a clear physical or structural impossibility, including impossible anatomy, impossible contact, floating objects, penetration, wrong occlusion/layering, severe scale errors, or broken garment/object structure.

7. reference_leakage
Image B's background, person, display environment, or irrelevant elements leak into Image C.

8. artifact_or_low_quality
Image C contains obvious artifacts, broken boundaries, severe blur, corrupted areas, visible repainting traces, unnatural seams, deformation, or generation collapse.

Only fail on visible evidence. Do not treat invisible, cropped, fully occluded, very small, or too blurry regions as confirmed errors.
```

- [ ] **Step 3: Create `universal_user_prompt_v0.txt`**

Write this content:

```text
Please perform the evaluation for this image editing sample.

Inputs:
- image 1 = source image (Image A)
- image 2 = reference image (Image B)
- image 3 = edited image (Image C)
- prompt = "{PROMPT}"

Follow the system rules and output the required JSON only.

Reminder:
- Judge only from visible evidence in Image A, Image B, Image C, and P.
- Check instruction following, reference fidelity, source preservation, edit localization, physical/structural realism, and image quality.
- If any dimension fails, the overall result must fail.
- Use concise Chinese reasons.
```

- [ ] **Step 4: Verify prompt files exist**

Run:

```powershell
Get-ChildItem .\prompts -Recurse -File | Select-Object FullName, Length
```

Expected: output includes the three files above and each file has non-zero length.

---

### Task 3: Add Task Adapter Assets

**Files:**
- Create: `D:\Project\auto_eval\prompts\adapters\human_item_adapter_v0.txt`
- Create: `D:\Project\auto_eval\prompts\adapters\texture_transfer_adapter_v0.txt`

- [ ] **Step 1: Create `human_item_adapter_v0.txt`**

Write this content:

```text
Task Adapter: human_item

Use this adapter for person-object holding, grasping, carrying, or cradling edits.

Task-specific checks:

1. The person in Image C should realistically hold, grasp, carry, or cradle the target object from Image B as requested by P.

2. The target object in Image C should match Image B in core identity:
- object category
- requested or dominant visible color
- quantity
- main shape or silhouette
- prominent visible components
- distinctive visible style when relevant to P

3. Fail if the target object is missing, replaced by a different object, has the wrong quantity, has a clearly wrong dominant color, or loses its main recognizable identity.

4. The target object should have a plausible physical relationship with the person's hand, arm, body, or support surface. Check visible contact, support, occlusion, layering, and scale.

5. Fail if the target object clearly floats near the person, only rests on the body without support, is pasted near the hands, penetrates the hand/body, has impossible layering, or is far too large or too small for the intended interaction.

6. Minimal hand, wrist, or arm changes are allowed when needed to make the holding interaction realistic.

7. Do not fail only because the grasp is slightly stiff, some fingers are hidden, the wrist is mildly awkward, or small object details are simplified.

8. Fail if there are clear severe hand or limb artifacts, including duplicated hands, extra arms, impossible limb origins, disconnected limbs, fused fingers, broken fingers, or hand-object fusion that is visible and not explainable by occlusion.

9. Image A's non-target identity, face, clothing, background, and overall scene should remain unchanged except for minimal necessary interaction changes.

Recommended task error_types:
- object_count_mismatch
- object_identity_mismatch
- invalid_hand_object_interaction
- severe_hand_or_limb_artifact
```

- [ ] **Step 2: Create `texture_transfer_adapter_v0.txt`**

Write this content:

```text
Task Adapter: texture_transfer

Use this adapter for clothing texture transfer edits.

Task-specific checks:

1. Image C should transfer the texture from Image B to the exact clothing region in Image A specified by P.

2. The transferred texture should broadly match Image B in dominant color family, pattern type, density, scale, material impression, and overall visual style.

3. Reasonable adaptation to clothing folds, lighting, shadows, perspective, body shape, and garment deformation is allowed.

4. Fail if the target garment keeps important visible original texture, color, or pattern residue from Image A.

5. Fail if important visible target parts are missed, including visible sleeves, cuffs, collar, neckline, hem, hood, straps, trim, lining, inner visible target areas, or edges.

6. The edit should change only the target garment's surface texture. It should not redesign the garment.

7. Fail if the garment structure, silhouette, fit, length, opening, sleeve length, collar, neckline, cuff, zipper, button, pocket, hood, strap, pants length, hem, or layering clearly changes.

8. Fail if non-target garments, skin, face, hair, accessories, props, bags, background, or other unrelated regions are retextured, recolored, removed, merged, or visibly changed.

9. Fail if Image B's background, person, product display setting, or unrelated objects leak into Image C.

10. If the texture match is good but the clothing structure clearly changes, the sample should still fail.

Recommended task error_types:
- texture_not_transferred
- texture_mismatch
- garment_structure_changed
- non_target_garment_changed
```

- [ ] **Step 3: Verify adapter files exist**

Run:

```powershell
Get-ChildItem .\prompts\adapters -File | Select-Object FullName, Length
```

Expected: output includes both adapter files and each file has non-zero length.

---

### Task 4: Add JSON Configs

**Files:**
- Create: `D:\Project\auto_eval\configs\output_schema.json`
- Create: `D:\Project\auto_eval\configs\error_taxonomy.json`
- Create: `D:\Project\auto_eval\configs\task_adapter_config.json`

- [ ] **Step 1: Create `output_schema.json`**

Write this JSON:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Universal Image Editing QC Output",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "is_passed",
    "instruction_following",
    "reference_fidelity",
    "source_preservation",
    "edit_localization",
    "physical_and_structural_realism",
    "image_quality_and_artifacts"
  ],
  "properties": {
    "is_passed": {
      "type": "boolean"
    },
    "instruction_following": {
      "$ref": "#/$defs/dimension_result"
    },
    "reference_fidelity": {
      "$ref": "#/$defs/dimension_result"
    },
    "source_preservation": {
      "$ref": "#/$defs/dimension_result"
    },
    "edit_localization": {
      "$ref": "#/$defs/dimension_result"
    },
    "physical_and_structural_realism": {
      "$ref": "#/$defs/dimension_result"
    },
    "image_quality_and_artifacts": {
      "$ref": "#/$defs/dimension_result"
    }
  },
  "$defs": {
    "dimension_result": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "passed",
        "reason",
        "error_types"
      ],
      "properties": {
        "passed": {
          "type": "boolean"
        },
        "reason": {
          "type": "string"
        },
        "error_types": {
          "type": "array",
          "items": {
            "type": "string"
          }
        }
      }
    }
  }
}
```

- [ ] **Step 2: Create `error_taxonomy.json`**

Write this JSON:

```json
{
  "version": "v0",
  "common": {
    "wrong_target": "The edit is applied to the wrong object, person, or region.",
    "missing_core_edit": "The core requested edit is missing or visibly incomplete.",
    "reference_mismatch": "The result does not match the task-relevant content from Image B.",
    "source_preservation_failure": "Important non-target content from Image A is visibly changed.",
    "edit_overreach": "The edit affects visible non-target regions.",
    "physical_implausibility": "The result contains clear physical, anatomical, structural, contact, support, occlusion, perspective, or scale errors.",
    "reference_leakage": "Irrelevant background, person, environment, or objects from Image B leak into Image C.",
    "artifact_or_low_quality": "The result has obvious artifacts, corruption, deformation, or severe quality degradation."
  },
  "tasks": {
    "human_item": {
      "object_count_mismatch": "The target object quantity does not match Image B or P.",
      "object_identity_mismatch": "The target object category or main visible identity does not match Image B or P.",
      "invalid_hand_object_interaction": "The hand, body, and target object interaction is visibly unsupported or physically impossible.",
      "severe_hand_or_limb_artifact": "The edit introduces clear severe hand, finger, arm, or limb structure errors."
    },
    "texture_transfer": {
      "texture_not_transferred": "The target garment texture is missing, incomplete, or visibly retains important original texture.",
      "texture_mismatch": "The transferred texture's dominant color, pattern, density, scale, material, or visual identity clearly mismatches Image B.",
      "garment_structure_changed": "The target garment structure, boundary, silhouette, length, opening, or anchor details visibly change.",
      "non_target_garment_changed": "Non-target clothing or other non-target visible regions are changed."
    }
  }
}
```

- [ ] **Step 3: Create `task_adapter_config.json`**

Write this JSON:

```json
{
  "version": "v0",
  "universal_prompt": "prompts/universal/universal_qc_prompt_v0.txt",
  "universal_redlines": "prompts/universal/universal_redlines_v0.txt",
  "universal_user_prompt": "prompts/user/universal_user_prompt_v0.txt",
  "output_schema": "configs/output_schema.json",
  "error_taxonomy": "configs/error_taxonomy.json",
  "dimensions": [
    "instruction_following",
    "reference_fidelity",
    "source_preservation",
    "edit_localization",
    "physical_and_structural_realism",
    "image_quality_and_artifacts"
  ],
  "prompt_modes": {
    "original_task_prompt": "Use the existing task-specific system/user prompt files without universal prompt composition.",
    "universal_only": "Use only the universal system prompt and universal user prompt.",
    "universal_adapter": "Append the task adapter after the universal system prompt and use the universal user prompt."
  },
  "tasks": {
    "human_item": {
      "task_name": "human_item",
      "adapter": "prompts/adapters/human_item_adapter_v0.txt",
      "original_system_prompt": "code/human_item/prompts/system_prompt.txt",
      "original_user_prompt": "code/human_item/prompts/user_prompt.txt",
      "data_sample": "data/human_item/human_item_label_sample.json",
      "prompt_modes": [
        "original_task_prompt",
        "universal_only",
        "universal_adapter"
      ],
      "task_error_types": [
        "object_count_mismatch",
        "object_identity_mismatch",
        "invalid_hand_object_interaction",
        "severe_hand_or_limb_artifact"
      ]
    },
    "texture_transfer": {
      "task_name": "texture_transfer",
      "adapter": "prompts/adapters/texture_transfer_adapter_v0.txt",
      "original_system_prompt": "code/texture_person/prompts/system_prompt.txt",
      "original_user_prompt": "code/texture_person/prompts/user_prompt.txt",
      "data_sample": "data/texture_person/texture_person_label_sample.json",
      "prompt_modes": [
        "original_task_prompt",
        "universal_only",
        "universal_adapter"
      ],
      "task_error_types": [
        "texture_not_transferred",
        "texture_mismatch",
        "garment_structure_changed",
        "non_target_garment_changed"
      ]
    }
  }
}
```

- [ ] **Step 4: Validate JSON parsing**

Run:

```powershell
python -m json.tool .\configs\output_schema.json > $null
python -m json.tool .\configs\error_taxonomy.json > $null
python -m json.tool .\configs\task_adapter_config.json > $null
```

Expected: all three commands exit with code 0.

---

### Task 5: Add Prompt Optimizer Assets

**Files:**
- Create: `D:\Project\auto_eval\optimizer\prompt_optimizer_skill.md`
- Create: `D:\Project\auto_eval\optimizer\prompt_patch_schema.json`

- [ ] **Step 1: Create `prompt_optimizer_skill.md`**

Write this content:

```markdown
# Prompt Optimizer Skill v0

## Purpose

This skill helps improve image-editing QC prompts from model misjudgment cases. It is a constrained prompt patch assistant, not a free-form prompt rewriter.

## Inputs

- `task_type`: task name, such as `human_item` or `texture_transfer`
- `current_prompt`: current Universal Prompt, Adapter, or final task prompt
- `prompt_layer`: one of `universal`, `adapter`, or `final_task_prompt`
- `model_predictions`: model outputs with pass/fail, dimension results, reasons, and error_types when available
- `human_labels`: human pass/fail labels and dimension labels
- `fp_cases`: human fail but model pass cases
- `fn_cases`: human pass but model fail cases
- `model_reasons`: model reasoning text
- `human_reasons`: human annotation reasons
- `metrics`: Accuracy, Precision, Recall, F1, TP, TN, FP, FN, and dimension metrics
- `change_history`: previous prompt changes and rollback records

## Output

Return only a JSON object matching `optimizer/prompt_patch_schema.json`.

## Allowed Decisions

Choose exactly one:

- `rewrite_existing_rule`
- `merge_existing_rules`
- `add_general_rule`
- `delete_low_value_rule`
- `no_prompt_change_record_case`

## Modification Principles

1. Make the smallest useful change.
2. Do not append rules by default.
3. Do not overfit a single case.
4. Prefer rewriting or merging existing rules over adding new rules.
5. Only modify the prompt for frequent, severe, and generalizable errors.
6. If adding a rule, also compress or remove lower-value wording.
7. Low-frequency special cases should go to the error case library, not the main prompt.
8. Cross-task issues modify the Universal Prompt.
9. Task-specific issues modify the Task Adapter.
10. Every accepted change must be verified with before/after regression metrics.

## FP/FN Priority

For training-data filtering, FP is usually more dangerous than FN because bad data enters the training set. Prefer reducing FP and improving Precision, but reject changes that create a large FN increase without a clear reason.

## Required Reasoning

The optimizer must explain:

- why the problem is generalizable
- why the selected prompt layer is correct
- why the decision is smaller than a full rewrite
- what old wording is compressed or replaced
- expected impact on Precision, Recall, FP, and FN

## Forbidden Behavior

- Do not rewrite the whole prompt.
- Do not add a long case-specific checklist for one sample.
- Do not introduce task details into Universal Prompt.
- Do not delete strict redlines only to improve Recall.
- Do not output natural-language suggestions without a structured patch.
```

- [ ] **Step 2: Create `prompt_patch_schema.json`**

Write this JSON:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Prompt Optimizer Patch",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "task_type",
    "prompt_layer",
    "problem_type",
    "current_prompt_issue",
    "decision",
    "anti_bloat_action",
    "patch",
    "expected_impact",
    "regression_requirements"
  ],
  "properties": {
    "task_type": {
      "type": "string"
    },
    "prompt_layer": {
      "type": "string",
      "enum": [
        "universal",
        "adapter",
        "final_task_prompt"
      ]
    },
    "problem_type": {
      "type": "string"
    },
    "current_prompt_issue": {
      "type": "string"
    },
    "decision": {
      "type": "string",
      "enum": [
        "rewrite_existing_rule",
        "merge_existing_rules",
        "add_general_rule",
        "delete_low_value_rule",
        "no_prompt_change_record_case"
      ]
    },
    "anti_bloat_action": {
      "type": "string"
    },
    "patch": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "target_section",
        "before",
        "after"
      ],
      "properties": {
        "target_section": {
          "type": "string"
        },
        "before": {
          "type": "string"
        },
        "after": {
          "type": "string"
        }
      }
    },
    "expected_impact": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "precision",
        "recall",
        "fp",
        "fn"
      ],
      "properties": {
        "precision": {
          "type": "string"
        },
        "recall": {
          "type": "string"
        },
        "fp": {
          "type": "string"
        },
        "fn": {
          "type": "string"
        }
      }
    },
    "regression_requirements": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  }
}
```

- [ ] **Step 3: Validate optimizer JSON**

Run:

```powershell
python -m json.tool .\optimizer\prompt_patch_schema.json > $null
```

Expected: command exits with code 0.

---

### Task 6: Add Phase 1 Asset Validator

**Files:**
- Create: `D:\Project\auto_eval\scripts\validate_prompt_assets.py`

- [ ] **Step 1: Create `validate_prompt_assets.py`**

Write this Python:

```python
#!/usr/bin/env python3
"""Validate prompt assets for the universal QC prompt project."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def read_text(path: Path) -> str:
    with path.open("r", encoding="utf-8-sig") as f:
        return f.read().strip()


def require_file(root: Path, relative_path: str) -> Path:
    path = root / relative_path
    if not path.is_file():
        raise FileNotFoundError(f"Missing file: {relative_path}")
    if path.stat().st_size == 0:
        raise ValueError(f"Empty file: {relative_path}")
    return path


def collect_error_types(taxonomy: dict[str, Any], task_name: str) -> set[str]:
    common = set(taxonomy.get("common", {}).keys())
    task_specific = set(taxonomy.get("tasks", {}).get(task_name, {}).keys())
    return common | task_specific


def validate_schema_dimensions(config: dict[str, Any], schema: dict[str, Any]) -> None:
    dimensions = config["dimensions"]
    required = schema.get("required", [])
    for dim in dimensions:
        if dim not in required:
            raise ValueError(f"Dimension {dim!r} missing from output_schema.required")
        if dim not in schema.get("properties", {}):
            raise ValueError(f"Dimension {dim!r} missing from output_schema.properties")


def validate_prompt_content(root: Path, config: dict[str, Any]) -> None:
    universal_prompt = read_text(require_file(root, config["universal_prompt"]))
    user_prompt = read_text(require_file(root, config["universal_user_prompt"]))
    require_file(root, config["universal_redlines"])

    if "{PROMPT}" not in user_prompt:
        raise ValueError("Universal user prompt must contain {PROMPT}")

    forbidden_task_terms = [
        "sleeve length",
        "cuff",
        "neckline",
        "zipper",
        "button",
        "pocket",
        "hold, grasp, carry, or cradle",
        "hand-object",
        "texture transfer edits",
    ]
    lowered = universal_prompt.lower()
    found = [term for term in forbidden_task_terms if term.lower() in lowered]
    if found:
        raise ValueError(f"Universal prompt appears task-contaminated: {found}")


def validate_tasks(root: Path, config: dict[str, Any], taxonomy: dict[str, Any]) -> None:
    prompt_modes = set(config["prompt_modes"].keys())
    for task_name, task_config in config["tasks"].items():
        require_file(root, task_config["adapter"])
        require_file(root, task_config["original_system_prompt"])
        require_file(root, task_config["original_user_prompt"])
        require_file(root, task_config["data_sample"])

        unknown_modes = set(task_config["prompt_modes"]) - prompt_modes
        if unknown_modes:
            raise ValueError(f"{task_name} has unknown prompt modes: {sorted(unknown_modes)}")

        allowed_error_types = collect_error_types(taxonomy, task_name)
        unknown_error_types = set(task_config["task_error_types"]) - allowed_error_types
        if unknown_error_types:
            raise ValueError(
                f"{task_name} has unknown task_error_types: {sorted(unknown_error_types)}"
            )


def build_preview(root: Path, config: dict[str, Any], task_name: str, mode: str) -> str:
    task_config = config["tasks"][task_name]
    if mode == "original_task_prompt":
        return read_text(root / task_config["original_system_prompt"])
    if mode == "universal_only":
        return read_text(root / config["universal_prompt"])
    if mode == "universal_adapter":
        universal = read_text(root / config["universal_prompt"])
        adapter = read_text(root / task_config["adapter"])
        return f"{universal}\n\n---\n\n{adapter}"
    raise ValueError(f"Unknown mode: {mode}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        default=str(ROOT),
        help="Project root. Defaults to the parent of the scripts directory.",
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Print composed prompt preview lengths.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(args.root).resolve()
    config = load_json(require_file(root, "configs/task_adapter_config.json"))
    schema = load_json(require_file(root, config["output_schema"]))
    taxonomy = load_json(require_file(root, config["error_taxonomy"]))

    validate_schema_dimensions(config, schema)
    validate_prompt_content(root, config)
    validate_tasks(root, config, taxonomy)
    require_file(root, "optimizer/prompt_optimizer_skill.md")
    require_file(root, "optimizer/prompt_patch_schema.json")

    if args.preview:
        for task_name, task_config in config["tasks"].items():
            for mode in task_config["prompt_modes"]:
                prompt = build_preview(root, config, task_name, mode)
                print(f"{task_name} {mode}: {len(prompt)} chars")

    print("Prompt assets validation passed.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run validator**

Run:

```powershell
python .\scripts\validate_prompt_assets.py --preview
```

Expected:

```text
human_item original_task_prompt: <non-zero> chars
human_item universal_only: <non-zero> chars
human_item universal_adapter: <non-zero> chars
texture_transfer original_task_prompt: <non-zero> chars
texture_transfer universal_only: <non-zero> chars
texture_transfer universal_adapter: <non-zero> chars
Prompt assets validation passed.
```

- [ ] **Step 3: Commit if git is available**

Run:

```powershell
git add prompts configs optimizer scripts docs/superpowers
git commit -m "feat: add universal qc prompt assets"
```

Expected if git is installed: commit succeeds.

Expected in the current local environment: `git` may not be recognized; record that no commit was created.

---

### Task 7: Phase 1 User Experiment Checkpoint

**Files:**
- Read: `D:\Project\auto_eval\prompts\universal\universal_qc_prompt_v0.txt`
- Read: `D:\Project\auto_eval\prompts\adapters\human_item_adapter_v0.txt`
- Read: `D:\Project\auto_eval\prompts\adapters\texture_transfer_adapter_v0.txt`
- Read: `D:\Project\auto_eval\configs\task_adapter_config.json`

- [ ] **Step 1: Package handoff summary**

Report these exact experiment modes to the user:

```text
Phase 1 assets are ready.

Run three prompt modes on the work computer:
1. original_task_prompt
2. universal_only
3. universal_adapter

For human_item:
- original system/user prompts: code/human_item/prompts/
- universal only: prompts/universal/universal_qc_prompt_v0.txt + prompts/user/universal_user_prompt_v0.txt
- universal adapter: universal_qc_prompt_v0.txt + prompts/adapters/human_item_adapter_v0.txt + universal_user_prompt_v0.txt

For texture_transfer:
- original system/user prompts: code/texture_person/prompts/
- universal only: prompts/universal/universal_qc_prompt_v0.txt + prompts/user/universal_user_prompt_v0.txt
- universal adapter: universal_qc_prompt_v0.txt + prompts/adapters/texture_transfer_adapter_v0.txt + universal_user_prompt_v0.txt

Please bring back:
- overall Accuracy / Precision / Recall / F1 / TP / TN / FP / FN
- per-dimension metrics if available
- FP cases with model reason and human reason
- FN cases with model reason and human reason
- any schema parse failures
```

- [ ] **Step 2: Stop implementation**

Do not begin Phase 2 until the user returns work-computer experiment results or explicitly asks to continue without them.

---

### Task 8: Create Phase 2 Tests for Prompt Assets Library

**Files:**
- Create: `D:\Project\auto_eval\tests\test_prompt_assets.py`
- Create: `D:\Project\auto_eval\scripts\prompt_assets.py`

- [ ] **Step 1: Create failing tests**

Write this Python test file:

```python
from pathlib import Path

import pytest

from scripts.prompt_assets import PromptAssetConfig, compose_system_prompt


ROOT = Path(__file__).resolve().parents[1]


def test_load_config_knows_two_tasks():
    config = PromptAssetConfig.load(ROOT / "configs" / "task_adapter_config.json")
    assert set(config.tasks.keys()) == {"human_item", "texture_transfer"}


def test_universal_adapter_contains_universal_and_adapter_text():
    config = PromptAssetConfig.load(ROOT / "configs" / "task_adapter_config.json")
    prompt = compose_system_prompt(config, "human_item", "universal_adapter")
    assert "You are a strict image-editing quality inspector." in prompt
    assert "Task Adapter: human_item" in prompt


def test_universal_only_excludes_adapter_text():
    config = PromptAssetConfig.load(ROOT / "configs" / "task_adapter_config.json")
    prompt = compose_system_prompt(config, "texture_transfer", "universal_only")
    assert "Task Adapter: texture_transfer" not in prompt


def test_unknown_task_fails():
    config = PromptAssetConfig.load(ROOT / "configs" / "task_adapter_config.json")
    with pytest.raises(KeyError):
        compose_system_prompt(config, "unknown_task", "universal_only")


def test_unknown_mode_fails():
    config = PromptAssetConfig.load(ROOT / "configs" / "task_adapter_config.json")
    with pytest.raises(ValueError):
        compose_system_prompt(config, "human_item", "unknown_mode")
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
python -m pytest .\tests\test_prompt_assets.py -v
```

Expected: FAIL because `scripts.prompt_assets` does not exist yet.

- [ ] **Step 3: Implement `prompt_assets.py`**

Write this Python:

```python
#!/usr/bin/env python3
"""Prompt asset loading and composition helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PromptAssetConfig:
    root: Path
    raw: dict[str, Any]

    @classmethod
    def load(cls, path: Path) -> "PromptAssetConfig":
        path = path.resolve()
        with path.open("r", encoding="utf-8-sig") as f:
            raw = json.load(f)
        return cls(root=path.parents[1], raw=raw)

    @property
    def tasks(self) -> dict[str, Any]:
        return self.raw["tasks"]

    def resolve(self, relative_path: str) -> Path:
        return self.root / relative_path

    def read_text(self, relative_path: str) -> str:
        with self.resolve(relative_path).open("r", encoding="utf-8-sig") as f:
            return f.read().strip()


def compose_system_prompt(config: PromptAssetConfig, task_name: str, mode: str) -> str:
    task = config.tasks[task_name]
    if mode not in task["prompt_modes"]:
        raise ValueError(f"Mode {mode!r} is not enabled for task {task_name!r}")

    if mode == "original_task_prompt":
        return config.read_text(task["original_system_prompt"])

    if mode == "universal_only":
        return config.read_text(config.raw["universal_prompt"])

    if mode == "universal_adapter":
        universal = config.read_text(config.raw["universal_prompt"])
        adapter = config.read_text(task["adapter"])
        return f"{universal}\n\n---\n\n{adapter}"

    raise ValueError(f"Unknown prompt mode: {mode}")


def get_user_prompt_template(config: PromptAssetConfig, task_name: str, mode: str) -> str:
    task = config.tasks[task_name]
    if mode not in task["prompt_modes"]:
        raise ValueError(f"Mode {mode!r} is not enabled for task {task_name!r}")

    if mode == "original_task_prompt":
        return config.read_text(task["original_user_prompt"])

    return config.read_text(config.raw["universal_user_prompt"])
```

- [ ] **Step 4: Run tests and verify pass**

Run:

```powershell
python -m pytest .\tests\test_prompt_assets.py -v
```

Expected: all tests pass.

---

### Task 9: Create Phase 2 Metrics Tests and Implementation

**Files:**
- Create: `D:\Project\auto_eval\tests\test_metrics.py`
- Create: `D:\Project\auto_eval\scripts\evaluate_prompt_suite.py`

- [ ] **Step 1: Create failing tests**

Write this Python test file:

```python
from scripts.evaluate_prompt_suite import calculate_metrics, parse_label


def test_parse_label_accepts_pass_fail_strings():
    assert parse_label("pass") is True
    assert parse_label("fail") is False
    assert parse_label(True) is True
    assert parse_label(False) is False


def test_calculate_metrics_counts_fp_fn():
    y_true = [True, False, True, False]
    y_pred = [True, True, False, False]
    metrics = calculate_metrics(y_true, y_pred)
    assert metrics["TP"] == 1
    assert metrics["FP"] == 1
    assert metrics["FN"] == 1
    assert metrics["TN"] == 1
    assert metrics["Accuracy"] == 0.5
    assert metrics["Precision"] == 0.5
    assert metrics["Recall"] == 0.5
    assert metrics["F1"] == 0.5
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
python -m pytest .\tests\test_metrics.py -v
```

Expected: FAIL because `scripts.evaluate_prompt_suite` does not exist yet.

- [ ] **Step 3: Implement metrics core in `evaluate_prompt_suite.py`**

Write this Python:

```python
#!/usr/bin/env python3
"""Offline evaluation utilities for prompt suite experiments."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_label(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"pass", "passed", "true", "1", "yes"}:
        return True
    if text in {"fail", "failed", "false", "0", "no"}:
        return False
    raise ValueError(f"Unsupported label: {value!r}")


def calculate_metrics(y_true: list[bool], y_pred: list[bool]) -> dict[str, Any]:
    if len(y_true) != len(y_pred):
        raise ValueError("y_true and y_pred must have the same length")

    tp = sum(1 for true, pred in zip(y_true, y_pred) if true and pred)
    tn = sum(1 for true, pred in zip(y_true, y_pred) if not true and not pred)
    fp = sum(1 for true, pred in zip(y_true, y_pred) if not true and pred)
    fn = sum(1 for true, pred in zip(y_true, y_pred) if true and not pred)
    total = len(y_true)

    accuracy = (tp + tn) / total if total else 0.0
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    return {
        "Total": total,
        "TP": tp,
        "TN": tn,
        "FP": fp,
        "FN": fn,
        "Accuracy": accuracy,
        "Precision": precision,
        "Recall": recall,
        "F1": f1,
    }


def load_records(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8-sig").strip()
    if not text:
        return []
    if path.suffix.lower() == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    obj = json.loads(text)
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        return [obj]
    raise ValueError(f"Unsupported record file: {path}")


def get_sample_id(record: dict[str, Any], index: int) -> str:
    return str(record.get("file_name") or record.get("index") or index)


def evaluate_offline(human_path: Path, model_path: Path) -> dict[str, Any]:
    human_records = load_records(human_path)
    model_records = load_records(model_path)
    human_by_id = {get_sample_id(item, idx): item for idx, item in enumerate(human_records)}

    y_true: list[bool] = []
    y_pred: list[bool] = []
    error_cases: list[dict[str, Any]] = []

    for idx, model in enumerate(model_records):
        sample_id = get_sample_id(model, idx)
        if sample_id not in human_by_id:
            continue
        human = human_by_id[sample_id]
        true_label = parse_label(human.get("groundtruth"))
        pred_label = parse_label(model.get("is_passed"))
        y_true.append(true_label)
        y_pred.append(pred_label)
        if true_label != pred_label:
            error_cases.append(
                {
                    "sample_id": sample_id,
                    "error_type": "FN" if true_label and not pred_label else "FP",
                    "human": human,
                    "model": model,
                }
            )

    return {
        "overall": calculate_metrics(y_true, y_pred),
        "error_cases": error_cases,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--human-json", required=True)
    parser.add_argument("--model-json", required=True)
    parser.add_argument("--report-json", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = evaluate_offline(Path(args.human_json), Path(args.model_json))
    output_path = Path(args.report_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Report saved to: {output_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests and verify pass**

Run:

```powershell
python -m pytest .\tests\test_metrics.py -v
```

Expected: all tests pass.

---

### Task 10: Add Report Comparison Script

**Files:**
- Create: `D:\Project\auto_eval\scripts\compare_prompt_reports.py`

- [ ] **Step 1: Implement report comparison**

Write this Python:

```python
#!/usr/bin/env python3
"""Compare prompt experiment reports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


METRIC_KEYS = ["Accuracy", "Precision", "Recall", "F1", "TP", "TN", "FP", "FN"]


def load_report(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def format_value(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def build_markdown(rows: list[tuple[str, Path, dict[str, Any]]]) -> str:
    lines = ["# Prompt Comparison Report", ""]
    lines.append("| Mode | " + " | ".join(METRIC_KEYS) + " |")
    lines.append("| --- | " + " | ".join("---" for _ in METRIC_KEYS) + " |")
    for mode, _path, report in rows:
        metrics = report["overall"]
        values = [format_value(metrics.get(key, "")) for key in METRIC_KEYS]
        lines.append(f"| {mode} | " + " | ".join(values) + " |")
    lines.append("")
    lines.append("FP is human Fail but model Pass. FN is human Pass but model Fail.")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report",
        action="append",
        nargs=2,
        metavar=("MODE", "PATH"),
        required=True,
        help="Report mode name and report JSON path. Repeat for multiple modes.",
    )
    parser.add_argument("--output-md", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = [(mode, Path(path), load_report(Path(path))) for mode, path in args.report]
    markdown = build_markdown(rows)
    output_path = Path(args.output_md)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")
    print(f"Comparison report saved to: {output_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Syntax check scripts**

Run:

```powershell
python -m py_compile .\scripts\prompt_assets.py .\scripts\evaluate_prompt_suite.py .\scripts\compare_prompt_reports.py .\scripts\validate_prompt_assets.py
```

Expected: command exits with code 0.

- [ ] **Step 3: Run all tests**

Run:

```powershell
python -m pytest .\tests -v
```

Expected: all tests pass.

---

## Plan Self-Review

Spec coverage:

- Prompt assets are covered by Tasks 1-3.
- JSON schema, taxonomy, and task mapping are covered by Task 4.
- Prompt optimizer workflow and patch schema are covered by Task 5.
- Phase 1 validation is covered by Task 6.
- User experiment pause is covered by Task 7.
- Phase 2 prompt composition is covered by Task 8.
- Phase 2 offline metrics are covered by Task 9.
- Phase 2 comparison reports are covered by Task 10.

Placeholder scan:

- No `TBD`, `TODO`, or unspecified implementation steps are intentionally left in this plan.

Type consistency:

- The six universal dimensions match between Universal Prompt, output schema, and task adapter config.
- Prompt modes match across config, validator, and prompt assets library.
- Error type names match between taxonomy and task adapter config.

Execution note:

- The current local machine may not have `git` in PATH. Commit steps should be attempted only if `git` is available; otherwise record that files were created without a local commit.
