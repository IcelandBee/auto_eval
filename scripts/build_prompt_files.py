#!/usr/bin/env python3
"""Export composed prompt files for prompt suite experiments."""

from __future__ import annotations

import argparse
from pathlib import Path

try:
    from prompt_assets import PromptAssetConfig, write_prompt_files
except ModuleNotFoundError:
    from scripts.prompt_assets import PromptAssetConfig, write_prompt_files


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/task_adapter_config.json")
    parser.add_argument(
        "--task",
        choices=["human_item", "texture_transfer", "all"],
        default="all",
    )
    parser.add_argument(
        "--mode",
        choices=["original_task_prompt", "universal_only", "universal_adapter", "all"],
        default="all",
    )
    parser.add_argument("--output-dir", default="prompt_builds")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = PromptAssetConfig.load(Path(args.config))
    output_dir = Path(args.output_dir)

    task_names = list(config.tasks.keys()) if args.task == "all" else [args.task]
    for task_name in task_names:
        task = config.tasks[task_name]
        modes = list(task["prompt_modes"]) if args.mode == "all" else [args.mode]
        for mode in modes:
            paths = write_prompt_files(config, task_name, mode, output_dir)
            print(
                f"{task_name} {mode}: "
                f"system={paths['system_prompt']} "
                f"user={paths['user_prompt']}"
            )


if __name__ == "__main__":
    main()
