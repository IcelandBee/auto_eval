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

    @property
    def dimensions(self) -> list[str]:
        return list(self.raw["dimensions"])

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


def get_dimensions_for_mode(
    config: PromptAssetConfig,
    task_name: str,
    mode: str,
) -> list[str]:
    task = config.tasks[task_name]
    if mode not in task["prompt_modes"]:
        raise ValueError(f"Mode {mode!r} is not enabled for task {task_name!r}")

    if mode == "original_task_prompt":
        return list(task.get("legacy_dimensions", config.dimensions))

    return config.dimensions


def build_prompt_preview(config: PromptAssetConfig) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for task_name, task in config.tasks.items():
        for mode in task["prompt_modes"]:
            system_prompt = compose_system_prompt(config, task_name, mode)
            user_prompt = get_user_prompt_template(config, task_name, mode)
            rows.append(
                {
                    "task": task_name,
                    "mode": mode,
                    "system_prompt_chars": len(system_prompt),
                    "user_prompt_chars": len(user_prompt),
                }
            )
    return rows


def write_prompt_files(
    config: PromptAssetConfig,
    task_name: str,
    mode: str,
    output_dir: Path,
) -> dict[str, Path]:
    target_dir = output_dir / task_name / mode
    target_dir.mkdir(parents=True, exist_ok=True)

    system_prompt_path = target_dir / "system_prompt.txt"
    user_prompt_path = target_dir / "user_prompt.txt"

    system_prompt_path.write_text(
        compose_system_prompt(config, task_name, mode) + "\n",
        encoding="utf-8",
    )
    user_prompt_path.write_text(
        get_user_prompt_template(config, task_name, mode) + "\n",
        encoding="utf-8",
    )

    return {
        "system_prompt": system_prompt_path,
        "user_prompt": user_prompt_path,
    }
