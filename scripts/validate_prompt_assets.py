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

        for version in task_config.get("task_prompt_versions", []):
            task_prompt_dir = f"prompts/tasks/{task_name}/{version}"
            require_file(root, f"{task_prompt_dir}/system_prompt.txt")
            user_prompt = read_text(require_file(root, f"{task_prompt_dir}/user_prompt.txt"))
            if "{PROMPT}" not in user_prompt:
                raise ValueError(
                    f"{task_name} {version} task user prompt must contain {{PROMPT}}"
                )

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
    if mode == "task_prompt":
        version = task_config.get("default_task_prompt_version")
        versions = task_config.get("task_prompt_versions", [])
        if not version and versions:
            version = versions[0]
        if not version:
            raise ValueError(f"{task_name} task_prompt mode requires a task prompt version")
        return read_text(root / f"prompts/tasks/{task_name}/{version}/system_prompt.txt")
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
