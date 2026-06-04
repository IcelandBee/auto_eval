#!/usr/bin/env python3
"""Run a config-driven MVP loop for VLM QC prompt auto tuning."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RESERVED_OUTPUT_FIELDS = {
    "is_passed",
    "passed",
    "reason",
    "error_types",
    "next_prompt_version",
    "system_prompt",
    "user_prompt",
    "change_summary",
}


@dataclass(frozen=True)
class AcceptancePolicy:
    max_fn_increase: int
    min_precision_delta: float
    require_fp_decrease: bool = True


@dataclass(frozen=True)
class AcceptanceDecision:
    accepted: bool
    reason: str


@dataclass(frozen=True)
class OrchestratorConfig:
    path: Path
    root: Path
    python: str
    task: str
    start_version: str
    max_iterations: int
    human_json: Path
    image_root: Path
    rules: Path
    artifact_root: Path
    vlm: dict[str, Any]
    optimizer: dict[str, Any]
    acceptance: AcceptancePolicy

    @classmethod
    def load(cls, path: Path) -> "OrchestratorConfig":
        path = path.resolve()
        raw = load_json(path)
        required = [
            "python",
            "task",
            "start_version",
            "max_iterations",
            "human_json",
            "image_root",
            "rules",
            "artifact_root",
            "vlm",
            "optimizer",
            "acceptance",
        ]
        missing = [key for key in required if key not in raw]
        if missing:
            raise ValueError(f"Missing required config field(s): {', '.join(missing)}")

        vlm = dict(raw["vlm"])
        require_mapping_fields(vlm, "vlm", ["base_url", "model_name"])
        require_api_key(vlm, "vlm")

        optimizer = dict(raw["optimizer"])
        require_mapping_fields(optimizer, "optimizer", ["base_url", "model_name"])
        require_api_key(optimizer, "optimizer")

        acceptance_raw = dict(raw["acceptance"])
        require_mapping_fields(
            acceptance_raw,
            "acceptance",
            ["max_fn_increase", "min_precision_delta"],
        )

        root = Path(raw.get("root", ROOT)).resolve()
        max_iterations = int(raw["max_iterations"])
        if max_iterations < 1:
            raise ValueError("max_iterations must be >= 1")

        return cls(
            path=path,
            root=root,
            python=str(raw["python"]),
            task=str(raw["task"]),
            start_version=str(raw["start_version"]),
            max_iterations=max_iterations,
            human_json=resolve_path(root, raw["human_json"]),
            image_root=resolve_path(root, raw["image_root"]),
            rules=resolve_path(root, raw["rules"]),
            artifact_root=resolve_path(root, raw["artifact_root"]),
            vlm=vlm,
            optimizer=optimizer,
            acceptance=AcceptancePolicy(
                max_fn_increase=int(acceptance_raw["max_fn_increase"]),
                min_precision_delta=float(acceptance_raw["min_precision_delta"]),
                require_fp_decrease=bool(acceptance_raw.get("require_fp_decrease", True)),
            ),
        )


def resolve_path(root: Path, value: str | os.PathLike[str]) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return root / path


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def extract_prompt_dimensions(system_prompt: str, user_prompt: str) -> list[str]:
    text = f"{system_prompt}\n{user_prompt}"
    dimensions: list[str] = []
    for match in re.finditer(r'"([a-z][a-z0-9_]*)"\s*:', text):
        field = match.group(1)
        if field in RESERVED_OUTPUT_FIELDS:
            continue
        if field not in dimensions:
            dimensions.append(field)
    return dimensions


def sync_task_prompt_config(
    *,
    config_path: Path,
    task: str,
    version: str,
    system_prompt: str,
    user_prompt: str,
) -> dict[str, Any]:
    raw = load_json(config_path)
    task_config = raw.setdefault("tasks", {}).setdefault(task, {})
    changed = False
    changes: list[str] = []

    prompt_modes = task_config.setdefault("prompt_modes", [])
    if "task_prompt" not in prompt_modes:
        prompt_modes.append("task_prompt")
        changed = True
        changes.append("enabled task_prompt mode")

    versions = task_config.setdefault("task_prompt_versions", [])
    if version not in versions:
        versions.append(version)
        changed = True
        changes.append(f"added prompt version {version}")

    if "default_task_prompt_version" not in task_config:
        task_config["default_task_prompt_version"] = version
        changed = True
        changes.append(f"set default prompt version to {version}")

    dimensions = extract_prompt_dimensions(system_prompt, user_prompt)
    if dimensions and task_config.get("task_prompt_dimensions") != dimensions:
        task_config["task_prompt_dimensions"] = dimensions
        changed = True
        changes.append("updated task prompt dimensions")

    if changed:
        write_json(config_path, raw)

    return {
        "updated": changed,
        "changes": changes,
        "dimensions": dimensions,
        "versions": list(task_config.get("task_prompt_versions", [])),
    }


def require_mapping_fields(mapping: dict[str, Any], label: str, fields: list[str]) -> None:
    missing = [field for field in fields if field not in mapping]
    if missing:
        raise ValueError(f"Missing required {label} field(s): {', '.join(missing)}")


def require_api_key(mapping: dict[str, Any], label: str) -> None:
    if "api_key" not in mapping and "api_key_env" not in mapping:
        raise ValueError(f"{label} requires api_key or api_key_env")


def get_api_key(mapping: dict[str, Any], label: str) -> str:
    if "api_key" in mapping:
        return str(mapping["api_key"])
    env_name = str(mapping["api_key_env"])
    value = os.environ.get(env_name)
    if not value:
        raise ValueError(f"{label} api_key_env is not set: {env_name}")
    return value


def strip_json_fence(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def find_json_object(text: str) -> str:
    stripped = strip_json_fence(text)
    if stripped.startswith("{"):
        return stripped

    start = stripped.find("{")
    if start < 0:
        raise ValueError("Optimizer response did not contain a JSON object")

    in_string = False
    escape = False
    depth = 0
    for index in range(start, len(stripped)):
        char = stripped[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return stripped[start : index + 1]

    raise ValueError("Optimizer response JSON braces are not balanced")


def parse_optimizer_response(text: str) -> dict[str, str]:
    parsed = json.loads(find_json_object(text))
    if not isinstance(parsed, dict):
        raise ValueError("Optimizer response must be a JSON object")
    required = ["next_prompt_version", "system_prompt", "user_prompt", "change_summary"]
    missing = [key for key in required if key not in parsed or not str(parsed[key]).strip()]
    if missing:
        raise ValueError(f"Optimizer response missing field(s): {', '.join(missing)}")
    if "{PROMPT}" not in str(parsed["user_prompt"]):
        raise ValueError('Optimizer user_prompt must contain "{PROMPT}"')
    return {key: str(parsed[key]).strip() for key in required}


def write_next_prompt_version(
    *,
    root: Path,
    task: str,
    version: str,
    system_prompt: str,
    user_prompt: str,
) -> dict[str, Path]:
    if "{PROMPT}" not in user_prompt:
        raise ValueError('User prompt must contain "{PROMPT}"')

    target_dir = root / "prompts" / "tasks" / task / version
    if target_dir.exists():
        raise FileExistsError(f"Task prompt version already exists: {target_dir}")
    target_dir.mkdir(parents=True)

    system_path = target_dir / "system_prompt.txt"
    user_path = target_dir / "user_prompt.txt"
    system_path.write_text(system_prompt.strip() + "\n", encoding="utf-8")
    user_path.write_text(user_prompt.strip() + "\n", encoding="utf-8")
    return {"system_prompt": system_path, "user_prompt": user_path}


def sync_prompt_version_from_files(root: Path, task: str, version: str) -> dict[str, Any]:
    prompt_dir = root / "prompts" / "tasks" / task / version
    system_prompt_path = prompt_dir / "system_prompt.txt"
    user_prompt_path = prompt_dir / "user_prompt.txt"
    if not system_prompt_path.is_file():
        raise FileNotFoundError(f"System prompt not found: {system_prompt_path}")
    if not user_prompt_path.is_file():
        raise FileNotFoundError(f"User prompt not found: {user_prompt_path}")

    return sync_task_prompt_config(
        config_path=root / "configs" / "task_adapter_config.json",
        task=task,
        version=version,
        system_prompt=system_prompt_path.read_text(encoding="utf-8-sig"),
        user_prompt=user_prompt_path.read_text(encoding="utf-8-sig"),
    )


def metric(report: dict[str, Any], name: str) -> float:
    return float(report.get("overall", {}).get(name, 0))


def accept_candidate(
    current_report: dict[str, Any],
    candidate_report: dict[str, Any],
    policy: AcceptancePolicy,
) -> AcceptanceDecision:
    current_fp = metric(current_report, "FP")
    candidate_fp = metric(candidate_report, "FP")
    current_fn = metric(current_report, "FN")
    candidate_fn = metric(candidate_report, "FN")
    precision_delta = metric(candidate_report, "Precision") - metric(current_report, "Precision")
    fn_delta = candidate_fn - current_fn

    if fn_delta > policy.max_fn_increase:
        return AcceptanceDecision(
            accepted=False,
            reason=f"FN increased by {fn_delta:g}, above limit {policy.max_fn_increase}",
        )
    if precision_delta < policy.min_precision_delta:
        return AcceptanceDecision(
            accepted=False,
            reason=(
                f"Precision delta {precision_delta:.4f} is below minimum "
                f"{policy.min_precision_delta:.4f}"
            ),
        )
    if policy.require_fp_decrease and candidate_fp >= current_fp:
        return AcceptanceDecision(
            accepted=False,
            reason=f"FP did not decrease: current={current_fp:g}, candidate={candidate_fp:g}",
        )
    if candidate_fp < current_fp:
        return AcceptanceDecision(
            accepted=True,
            reason=f"FP decreased from {current_fp:g} to {candidate_fp:g}",
        )
    return AcceptanceDecision(accepted=True, reason="Acceptance policy satisfied")


def increment_version(version: str) -> str:
    match = re.fullmatch(r"v(\d+)", version)
    if match:
        return f"v{int(match.group(1)) + 1}"
    raise ValueError(f"Cannot infer next version from {version!r}; use v<number> versions")


def run_command(command: list[str], cwd: Path) -> None:
    print("Running:", " ".join(command))
    subprocess.run(command, cwd=str(cwd), check=True)


def build_vlm_command(
    config: OrchestratorConfig,
    version: str,
    output_jsonl: Path,
    report_json: Path,
) -> list[str]:
    vlm_args = config.vlm.get("args", {})
    command = [
        config.python,
        "scripts/run_vlm_eval.py",
        "--task",
        config.task,
        "--mode",
        "task_prompt",
        "--prompt-version",
        version,
        "--input-json",
        str(config.human_json),
        "--output-jsonl",
        str(output_jsonl),
        "--report-json",
        str(report_json),
        "--image-root",
        str(config.image_root),
        "--base-url",
        str(config.vlm["base_url"]),
        "--api-key",
        get_api_key(config.vlm, "vlm"),
        "--model-name",
        str(config.vlm["model_name"]),
    ]
    for key, value in vlm_args.items():
        flag = "--" + str(key).replace("_", "-")
        if isinstance(value, bool):
            if value:
                command.append(flag)
        else:
            command.extend([flag, str(value)])
    return command


def run_evaluation(config: OrchestratorConfig, version: str, version_dir: Path) -> dict[str, Any]:
    output_jsonl = version_dir / "model_outputs.jsonl"
    report_json = version_dir / "eval_report.json"
    bad_cases_json = version_dir / "bad_cases.json"
    version_dir.mkdir(parents=True, exist_ok=True)

    run_command(build_vlm_command(config, version, output_jsonl, report_json), config.root)
    run_command(
        [
            config.python,
            "scripts/evaluate_prompt_suite.py",
            "--task",
            config.task,
            "--mode",
            "task_prompt",
            "--human-json",
            str(config.human_json),
            "--model-json",
            str(output_jsonl),
            "--report-json",
            str(report_json),
            "--bad-cases-json",
            str(bad_cases_json),
        ],
        config.root,
    )
    return load_json(report_json)


def build_optimizer_input(
    config: OrchestratorConfig,
    current_version: str,
    current_dir: Path,
) -> Path:
    output_json = current_dir / "optimizer_input.json"
    run_command(
        [
            config.python,
            "scripts/optimize_prompt_iteration.py",
            "--task",
            config.task,
            "--prompt-version",
            current_version,
            "--eval-report",
            str(current_dir / "eval_report.json"),
            "--bad-cases-json",
            str(current_dir / "bad_cases.json"),
            "--rules",
            str(config.rules),
            "--output-json",
            str(output_json),
        ],
        config.root,
    )
    return output_json


def build_optimizer_messages(
    optimizer_input: dict[str, Any],
    next_version: str,
) -> list[dict[str, str]]:
    user_payload = dict(optimizer_input)
    user_payload["requested_output"]["next_prompt_version"] = next_version
    return [
        {
            "role": "system",
            "content": (
                "You revise VLM-as-a-judge QC prompts. Return only valid JSON with "
                "next_prompt_version, system_prompt, user_prompt, change_summary. "
                "The user_prompt must contain {PROMPT}. Preserve JSON output requirements."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(user_payload, ensure_ascii=False, indent=2),
        },
    ]


def call_optimizer(config: OrchestratorConfig, optimizer_input_path: Path, next_version: str) -> dict[str, str]:
    try:
        from openai import OpenAI
    except ModuleNotFoundError as exc:
        raise RuntimeError("The openai package is required for optimizer calls") from exc

    client = OpenAI(
        base_url=str(config.optimizer["base_url"]),
        api_key=get_api_key(config.optimizer, "optimizer"),
        timeout=float(config.optimizer.get("timeout", 300)),
    )
    optimizer_input = load_json(optimizer_input_path)
    kwargs: dict[str, Any] = {
        "model": str(config.optimizer["model_name"]),
        "messages": build_optimizer_messages(optimizer_input, next_version),
        "temperature": float(config.optimizer.get("temperature", 0.1)),
        "max_tokens": int(config.optimizer.get("max_tokens", 8192)),
    }
    if config.optimizer.get("use_response_format"):
        kwargs["response_format"] = {"type": "json_object"}

    response = client.chat.completions.create(**kwargs)
    raw_text = str(response.choices[0].message.content or "")
    optimizer_input_path.with_name("optimizer_response.txt").write_text(raw_text, encoding="utf-8")
    return parse_optimizer_response(raw_text)


def run_loop(config: OrchestratorConfig) -> list[dict[str, Any]]:
    log: list[dict[str, Any]] = []
    config.artifact_root.mkdir(parents=True, exist_ok=True)
    current_version = config.start_version
    current_dir = config.artifact_root / current_version
    sync_prompt_version_from_files(config.root, config.task, current_version)
    current_report = run_evaluation(config, current_version, current_dir)

    for iteration in range(1, config.max_iterations + 1):
        next_version = increment_version(current_version)
        optimizer_input_path = build_optimizer_input(config, current_version, current_dir)
        proposed = call_optimizer(config, optimizer_input_path, next_version)
        if proposed["next_prompt_version"] != next_version:
            raise ValueError(
                f"Optimizer returned {proposed['next_prompt_version']!r}; expected {next_version!r}"
            )

        write_next_prompt_version(
            root=config.root,
            task=config.task,
            version=next_version,
            system_prompt=proposed["system_prompt"],
            user_prompt=proposed["user_prompt"],
        )
        sync_task_prompt_config(
            config_path=config.root / "configs" / "task_adapter_config.json",
            task=config.task,
            version=next_version,
            system_prompt=proposed["system_prompt"],
            user_prompt=proposed["user_prompt"],
        )

        candidate_dir = config.artifact_root / next_version
        candidate_report = run_evaluation(config, next_version, candidate_dir)
        decision = accept_candidate(current_report, candidate_report, config.acceptance)
        comparison_md = config.artifact_root / f"compare_{current_version}_{next_version}.md"
        run_command(
            [
                config.python,
                "scripts/compare_prompt_reports.py",
                "--report",
                current_version,
                str(current_dir / "eval_report.json"),
                "--report",
                next_version,
                str(candidate_dir / "eval_report.json"),
                "--output-md",
                str(comparison_md),
            ],
            config.root,
        )

        row = {
            "iteration": iteration,
            "current_version": current_version,
            "candidate_version": next_version,
            "accepted": decision.accepted,
            "reason": decision.reason,
            "change_summary": proposed["change_summary"],
            "comparison_report": str(comparison_md),
        }
        log.append(row)
        write_json(config.artifact_root / "iteration_log.json", log)

        if not decision.accepted:
            break

        current_version = next_version
        current_dir = candidate_dir
        current_report = candidate_report

    return log


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="Path to auto-tuning orchestrator JSON config.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = OrchestratorConfig.load(Path(args.config))
    log = run_loop(config)
    print(f"Iteration log saved to: {config.artifact_root / 'iteration_log.json'}")
    print(f"Iterations attempted: {len(log)}")


if __name__ == "__main__":
    main()
