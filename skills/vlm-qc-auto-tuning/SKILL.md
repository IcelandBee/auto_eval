---
name: vlm-qc-auto-tuning
description: Use when tuning VLM-as-a-judge prompts for image-editing QC from stable task prompts, human labels, eval reports, FP/FN bad cases, and iterative prompt versions
---

# VLM QC Auto Tuning

## Core Intent

Tune an already initialized task-specific VLM QC prompt through repeatable evaluation, FP/FN inspection, optimizer input construction, prompt revision, and version comparison.

This skill is for iterative tuning only. If a task-specific initial prompt does not exist yet, use `vlm-qc-prompt-initialization` first.

## No Defaults Rule

Do not use default values for any parameter.

Before running a command, writing a file, selecting data, or choosing an iteration target, confirm every required value from the user's request or an explicit artifact produced earlier in the same workflow. If a required value is missing, stop and ask the user for it. Ask only for blocker information.

Examples, placeholder paths, previous project habits, and command snippets are not defaults. Treat them as templates only.

## Startup Gate

At the beginning of every auto-tuning run, confirm the Python runtime first.

If the user has not explicitly provided the Python environment name or Python executable path, stop and ask for one of:

- Python executable path, such as `<python_executable>`;
- environment name plus runner, such as `conda run -n <env_name> python` or another user-approved command prefix.

Do not assume a Conda environment, virtualenv, system Python, bundled Python, or machine-specific path.

## Required Inputs

Collect the required inputs for the requested operation before acting:

- Python runtime command or executable path;
- task name;
- current prompt version;
- next prompt version, when writing a revised prompt;
- prompt directory for the current version;
- human-label JSON or JSONL path;
- image root;
- model API base URL;
- model API key source or value;
- model name;
- any decoding parameters required for reproducible comparison;
- model output JSONL path;
- evaluation report JSON path;
- bad-cases JSON path;
- optimizer rules file path or explicit tuning rules;
- optimizer input JSON path;
- comparison report output path, when comparing versions;
- stop criteria, such as max iterations, target precision, FP tolerance, FN/recall tolerance, or user-defined review checkpoint.

If only part of a command can be built, ask for the missing values before running it. Do not fill gaps with a task name, version, path, model, or threshold from earlier examples unless the user explicitly chose that value for the current run.

## Required Loop

Run this loop for each prompt version:

1. Confirm all inputs needed for the current step.
2. Run VLM evaluation with `--mode task_prompt --prompt-version <current_version>`.
3. Produce model outputs and `eval_report.json` at user-confirmed paths.
4. Write `bad_cases.json`, with FP cases inspected first.
5. Build `optimizer_input.json`.
6. Use `optimizer_input.json` to propose or write the next prompt version.
7. Re-run evaluation and compare versions with the same confirmed data, model, decoding parameters, and image root.

Do not overwrite old prompt versions. Save every accepted prompt as a new user-confirmed version directory.

## Initialize or Inspect Current Version

If the requested current prompt version does not exist, do not create it with assumed sources. Ask the user whether to initialize it and collect:

- task name;
- target version;
- source system prompt path;
- source user prompt path;
- output prompt directory;
- overwrite policy.

Initialization command template:

```powershell
<python> scripts\init_task_prompt.py `
  --task <task> `
  --version <version> `
  --source-system <source_system_prompt> `
  --source-user <source_user_prompt>
```

If the prompt version already exists, inspect it instead of overwriting it.

## Run Evaluation

Use the project VLM runner with `task_prompt` mode after all command arguments are confirmed:

```powershell
<python> scripts\run_vlm_eval.py `
  --task <task> `
  --mode task_prompt `
  --prompt-version <current_version> `
  --input-json <human_label_json_or_jsonl> `
  --output-jsonl <model_outputs_jsonl> `
  --report-json <eval_report_json> `
  --image-root <image_root> `
  --base-url <base_url> `
  --api-key <api_key_or_env_value> `
  --model-name <model_name>
```

Add decoding or runtime flags only when the user provides them or an explicit earlier run artifact requires them for an apples-to-apples comparison.

## Extract Bad Cases

If an evaluation report exists but no bad-case file exists, confirm the output path before creating one:

```powershell
<python> scripts\evaluate_prompt_suite.py `
  --task <task> `
  --mode task_prompt `
  --human-json <human_label_json_or_jsonl> `
  --model-json <model_outputs_jsonl> `
  --report-json <eval_report_json> `
  --bad-cases-json <bad_cases_json>
```

Inspect FP before FN:

- FP = human fail but model pass.
- FP is the main risk because bad samples may enter the training set.

## Build Optimizer Input

Create the LLM-ready optimization packet only after confirming every source and destination:

```powershell
<python> scripts\optimize_prompt_iteration.py `
  --task <task> `
  --prompt-version <current_version> `
  --eval-report <eval_report_json> `
  --bad-cases-json <bad_cases_json> `
  --rules <optimizer_rules> `
  --output-json <optimizer_input_json>
```

The next prompt should be based on:

- recurring FP patterns,
- metrics,
- human reasons,
- model reasons,
- current prompt text,
- optimization rules.

## Write Next Version

Before creating the next version, confirm:

- current version directory;
- next version identifier;
- next version directory;
- whether to copy the current version first;
- whether the user wants direct file edits or a reviewable proposal first.

When writing the next version:

- copy the current version to the next version first, unless the user chose a different workflow;
- edit only the rules needed for recurring, visible, generalizable FP/FN patterns;
- prefer FP reduction and Precision improvement;
- do not add a long one-case checklist;
- preserve tolerance for invisible, cropped, occluded, blurry, tiny, shadowed, or ambiguous regions.

High-risk FP patterns to inspect for image-editing QC:

- original unwanted texture, color, pattern, object, or artifact remains on important target regions;
- non-target regions are changed;
- source structure changes beyond the task requirement;
- important boundaries, shapes, layout, identity, count, text, or functional details change when they should be preserved.

## Compare Versions

After evaluating the next version, compare reports with user-confirmed labels and output path:

```powershell
<python> scripts\compare_prompt_reports.py `
  --report <current_label> <current_eval_report_json> `
  --report <next_label> <next_eval_report_json> `
  --output-md <comparison_output_md>
```

Primary metrics:

- Precision
- FP
- Recall
- FN
- F1

Accept a new prompt version only when FP/Precision improves without an unacceptable FN/Recall regression. The unacceptable regression threshold must come from the user or a confirmed project rule, not from this skill.

## Stop Conditions

Stop or pause when a user-confirmed condition is met:

- maximum planned iterations reached;
- Precision reaches the target;
- FP no longer decreases;
- FN increases beyond tolerance;
- remaining errors are too ambiguous or not visibly verifiable;
- the user requested a review checkpoint.

If no stop condition was provided, ask before starting the loop.

## Verification

Before claiming the loop is ready, run the user-confirmed verification commands with the confirmed Python runtime. Do not assume a test command or preview target is acceptable if the user has not approved it for the current environment.

Common project verification templates:

```powershell
<python> -m pytest
<python> scripts\validate_prompt_assets.py
<python> scripts\evaluate_prompt_suite.py --preview-prompts
```

Expected preview entries must be checked against the user-confirmed task and mode.

## Do Not Do

- Do not use hard-coded defaults when required inputs are missing.
- Do not start without a confirmed Python runtime command or executable path.
- Do not assume task name, prompt version, paths, model, API endpoint, API key, decoding parameters, stop criteria, or thresholds.
- Do not silently reuse machine-specific paths or previous examples.
- Do not build LLM prompt initialization from human labels in this skill.
- Do not split labels into initialization and validation sets unless requested.
- Do not return to universal-only or universal-adapter as the main loop unless requested.
- Do not overwrite any prompt version without explicit instruction.
- Do not optimize for Accuracy while ignoring FP.
