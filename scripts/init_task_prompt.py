#!/usr/bin/env python3
"""Initialize a versioned task prompt from existing prompt files."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_required_text(path: Path, label: str) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"{label} prompt not found: {path}")
    text = path.read_text(encoding="utf-8-sig").strip()
    if not text:
        raise ValueError(f"{label} prompt is empty: {path}")
    return text


def init_task_prompt(
    root: Path,
    task: str,
    version: str,
    source_system: Path,
    source_user: Path,
    overwrite: bool = False,
) -> dict[str, Path]:
    system_text = read_required_text(source_system, "system")
    user_text = read_required_text(source_user, "user")
    if "{PROMPT}" not in user_text:
        raise ValueError('User prompt must contain "{PROMPT}"')

    target_dir = root / "prompts" / "tasks" / task / version
    if target_dir.exists():
        if not overwrite:
            raise FileExistsError(f"Task prompt version already exists: {target_dir}")
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True)

    system_prompt = target_dir / "system_prompt.txt"
    user_prompt = target_dir / "user_prompt.txt"
    system_prompt.write_text(system_text + "\n", encoding="utf-8")
    user_prompt.write_text(user_text + "\n", encoding="utf-8")

    return {
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--source-system", required=True)
    parser.add_argument("--source-user", required=True)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = init_task_prompt(
        root=Path(args.root),
        task=args.task,
        version=args.version,
        source_system=Path(args.source_system),
        source_user=Path(args.source_user),
        overwrite=args.overwrite,
    )
    print(f"System prompt saved to: {result['system_prompt']}")
    print(f"User prompt saved to: {result['user_prompt']}")


if __name__ == "__main__":
    main()
