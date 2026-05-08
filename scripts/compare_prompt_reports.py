#!/usr/bin/env python3
"""Compare prompt experiment reports."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


METRIC_KEYS = ["Accuracy", "Precision", "Recall", "F1", "TP", "TN", "FP", "FN"]


def load_report(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def format_value(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def collect_error_type_counts(report: dict[str, Any], fp_or_fn: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    for case in report.get("error_cases", []):
        if case.get("error_type") != fp_or_fn:
            continue
        model = case.get("model", {})
        for value in model.values():
            if isinstance(value, dict):
                for error_type in value.get("error_types", []) or []:
                    counts[str(error_type)] += 1
    return counts


def format_counts(counts: Counter[str]) -> str:
    if not counts:
        return ""
    return ", ".join(f"{key}: {value}" for key, value in counts.most_common())


def build_metric_table(rows: list[tuple[str, Path, dict[str, Any]]]) -> list[str]:
    lines = ["| Mode | " + " | ".join(METRIC_KEYS) + " |"]
    lines.append("| --- | " + " | ".join("---" for _ in METRIC_KEYS) + " |")
    for mode, _path, report in rows:
        metrics = report["overall"]
        values = [format_value(metrics.get(key, "")) for key in METRIC_KEYS]
        lines.append(f"| {mode} | " + " | ".join(values) + " |")
    return lines


def build_error_type_table(rows: list[tuple[str, Path, dict[str, Any]]]) -> list[str]:
    lines = ["| Mode | FP Error Types | FN Error Types |"]
    lines.append("| --- | --- | --- |")
    for mode, _path, report in rows:
        fp_counts = collect_error_type_counts(report, "FP")
        fn_counts = collect_error_type_counts(report, "FN")
        lines.append(f"| {mode} | {format_counts(fp_counts)} | {format_counts(fn_counts)} |")
    return lines


def build_markdown(rows: list[tuple[str, Path, dict[str, Any]]]) -> str:
    lines = ["# Prompt Comparison Report", ""]
    lines.extend(build_metric_table(rows))
    lines.append("")
    lines.append("FP is human Fail but model Pass. FN is human Pass but model Fail.")
    lines.append("")
    lines.append("## Error Type Counts")
    lines.append("")
    lines.extend(build_error_type_table(rows))
    lines.append("")
    lines.append("## Source Reports")
    lines.append("")
    for mode, path, _report in rows:
        lines.append(f"- {mode}: `{path}`")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report",
        action="append",
        nargs=2,
        metavar=("MODE", "PATH"),
        required=True,
        help="Report mode name and report JSON path. Repeat for multiple modes.",
    )
    parser.add_argument("--output-md", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = [(mode, Path(path), load_report(Path(path))) for mode, path in args.report]
    markdown = build_markdown(rows)
    output_path = Path(args.output_md)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")
    print(f"Comparison report saved to: {output_path}")


if __name__ == "__main__":
    main()
