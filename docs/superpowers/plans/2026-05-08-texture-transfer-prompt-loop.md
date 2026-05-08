# Texture Transfer Prompt Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the minimum prompt iteration loop for `texture_transfer`: initialize v0, load direct task prompt versions, emit bad cases, and build `optimizer_input.json`.

**Architecture:** Keep deterministic work in scripts and keep prompt workflow decisions in prompt/rules files. Extend existing prompt asset helpers so current universal/original modes keep working while the new `task_prompt` mode reads versioned prompt files from `prompts/tasks/<task>/<version>/`.

**Tech Stack:** Python 3.12, stdlib `argparse/json/pathlib/shutil`, existing pytest suite, configured interpreter `C:\Work\Install\Miniconda3\envs\py312\python.exe`.

---

## Files

- Modify: `scripts/prompt_assets.py` to support direct task prompt versions and dimensions.
- Modify: `scripts/run_vlm_eval.py` to accept `--prompt-version` and pass it to prompt loaders.
- Modify: `scripts/evaluate_prompt_suite.py` to optionally write `bad_cases.json`.
- Create: `scripts/init_task_prompt.py` to import stable prompts as versioned task prompts.
- Create: `scripts/optimize_prompt_iteration.py` to write `optimizer_input.json`.
- Create: `optimizer/prompt_optimization_rules_v0.txt` for the lightweight tuning rules.
- Modify: `configs/task_adapter_config.json` to enable `task_prompt` and task prompt dimensions.
- Modify: `tests/test_prompt_assets.py` for task prompt loading tests.
- Modify: `tests/test_run_vlm_eval.py` for request-building with task prompt versions.
- Modify: `tests/test_metrics.py` or create `tests/test_prompt_loop.py` for bad case and optimizer input tests.

---

### Task 1: Task Prompt Version Loading

**Files:**
- Modify: `configs/task_adapter_config.json`
- Modify: `scripts/prompt_assets.py`
- Modify: `tests/test_prompt_assets.py`

- [ ] **Step 1: Write failing tests**

Add tests showing that `task_prompt` reads `prompts/tasks/texture_transfer/v0/` and uses texture dimensions.

```python
def test_task_prompt_mode_loads_versioned_task_prompts(tmp_path):
    config_path = tmp_path / "configs" / "task_adapter_config.json"
    prompt_dir = tmp_path / "prompts" / "tasks" / "texture_transfer" / "v0"
    config_path.parent.mkdir(parents=True)
    prompt_dir.mkdir(parents=True)
    config_path.write_text(
        json.dumps(
            {
                "dimensions": ["reference_fidelity"],
                "tasks": {
                    "texture_transfer": {
                        "prompt_modes": ["task_prompt"],
                        "task_prompt_dimensions": [
                            "instruction_following",
                            "texture_consistency",
                            "clothes_consistency",
                        ],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    (prompt_dir / "system_prompt.txt").write_text("TASK SYSTEM", encoding="utf-8")
    (prompt_dir / "user_prompt.txt").write_text('prompt = "{PROMPT}"', encoding="utf-8")

    config = PromptAssetConfig.load(config_path)

    assert compose_system_prompt(config, "texture_transfer", "task_prompt", "v0") == "TASK SYSTEM"
    assert get_user_prompt_template(config, "texture_transfer", "task_prompt", "v0") == 'prompt = "{PROMPT}"'
    assert get_dimensions_for_mode(config, "texture_transfer", "task_prompt") == [
        "instruction_following",
        "texture_consistency",
        "clothes_consistency",
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
C:\Work\Install\Miniconda3\envs\py312\python.exe -m pytest tests\test_prompt_assets.py -q
```

Expected: FAIL because `compose_system_prompt()` does not accept `prompt_version` and `task_prompt` is unknown.

- [ ] **Step 3: Implement minimal prompt asset support**

Update function signatures:

```python
def compose_system_prompt(config, task_name, mode, prompt_version=None): ...
def get_user_prompt_template(config, task_name, mode, prompt_version=None): ...
```

Add helper:

```python
def get_task_prompt_path(task_name: str, prompt_version: str, filename: str) -> str:
    return f"prompts/tasks/{task_name}/{prompt_version}/{filename}"
```

For `task_prompt`, require `prompt_version`, read versioned system/user files, and use `task_prompt_dimensions` or `legacy_dimensions`.

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
C:\Work\Install\Miniconda3\envs\py312\python.exe -m pytest tests\test_prompt_assets.py -q
```

Expected: PASS.

---

### Task 2: Initialize v0 Task Prompt

**Files:**
- Create: `scripts/init_task_prompt.py`
- Create or modify: `tests/test_prompt_loop.py`

- [ ] **Step 1: Write failing tests**

Create tests for copying prompts and refusing overwrite.

```python
def test_init_task_prompt_copies_source_prompts(tmp_path):
    source_system = tmp_path / "source_system.txt"
    source_user = tmp_path / "source_user.txt"
    source_system.write_text("SYSTEM", encoding="utf-8")
    source_user.write_text('prompt = "{PROMPT}"', encoding="utf-8")

    result = init_task_prompt(
        root=tmp_path,
        task="texture_transfer",
        version="v0",
        source_system=source_system,
        source_user=source_user,
        overwrite=False,
    )

    assert result["system_prompt"].read_text(encoding="utf-8") == "SYSTEM\n"
    assert result["user_prompt"].read_text(encoding="utf-8") == 'prompt = "{PROMPT}"\n'


def test_init_task_prompt_refuses_existing_version(tmp_path):
    target = tmp_path / "prompts" / "tasks" / "texture_transfer" / "v0"
    target.mkdir(parents=True)
    source_system = tmp_path / "source_system.txt"
    source_user = tmp_path / "source_user.txt"
    source_system.write_text("SYSTEM", encoding="utf-8")
    source_user.write_text('prompt = "{PROMPT}"', encoding="utf-8")

    with pytest.raises(FileExistsError):
        init_task_prompt(tmp_path, "texture_transfer", "v0", source_system, source_user, False)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
C:\Work\Install\Miniconda3\envs\py312\python.exe -m pytest tests\test_prompt_loop.py -q
```

Expected: FAIL because `scripts.init_task_prompt` does not exist.

- [ ] **Step 3: Implement minimal script**

Implement `init_task_prompt()` plus CLI arguments:

```text
--task
--version
--source-system
--source-user
--root
--overwrite
```

Validate that user prompt contains `{PROMPT}`.

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
C:\Work\Install\Miniconda3\envs\py312\python.exe -m pytest tests\test_prompt_loop.py -q
```

Expected: PASS.

---

### Task 3: Evaluation Bad Case Artifact

**Files:**
- Modify: `scripts/evaluate_prompt_suite.py`
- Modify: `tests/test_prompt_loop.py`

- [ ] **Step 1: Write failing test**

Add a test that writes `bad_cases.json` from a report.

```python
def test_write_bad_cases_sorts_fp_before_fn(tmp_path):
    report = {
        "error_cases": [
            {"sample_id": "fn", "error_type": "FN"},
            {"sample_id": "fp", "error_type": "FP"},
        ]
    }
    output = tmp_path / "bad_cases.json"

    write_bad_cases(report, output)

    cases = json.loads(output.read_text(encoding="utf-8"))
    assert [case["sample_id"] for case in cases] == ["fp", "fn"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
C:\Work\Install\Miniconda3\envs\py312\python.exe -m pytest tests\test_prompt_loop.py -q
```

Expected: FAIL because `write_bad_cases` does not exist.

- [ ] **Step 3: Implement bad case writer**

Add:

```python
def write_bad_cases(report: dict[str, Any], output_path: Path) -> list[dict[str, Any]]:
    cases = sorted(report.get("error_cases", []), key=lambda item: 0 if item.get("error_type") == "FP" else 1)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding="utf-8")
    return cases
```

Add CLI option `--bad-cases-json`.

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
C:\Work\Install\Miniconda3\envs\py312\python.exe -m pytest tests\test_prompt_loop.py -q
```

Expected: PASS.

---

### Task 4: Optimizer Input Builder

**Files:**
- Create: `scripts/optimize_prompt_iteration.py`
- Create: `optimizer/prompt_optimization_rules_v0.txt`
- Modify: `tests/test_prompt_loop.py`

- [ ] **Step 1: Write failing test**

Add a test that builds optimizer input from prompt files, report, bad cases, and rules.

```python
def test_build_optimizer_input_contains_prompts_metrics_and_fp_cases(tmp_path):
    prompt_dir = tmp_path / "prompts" / "tasks" / "texture_transfer" / "v0"
    prompt_dir.mkdir(parents=True)
    (prompt_dir / "system_prompt.txt").write_text("SYSTEM", encoding="utf-8")
    (prompt_dir / "user_prompt.txt").write_text('prompt = "{PROMPT}"', encoding="utf-8")
    report_path = tmp_path / "eval_report.json"
    bad_cases_path = tmp_path / "bad_cases.json"
    rules_path = tmp_path / "rules.txt"
    report_path.write_text(json.dumps({"overall": {"FP": 2, "FN": 1, "Precision": 0.5}}), encoding="utf-8")
    bad_cases_path.write_text(json.dumps([{"sample_id": "a", "error_type": "FP"}]), encoding="utf-8")
    rules_path.write_text("Reduce FP first.", encoding="utf-8")

    result = build_optimizer_input(
        root=tmp_path,
        task="texture_transfer",
        prompt_version="v0",
        report_path=report_path,
        bad_cases_path=bad_cases_path,
        rules_path=rules_path,
    )

    assert result["task"] == "texture_transfer"
    assert result["current_prompt"]["system_prompt"] == "SYSTEM"
    assert result["metrics"]["FP"] == 2
    assert result["fp_cases"][0]["sample_id"] == "a"
    assert "Reduce FP first." in result["optimization_rules"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
C:\Work\Install\Miniconda3\envs\py312\python.exe -m pytest tests\test_prompt_loop.py -q
```

Expected: FAIL because `scripts.optimize_prompt_iteration` does not exist.

- [ ] **Step 3: Implement optimizer input builder**

Implement:

```python
def build_optimizer_input(root, task, prompt_version, report_path, bad_cases_path, rules_path):
    ...
```

CLI arguments:

```text
--task
--prompt-version
--eval-report
--bad-cases-json
--rules
--output-json
--root
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
C:\Work\Install\Miniconda3\envs\py312\python.exe -m pytest tests\test_prompt_loop.py -q
```

Expected: PASS.

---

### Task 5: Wire Evaluation Runner to Task Prompt Versions

**Files:**
- Modify: `scripts/run_vlm_eval.py`
- Modify: `tests/test_run_vlm_eval.py`

- [ ] **Step 1: Write failing test**

Add a test that passes `prompt_version="v0"` to request building.

```python
def test_build_request_kwargs_uses_task_prompt_version(tmp_path):
    config_path = tmp_path / "configs" / "task_adapter_config.json"
    prompt_dir = tmp_path / "prompts" / "tasks" / "texture_transfer" / "v0"
    config_path.parent.mkdir(parents=True)
    prompt_dir.mkdir(parents=True)
    config_path.write_text(
        json.dumps(
            {
                "dimensions": ["reference_fidelity"],
                "tasks": {
                    "texture_transfer": {
                        "prompt_modes": ["task_prompt"],
                        "task_prompt_dimensions": [
                            "instruction_following",
                            "texture_consistency",
                            "clothes_consistency",
                        ],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    (prompt_dir / "system_prompt.txt").write_text("TASK SYSTEM", encoding="utf-8")
    (prompt_dir / "user_prompt.txt").write_text('Task prompt: "{PROMPT}"', encoding="utf-8")
    config = PromptAssetConfig.load(config_path)

    request = build_request_kwargs(
        config=config,
        task_name="texture_transfer",
        mode="task_prompt",
        prompt_version="v0",
        record={"prompt": "Transfer texture."},
        sample_idx=0,
        model_name="demo",
        image_urls=["src", "ref", "edt"],
        max_tokens=128,
        temperature=0,
        top_p=1,
        seed=1,
        top_k=1,
        repetition_penalty=1,
        min_pixels=1,
        max_pixels=2,
        max_soft_tokens=280,
        use_response_format=True,
    )

    assert request["messages"][0]["content"] == "TASK SYSTEM"
    assert "Transfer texture." in request["messages"][1]["content"][0]["text"]
    assert "texture_consistency" in request["response_format"]["json_schema"]["schema"]["properties"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
C:\Work\Install\Miniconda3\envs\py312\python.exe -m pytest tests\test_run_vlm_eval.py -q
```

Expected: FAIL because `build_request_kwargs` has no `prompt_version` parameter.

- [ ] **Step 3: Implement runner support**

Add optional `prompt_version` to `build_request_kwargs`, pass it to prompt asset helpers, add CLI argument `--prompt-version`, and require it when `--mode task_prompt`.

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
C:\Work\Install\Miniconda3\envs\py312\python.exe -m pytest tests\test_run_vlm_eval.py -q
```

Expected: PASS.

---

### Task 6: Create Real v0 Prompt Version and Verify Suite

**Files:**
- Generated: `prompts/tasks/texture_transfer/v0/system_prompt.txt`
- Generated: `prompts/tasks/texture_transfer/v0/user_prompt.txt`

- [ ] **Step 1: Run init script**

Run:

```powershell
C:\Work\Install\Miniconda3\envs\py312\python.exe scripts\init_task_prompt.py `
  --task texture_transfer `
  --version v0 `
  --source-system code\texture_person\prompts\system_prompt.txt `
  --source-user code\texture_person\prompts\user_prompt.txt
```

Expected: files created under `prompts/tasks/texture_transfer/v0/`.

- [ ] **Step 2: Run full test suite**

Run:

```powershell
C:\Work\Install\Miniconda3\envs\py312\python.exe -m pytest
```

Expected: all tests pass.

- [ ] **Step 3: Preview prompt assets**

Run:

```powershell
C:\Work\Install\Miniconda3\envs\py312\python.exe scripts\evaluate_prompt_suite.py --preview-prompts
```

Expected: output includes `texture_transfer task_prompt`.

