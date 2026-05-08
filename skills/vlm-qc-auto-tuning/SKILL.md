---
name: vlm-qc-auto-tuning
description: Use when tuning VLM-as-a-judge prompts for image-editing QC from stable task prompts, human labels, eval reports, FP/FN bad cases, and iterative prompt versions
---

# VLM QC Auto Tuning

## Core Intent

Use Scheme A only:

- Reuse an already stable task prompt as `v0`.
- Do not generate the initial prompt from human labels yet.
- Focus on the automatic prompt-tuning loop.
- Make each iteration easy to inspect, rerun, and compare.

For the current `auto_eval` project, the first target is `texture_transfer` / `texture_person`.

## Default Project Setup

Use this Python on the work computer:

```powershell
C:\Work\Install\Miniconda3\envs\py312\python.exe
```

Default stable prompt source:

```text
code/texture_person/prompts/system_prompt.txt
code/texture_person/prompts/user_prompt.txt
```

Default versioned v0 target:

```text
prompts/tasks/texture_transfer/v0/system_prompt.txt
prompts/tasks/texture_transfer/v0/user_prompt.txt
```

Default optimization rules:

```text
optimizer/prompt_optimization_rules_v0.txt
```

## Required Loop

Run this loop for each prompt version:

1. Start from a versioned prompt, usually `texture_transfer/v0`.
2. Run VLM evaluation with `--mode task_prompt --prompt-version <version>`.
3. Produce model outputs and `eval_report.json`.
4. Write `bad_cases.json`, with FP cases inspected first.
5. Build `optimizer_input.json`.
6. Use `optimizer_input.json` to write the next prompt version.
7. Re-run evaluation and compare versions.

Do not overwrite old prompt versions. Save every accepted prompt as a new directory such as `v1`, `v2`, or `v3`.

## Initialize v0

Use this command when `prompts/tasks/texture_transfer/v0/` does not exist:

```powershell
C:\Work\Install\Miniconda3\envs\py312\python.exe scripts\init_task_prompt.py `
  --task texture_transfer `
  --version v0 `
  --source-system code\texture_person\prompts\system_prompt.txt `
  --source-user code\texture_person\prompts\user_prompt.txt
```

If v0 already exists, inspect it instead of overwriting it.

## Run Evaluation

Use the project VLM runner with `task_prompt` mode:

```powershell
C:\Work\Install\Miniconda3\envs\py312\python.exe scripts\run_vlm_eval.py `
  --task texture_transfer `
  --mode task_prompt `
  --prompt-version v0 `
  --input-json <human_label_json_or_jsonl> `
  --output-jsonl runs\texture_transfer\iter_000\model_outputs.jsonl `
  --report-json runs\texture_transfer\iter_000\eval_report.json `
  --image-root <image_root> `
  --base-url <base_url> `
  --api-key <api_key> `
  --model-name <model_name>
```

Use the same data, model, decoding parameters, and image root when comparing versions.

## Extract Bad Cases

If `run_vlm_eval.py` already produced a report but not a bad-case file, run:

```powershell
C:\Work\Install\Miniconda3\envs\py312\python.exe scripts\evaluate_prompt_suite.py `
  --task texture_transfer `
  --mode task_prompt `
  --human-json <human_label_json_or_jsonl> `
  --model-json runs\texture_transfer\iter_000\model_outputs.jsonl `
  --report-json runs\texture_transfer\iter_000\eval_report.json `
  --bad-cases-json runs\texture_transfer\iter_000\bad_cases.json
```

Inspect FP before FN:

- FP = human fail but model pass.
- FP is the main risk because bad samples may enter the training set.

## Build Optimizer Input

Create the LLM-ready optimization packet:

```powershell
C:\Work\Install\Miniconda3\envs\py312\python.exe scripts\optimize_prompt_iteration.py `
  --task texture_transfer `
  --prompt-version v0 `
  --eval-report runs\texture_transfer\iter_000\eval_report.json `
  --bad-cases-json runs\texture_transfer\iter_000\bad_cases.json `
  --rules optimizer\prompt_optimization_rules_v0.txt `
  --output-json runs\texture_transfer\iter_000\optimizer_input.json
```

The next prompt should be based on:

- recurring FP patterns,
- metrics,
- human reasons,
- model reasons,
- current prompt text,
- optimization rules.

## Write v1

When creating `v1`:

- Copy `v0` to `v1` first.
- Edit only the rules needed for recurring, visible, generalizable FP/FN patterns.
- Prefer FP reduction and Precision improvement.
- Do not add a long one-case checklist.
- Preserve tolerance for invisible, cropped, occluded, blurry, tiny, shadowed, or ambiguous regions.

Texture-transfer high-risk FP patterns:

- original texture/color/pattern remains on important target regions,
- non-target regions receive the transferred texture,
- garment structure changes,
- neckline, collar, cuff, sleeve length, hem, zipper, buttons, cutouts, straps, laces, pockets, hood, openings, silhouette, fit, or layering changes.

## Compare Versions

After running `v1`, compare reports:

```powershell
C:\Work\Install\Miniconda3\envs\py312\python.exe scripts\compare_prompt_reports.py `
  --report texture_transfer_v0 runs\texture_transfer\iter_000\eval_report.json `
  --report texture_transfer_v1 runs\texture_transfer\iter_001\eval_report.json `
  --output-md runs\texture_transfer\comparison_v0_v1.md
```

Primary metrics:

- Precision
- FP
- Recall
- FN
- F1

Accept a new prompt version only when FP/Precision improves without an unacceptable FN/Recall regression.

## Stop Conditions

Stop or pause when:

- maximum planned iterations are reached,
- Precision reaches the target,
- FP no longer decreases,
- FN increases beyond tolerance,
- the remaining errors are too ambiguous or not visibly verifiable.

## Verification

Before claiming the loop is ready, run:

```powershell
C:\Work\Install\Miniconda3\envs\py312\python.exe -m pytest
C:\Work\Install\Miniconda3\envs\py312\python.exe scripts\validate_prompt_assets.py
C:\Work\Install\Miniconda3\envs\py312\python.exe scripts\evaluate_prompt_suite.py --preview-prompts
```

Expected preview must include:

```text
texture_transfer task_prompt
```

## Do Not Do Yet

- Do not build LLM prompt initialization from the 100 human labels.
- Do not split the 100 labels into initialization and validation sets unless requested.
- Do not return to universal-only or universal-adapter as the main loop.
- Do not overwrite `v0`.
- Do not optimize for Accuracy while ignoring FP.
