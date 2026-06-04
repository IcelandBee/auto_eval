import json
from pathlib import Path

import pytest

from scripts.run_prompt_orchestrator import (
    AcceptancePolicy,
    OrchestratorConfig,
    accept_candidate,
    extract_prompt_dimensions,
    parse_optimizer_response,
    sync_task_prompt_config,
    write_next_prompt_version,
)


def test_config_requires_core_fields(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "python": "python",
                "task": "texture_transfer",
                "start_version": "v0",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="max_iterations"):
        OrchestratorConfig.load(config_path)


def test_parse_optimizer_response_extracts_fenced_json():
    response = """
```json
{
  "next_prompt_version": "v1",
  "system_prompt": "SYSTEM V1",
  "user_prompt": "USER {PROMPT}",
  "change_summary": "tighten FP redlines"
}
```
"""

    parsed = parse_optimizer_response(response)

    assert parsed["next_prompt_version"] == "v1"
    assert parsed["system_prompt"] == "SYSTEM V1"
    assert parsed["user_prompt"] == "USER {PROMPT}"
    assert parsed["change_summary"] == "tighten FP redlines"


def test_write_next_prompt_version_refuses_overwrite(tmp_path):
    root = tmp_path
    target = root / "prompts" / "tasks" / "texture_transfer" / "v1"
    target.mkdir(parents=True)

    with pytest.raises(FileExistsError):
        write_next_prompt_version(
            root=root,
            task="texture_transfer",
            version="v1",
            system_prompt="SYSTEM",
            user_prompt="USER {PROMPT}",
        )


def test_write_next_prompt_version_saves_prompt_files(tmp_path):
    result = write_next_prompt_version(
        root=tmp_path,
        task="texture_transfer",
        version="v1",
        system_prompt="SYSTEM",
        user_prompt="USER {PROMPT}",
    )

    assert result["system_prompt"].read_text(encoding="utf-8") == "SYSTEM\n"
    assert result["user_prompt"].read_text(encoding="utf-8") == "USER {PROMPT}\n"


def test_accept_candidate_prefers_fp_reduction_without_fn_regression():
    current = {"overall": {"FP": 3, "FN": 1, "Precision": 0.6, "Recall": 0.9}}
    candidate = {"overall": {"FP": 2, "FN": 1, "Precision": 0.7, "Recall": 0.9}}

    decision = accept_candidate(
        current,
        candidate,
        AcceptancePolicy(max_fn_increase=0, min_precision_delta=0.0),
    )

    assert decision.accepted is True
    assert "FP decreased" in decision.reason


def test_accept_candidate_rejects_fn_regression_beyond_policy():
    current = {"overall": {"FP": 3, "FN": 1, "Precision": 0.6, "Recall": 0.9}}
    candidate = {"overall": {"FP": 2, "FN": 3, "Precision": 0.7, "Recall": 0.7}}

    decision = accept_candidate(
        current,
        candidate,
        AcceptancePolicy(max_fn_increase=1, min_precision_delta=0.0),
    )

    assert decision.accepted is False
    assert "FN increased" in decision.reason


def test_extract_prompt_dimensions_from_output_json_template():
    prompt = """
Output format:
{
  "is_passed": true/false,
  "target_coverage": {"passed": true/false, "reason": "中文一句话"},
  "texture_consistency": {"passed": true/false, "reason": "中文一句话"},
  "structure_preservation": {"passed": true/false, "reason": "中文一句话"}
}
"""

    assert extract_prompt_dimensions(prompt, "") == [
        "target_coverage",
        "texture_consistency",
        "structure_preservation",
    ]


def test_sync_task_prompt_config_updates_versions_and_dimensions(tmp_path):
    config_path = tmp_path / "configs" / "task_adapter_config.json"
    config_path.parent.mkdir()
    config_path.write_text(
        json.dumps(
            {
                "tasks": {
                    "texture_transfer": {
                        "prompt_modes": ["task_prompt"],
                        "task_prompt_versions": ["v0"],
                        "default_task_prompt_version": "v0",
                        "task_prompt_dimensions": ["old_dimension"],
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    result = sync_task_prompt_config(
        config_path=config_path,
        task="texture_transfer",
        version="v1",
        system_prompt="""
{
  "is_passed": true/false,
  "new_dimension": {"passed": true/false, "reason": ""},
  "texture_consistency": {"passed": true/false, "reason": ""}
}
""",
        user_prompt="prompt = {PROMPT}",
    )

    updated = json.loads(config_path.read_text(encoding="utf-8"))
    task = updated["tasks"]["texture_transfer"]
    assert result["updated"] is True
    assert task["task_prompt_versions"] == ["v0", "v1"]
    assert task["task_prompt_dimensions"] == ["new_dimension", "texture_consistency"]
