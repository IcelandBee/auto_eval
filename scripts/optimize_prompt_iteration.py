#!/usr/bin/env python3
"""Build optimizer input for one prompt iteration."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def read_text(path: Path) -> str:
    with path.open("r", encoding="utf-8-sig") as f:
        return f.read().strip()


def get_prompt_dir(root: Path, task: str, prompt_version: str) -> Path:
    return root / "prompts" / "tasks" / task / prompt_version


def collect_error_type_counts(cases: list[dict[str, Any]], error_type: str) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for case in cases:
        if case.get("error_type") != error_type:
            continue
        model = case.get("model", {})
        for value in model.values():
            if isinstance(value, dict):
                for item in value.get("error_types", []) or []:
                    counts[str(item)] += 1
    return dict(counts.most_common())


def build_optimizer_input(
    root: Path,
    task: str,
    prompt_version: str,
    report_path: Path,
    bad_cases_path: Path,
    rules_path: Path,
) -> dict[str, Any]:
    prompt_dir = get_prompt_dir(root, task, prompt_version)
    system_prompt_path = prompt_dir / "system_prompt.txt"
    user_prompt_path = prompt_dir / "user_prompt.txt"
    if not system_prompt_path.is_file():
        raise FileNotFoundError(f"System prompt not found: {system_prompt_path}")
    if not user_prompt_path.is_file():
        raise FileNotFoundError(f"User prompt not found: {user_prompt_path}")

    report = load_json(report_path)
    bad_cases = load_json(bad_cases_path)
    fp_cases = [case for case in bad_cases if case.get("error_type") == "FP"]
    fn_cases = [case for case in bad_cases if case.get("error_type") == "FN"]

    return {
        "task": task,
        "current_prompt_version": prompt_version,
        "current_prompt": {
            "system_prompt": read_text(system_prompt_path),
            "user_prompt": read_text(user_prompt_path),
        },
        "metrics": report.get("overall", {}),
        "fp_cases": fp_cases,
        "fn_cases": fn_cases,
        "fp_error_type_counts": collect_error_type_counts(bad_cases, "FP"),
        "fn_error_type_counts": collect_error_type_counts(bad_cases, "FN"),
        "optimization_rules": read_text(rules_path),
        "requested_output": {
            "next_prompt_version": "vNEXT",
            "system_prompt": "Full revised system prompt text.",
            "user_prompt": "Full revised user prompt text.",
            "change_summary": "Brief explanation of recurring FP/FN patterns addressed.",
            "expected_metric_impact": {
                "Precision": "increase",
                "FP": "decrease",
                "Recall": "avoid large regression",
                "FN": "avoid large increase",
            },
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", required=True)
    parser.add_argument("--prompt-version", required=True)
    parser.add_argument("--eval-report", required=True)
    parser.add_argument("--bad-cases-json", required=True)
    parser.add_argument("--rules", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--root", default=str(ROOT))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output = build_optimizer_input(
        root=Path(args.root),
        task=args.task,
        prompt_version=args.prompt_version,
        report_path=Path(args.eval_report),
        bad_cases_path=Path(args.bad_cases_json),
        rules_path=Path(args.rules),
    )
    output_path = Path(args.output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Optimizer input saved to: {output_path}")


if __name__ == "__main__":
    main()
