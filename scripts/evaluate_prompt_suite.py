#!/usr/bin/env python3
"""Offline evaluation utilities for prompt suite experiments."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from prompt_assets import PromptAssetConfig, build_prompt_preview, get_dimensions_for_mode
except ModuleNotFoundError:
    from scripts.prompt_assets import (
        PromptAssetConfig,
        build_prompt_preview,
        get_dimensions_for_mode,
    )


def parse_label(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"pass", "passed", "true", "1", "yes"}:
        return True
    if text in {"fail", "failed", "false", "0", "no"}:
        return False
    raise ValueError(f"Unsupported label: {value!r}")


def calculate_metrics(y_true: list[bool], y_pred: list[bool]) -> dict[str, Any]:
    if len(y_true) != len(y_pred):
        raise ValueError("y_true and y_pred must have the same length")

    tp = sum(1 for true, pred in zip(y_true, y_pred) if true and pred)
    tn = sum(1 for true, pred in zip(y_true, y_pred) if not true and not pred)
    fp = sum(1 for true, pred in zip(y_true, y_pred) if not true and pred)
    fn = sum(1 for true, pred in zip(y_true, y_pred) if true and not pred)
    total = len(y_true)

    accuracy = (tp + tn) / total if total else 0.0
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    return {
        "Total": total,
        "TP": tp,
        "TN": tn,
        "FP": fp,
        "FN": fn,
        "Accuracy": accuracy,
        "Precision": precision,
        "Recall": recall,
        "F1": f1,
    }


def load_records(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8-sig").strip()
    if not text:
        return []

    if path.suffix.lower() == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]

    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return [json.loads(line) for line in text.splitlines() if line.strip()]

    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        return [obj]
    raise ValueError(f"Unsupported record file: {path}")


def get_sample_id(record: dict[str, Any], index: int) -> str:
    return str(record.get("file_name") or record.get("index") or index)


def normalize_dimension_result(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        error_types = value.get("error_types", []) or []
        if isinstance(error_types, str):
            error_types = [error_types]
        return {
            "passed": parse_label(value.get("passed", False)),
            "reason": str(value.get("reason", "") or ""),
            "error_types": list(error_types),
        }

    return {
        "passed": parse_label(value),
        "reason": "",
        "error_types": [],
    }


def is_empty_label(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def get_human_dimension(record: dict[str, Any], dim: str) -> dict[str, Any] | None:
    if dim not in record:
        return None
    if is_empty_label(record[dim]):
        return None
    result = normalize_dimension_result(record[dim])
    reason_key = f"{dim}_reasoning"
    if reason_key in record and not result["reason"]:
        result["reason"] = str(record.get(reason_key, "") or "")
    return result


def get_model_dimension(record: dict[str, Any], dim: str) -> dict[str, Any] | None:
    if dim not in record:
        return None
    if is_empty_label(record[dim]):
        return None
    return normalize_dimension_result(record[dim])


def build_dimension_metrics(
    human_records: list[dict[str, Any]],
    model_records: list[dict[str, Any]],
    dimensions: list[str],
) -> dict[str, Any]:
    human_by_id = {get_sample_id(item, idx): item for idx, item in enumerate(human_records)}
    results: dict[str, Any] = {}

    for dim in dimensions:
        y_true: list[bool] = []
        y_pred: list[bool] = []
        for idx, model in enumerate(model_records):
            sample_id = get_sample_id(model, idx)
            human = human_by_id.get(sample_id)
            if human is None:
                continue
            human_dim = get_human_dimension(human, dim)
            model_dim = get_model_dimension(model, dim)
            if human_dim is None or model_dim is None:
                continue
            y_true.append(human_dim["passed"])
            y_pred.append(model_dim["passed"])
        if y_true:
            results[dim] = calculate_metrics(y_true, y_pred)

    return results


def validate_model_output(record: dict[str, Any], dimensions: list[str]) -> list[str]:
    errors: list[str] = []
    if "is_passed" not in record:
        errors.append("missing is_passed")

    dim_passes: list[bool] = []
    for dim in dimensions:
        if dim not in record:
            errors.append(f"missing dimension: {dim}")
            continue
        try:
            result = normalize_dimension_result(record[dim])
        except ValueError as exc:
            errors.append(f"{dim}: {exc}")
            continue
        dim_passes.append(result["passed"])

    if "is_passed" in record and dim_passes:
        expected = all(dim_passes)
        actual = parse_label(record["is_passed"])
        if actual != expected:
            errors.append(f"is_passed inconsistent with dimensions, expected {expected}")

    return errors


def evaluate_offline(
    human_path: Path,
    model_path: Path,
    dimensions: list[str],
    validate_schema: bool = True,
) -> dict[str, Any]:
    human_records = load_records(human_path)
    model_records = load_records(model_path)
    human_by_id = {get_sample_id(item, idx): item for idx, item in enumerate(human_records)}

    y_true: list[bool] = []
    y_pred: list[bool] = []
    error_cases: list[dict[str, Any]] = []
    schema_errors: list[dict[str, Any]] = []

    for idx, model in enumerate(model_records):
        sample_id = get_sample_id(model, idx)
        if validate_schema:
            output_errors = validate_model_output(model, dimensions)
            if output_errors:
                schema_errors.append({"sample_id": sample_id, "errors": output_errors})

        human = human_by_id.get(sample_id)
        if human is None:
            continue

        true_label = parse_label(human.get("groundtruth"))
        pred_label = parse_label(model.get("is_passed"))
        y_true.append(true_label)
        y_pred.append(pred_label)

        if true_label != pred_label:
            error_cases.append(
                {
                    "sample_id": sample_id,
                    "error_type": "FN" if true_label and not pred_label else "FP",
                    "human": human,
                    "model": model,
                }
            )

    return {
        "overall": calculate_metrics(y_true, y_pred),
        "dimensions": build_dimension_metrics(human_records, model_records, dimensions),
        "error_cases": error_cases,
        "schema_errors": schema_errors,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/task_adapter_config.json")
    parser.add_argument("--task", choices=["human_item", "texture_transfer"])
    parser.add_argument(
        "--mode",
        choices=["original_task_prompt", "universal_only", "universal_adapter"],
    )
    parser.add_argument("--human-json")
    parser.add_argument("--model-json")
    parser.add_argument("--report-json")
    parser.add_argument("--preview-prompts", action="store_true")
    parser.add_argument("--skip-schema-validation", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = PromptAssetConfig.load(Path(args.config))

    if args.preview_prompts:
        for row in build_prompt_preview(config):
            print(
                f"{row['task']} {row['mode']}: "
                f"system={row['system_prompt_chars']} chars, "
                f"user={row['user_prompt_chars']} chars"
            )
        return

    if not args.human_json or not args.model_json or not args.report_json:
        raise SystemExit("--human-json, --model-json, and --report-json are required")

    report = evaluate_offline(
        human_path=Path(args.human_json),
        model_path=Path(args.model_json),
        dimensions=(
            get_dimensions_for_mode(config, args.task, args.mode)
            if args.task and args.mode
            else config.dimensions
        ),
        validate_schema=not args.skip_schema_validation,
    )
    output_path = Path(args.report_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Report saved to: {output_path}")


if __name__ == "__main__":
    main()
