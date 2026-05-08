# Texture Transfer Prompt Loop Design

## Background

This project uses VLM-as-a-judge to evaluate image-editing samples with:

- Image A: source image
- Image B: reference image or texture
- Image C: edited image
- P: edit instruction

The previous direction emphasized a universal QC prompt plus task adapters. Recent experiments on `texture_person` / `texture_transfer` showed that universal-only evaluation has high recall but weak precision:

- Total: 100
- TP: 48
- TN: 23
- FP: 28
- FN: 1
- Accuracy: 0.71
- Precision: 0.6316
- Recall: 0.9796
- F1: 0.768

The main risk is FP: human fail but model pass. For training-data filtering, FP is more dangerous than FN because bad samples can enter the training set.

The current goal is to simplify the project direction and build a debuggable minimum loop before expanding the framework.

## Goal

Build the minimum viable prompt-optimization loop for `texture_transfer` / `texture_person`.

After this loop exists, the user should be able to:

1. Initialize `texture_transfer` prompt version `v0`.
2. Run 100 labeled cases with `v0`.
3. Produce `eval_report.json`.
4. Automatically extract FP/FN bad cases.
5. Generate `optimizer_input.json` for an LLM prompt optimizer.
6. Manually or semi-automatically produce `v1`.
7. Run `v1` and compare `v0` vs `v1` on Precision, Recall, FP, and FN.

This is a lightweight, testable loop. It is not a full automatic prompt optimization platform yet.

## Non-Goals

This iteration does not:

- Split the 100 human-labeled cases into initialization and validation sets.
- Require LLM-generated prompt initialization.
- Require a fully automatic LLM optimizer that writes `v1` without review.
- Replace the existing VLM evaluation runner.
- Generalize all tasks at once.
- Force the task prompt into a universal prompt plus adapter structure.

The first target is `texture_transfer`, using the stable prompt files already tested under `code/texture_person/prompts/`.

## Recommended Approach

Use the stable prompt under `code/texture_person/prompts/` as the initial `v0` task prompt.

The prompt initialization stage is therefore a copy/import step in the minimum version:

```text
code/texture_person/prompts/system_prompt.txt
code/texture_person/prompts/user_prompt.txt
```

becomes:

```text
prompts/tasks/texture_transfer/v0/system_prompt.txt
prompts/tasks/texture_transfer/v0/user_prompt.txt
```

The automatic optimization stage starts by preparing high-quality optimizer inputs. The first version may stop at writing `optimizer_input.json`, allowing the user or Codex to write `v1` with human review. Full LLM automation can be added after the loop is proven.

## Directory Layout

New prompt versions:

```text
prompts/tasks/texture_transfer/
  v0/
    system_prompt.txt
    user_prompt.txt
  v1/
    system_prompt.txt
    user_prompt.txt
```

New experiment runs:

```text
runs/texture_transfer/
  iter_000/
    model_outputs.jsonl
    eval_report.json
    bad_cases.json
    optimizer_input.json
  iter_001/
    model_outputs.jsonl
    eval_report.json
    bad_cases.json
    optimizer_input.json
```

The run directory stores generated artifacts only. Prompt versions remain under `prompts/tasks/`.

## Components

### Task Prompt Assets

Task prompt assets are versioned prompt files. They are direct task prompts, not adapter fragments.

Each version contains:

- `system_prompt.txt`
- `user_prompt.txt`

Old versions must not be overwritten. A new prompt change creates a new version directory.

### Prompt Initialization Script

Add:

```text
scripts/init_task_prompt.py
```

Responsibilities:

- Create `prompts/tasks/<task>/v<version>/`.
- Copy a source system prompt and user prompt into that version.
- Refuse to overwrite an existing version unless an explicit overwrite flag is provided.

Minimum use case:

```powershell
C:\Work\Install\Miniconda3\envs\py312\python.exe scripts\init_task_prompt.py `
  --task texture_transfer `
  --version v0 `
  --source-system code\texture_person\prompts\system_prompt.txt `
  --source-user code\texture_person\prompts\user_prompt.txt
```

### Prompt Asset Loader Updates

Extend prompt loading so evaluation can use a direct task prompt version.

Minimum behavior:

- Existing modes continue to work.
- A new mode can load `prompts/tasks/<task>/<version>/system_prompt.txt`.
- The user prompt is loaded from the matching version directory.
- Dimensions for `texture_transfer` task prompts should match the stable prompt:
  - `instruction_following`
  - `texture_consistency`
  - `clothes_consistency`

The interface can be implemented either with:

- a new `task_prompt` mode plus `--prompt-version`, or
- explicit `--system-prompt` and `--user-prompt` arguments.

The preferred option is `task_prompt` plus `--prompt-version` because it keeps runs reproducible.

### Bad Case Extraction

The current `evaluate_prompt_suite.py` already returns `error_cases`. Add a dedicated artifact:

```text
bad_cases.json
```

It should include:

- `sample_id`
- `error_type`: `FP` or `FN`
- human label and reason fields
- model label and reason fields
- model dimension outputs

FP cases should be easy to inspect first.

### Optimizer Input Builder

Add:

```text
scripts/optimize_prompt_iteration.py
```

Minimum responsibilities:

- Read the current prompt version.
- Read `eval_report.json`.
- Read or derive FP/FN bad cases.
- Read prompt optimization rules.
- Write `optimizer_input.json`.

`optimizer_input.json` should include:

- task name
- current prompt version
- current system prompt
- current user prompt
- metrics
- FP cases
- FN cases
- summarized FP patterns when possible
- optimization rules
- requested output contract for the next prompt version

The first implementation does not need to call an LLM. It prepares the input that a human or Codex can use to produce `v1`.

### Comparison

Continue using:

```text
scripts/compare_prompt_reports.py
```

It should be usable to compare:

- `texture_transfer_v0`
- `texture_transfer_v1`

The most important comparison fields are:

- Precision
- Recall
- FP
- FN
- F1

## Data Flow

```text
stable prompt in code/
  -> init_task_prompt.py
  -> prompts/tasks/texture_transfer/v0/
  -> run_vlm_eval.py
  -> model_outputs.jsonl
  -> evaluate_prompt_suite.py
  -> eval_report.json + bad_cases.json
  -> optimize_prompt_iteration.py
  -> optimizer_input.json
  -> manually or semi-automatically write v1
  -> run/evaluate/compare again
```

## Prompt Optimization Rules

The loop should keep these rules explicit:

- Optimize for Precision first.
- FP reduction is the primary early objective.
- Do not accept large FN increases without a deliberate trade-off.
- Modify prompts only for recurring, visible, generalizable errors.
- Avoid overfitting one sample.
- Preserve tolerance for invisible, occluded, cropped, blurry, tiny, or ambiguous details.
- Save each accepted prompt as a new version.

For texture transfer, high-risk FP patterns include:

- Target garment structure changes but model passes.
- Original texture, color, or pattern remains in important visible target regions.
- Texture leaks into non-target regions.
- Structural anchors change, including neckline, collar, cuffs, sleeve length, hem, zipper, buttons, cutouts, straps, laces, pockets, hood, openings, silhouette, fit, or layering.

## Error Handling

Scripts should fail clearly when:

- The source prompt path does not exist.
- The target prompt version already exists and overwrite is not allowed.
- A task prompt version is requested but missing.
- A user prompt does not contain `{PROMPT}`.
- Evaluation records cannot be matched to human labels.
- Required dimensions do not match the selected prompt mode.

When possible, errors should include the task, version, and file path involved.

## Testing

Add focused tests for:

- Initializing a task prompt version from source files.
- Refusing to overwrite an existing version by default.
- Loading a direct task prompt version.
- Returning the expected texture-transfer dimensions for task prompt mode.
- Writing `bad_cases.json` from an evaluation report.
- Building `optimizer_input.json` with metrics, FP/FN cases, prompts, and rules.

Use the configured Python environment for verification:

```powershell
C:\Work\Install\Miniconda3\envs\py312\python.exe -m pytest
```

## Success Criteria

The minimum loop is successful when the user can run one complete `texture_transfer` iteration:

1. `v0` exists under `prompts/tasks/texture_transfer/v0/`.
2. `v0` can be used by the evaluation runner.
3. `eval_report.json` is produced.
4. `bad_cases.json` is produced with FP/FN cases.
5. `optimizer_input.json` is produced.
6. A reviewed `v1` can be saved as a new prompt version.
7. `v0` and `v1` reports can be compared.

The first version is allowed to be semi-automatic. The important milestone is a reliable, inspectable prompt iteration loop.
