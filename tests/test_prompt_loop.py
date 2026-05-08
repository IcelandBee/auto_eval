import json
from pathlib import Path

import pytest

from scripts.evaluate_prompt_suite import write_bad_cases
from scripts.init_task_prompt import init_task_prompt
from scripts.optimize_prompt_iteration import build_optimizer_input


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


def test_build_optimizer_input_contains_prompts_metrics_and_fp_cases(tmp_path):
    prompt_dir = tmp_path / "prompts" / "tasks" / "texture_transfer" / "v0"
    prompt_dir.mkdir(parents=True)
    (prompt_dir / "system_prompt.txt").write_text("SYSTEM", encoding="utf-8")
    (prompt_dir / "user_prompt.txt").write_text('prompt = "{PROMPT}"', encoding="utf-8")
    report_path = tmp_path / "eval_report.json"
    bad_cases_path = tmp_path / "bad_cases.json"
    rules_path = tmp_path / "rules.txt"
    report_path.write_text(
        json.dumps({"overall": {"FP": 2, "FN": 1, "Precision": 0.5}}),
        encoding="utf-8",
    )
    bad_cases_path.write_text(
        json.dumps(
            [
                {"sample_id": "a", "error_type": "FP"},
                {"sample_id": "b", "error_type": "FN"},
            ]
        ),
        encoding="utf-8",
    )
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
    assert result["current_prompt"]["user_prompt"] == 'prompt = "{PROMPT}"'
    assert result["metrics"]["FP"] == 2
    assert result["fp_cases"][0]["sample_id"] == "a"
    assert result["fn_cases"][0]["sample_id"] == "b"
    assert "Reduce FP first." in result["optimization_rules"]
