#!/usr/bin/env python3
"""Run real VLM prompt-suite experiments on image-editing QC data."""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

try:
    from evaluate_prompt_suite import evaluate_offline, load_records, normalize_dimension_result
    from prompt_assets import (
        PromptAssetConfig,
        compose_system_prompt,
        get_dimensions_for_mode,
        get_user_prompt_template,
    )
except ModuleNotFoundError:
    from scripts.evaluate_prompt_suite import (
        evaluate_offline,
        load_records,
        normalize_dimension_result,
    )
    from scripts.prompt_assets import (
        PromptAssetConfig,
        compose_system_prompt,
        get_dimensions_for_mode,
        get_user_prompt_template,
    )


_THREAD_LOCAL = threading.local()
VALID_GEMMA_MAX_SOFT_TOKENS = (70, 140, 280, 560, 1120)


def str2bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y", "t"}:
        return True
    if text in {"false", "0", "no", "n", "f"}:
        return False
    raise argparse.ArgumentTypeError("Boolean value expected")


def build_output_schema(dimensions: list[str]) -> dict[str, Any]:
    properties: dict[str, Any] = {"is_passed": {"type": "boolean"}}
    required = ["is_passed"]
    for dim in dimensions:
        required.append(dim)
        properties[dim] = {"$ref": "#/$defs/dimension_result"}

    return {
        "type": "object",
        "additionalProperties": False,
        "required": required,
        "properties": properties,
        "$defs": {
            "dimension_result": {
                "type": "object",
                "additionalProperties": False,
                "required": ["passed", "reason"],
                "properties": {
                    "passed": {"type": "boolean"},
                    "reason": {"type": "string"},
                    "error_types": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            }
        },
    }


def validate_gemma_max_soft_tokens(value: int) -> None:
    if value not in VALID_GEMMA_MAX_SOFT_TOKENS:
        valid = ", ".join(str(item) for item in VALID_GEMMA_MAX_SOFT_TOKENS)
        raise ValueError(
            f"Unsupported max_soft_tokens value: {value}. Valid values are ({valid})"
        )


def image_path_to_data_url(path: Path) -> str:
    mime_type, _ = mimetypes.guess_type(str(path))
    if not mime_type:
        mime_type = "image/jpeg"
    encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


def resolve_image_path(raw_path: str, image_root: Path | None) -> Path:
    path = Path(raw_path)
    if path.is_file():
        return path
    if image_root is not None:
        rooted = image_root / raw_path
        if rooted.is_file():
            return rooted
    raise FileNotFoundError(f"Image file not found: {raw_path}")


def build_user_prompt(prompt: str, user_prompt_template: str) -> str:
    if "{PROMPT}" not in user_prompt_template:
        raise ValueError('User prompt template must contain "{PROMPT}"')
    return user_prompt_template.replace("{PROMPT}", str(prompt))


def build_request_kwargs(
    *,
    config: PromptAssetConfig,
    task_name: str,
    mode: str,
    record: dict[str, Any],
    sample_idx: int,
    model_name: str,
    image_urls: list[str],
    max_tokens: int,
    temperature: float,
    top_p: float,
    seed: int,
    top_k: int,
    repetition_penalty: float,
    min_pixels: int,
    max_pixels: int,
    max_soft_tokens: int,
    use_response_format: bool,
) -> dict[str, Any]:
    if len(image_urls) != 3:
        raise ValueError("image_urls must contain source, reference, and edited image URLs")

    system_prompt = compose_system_prompt(config, task_name, mode)
    user_prompt = build_user_prompt(
        str(record["prompt"]),
        get_user_prompt_template(config, task_name, mode),
    )

    model_lower = model_name.lower()
    mm_kwargs: dict[str, Any] = {}
    if "qwen" in model_lower:
        mm_kwargs["min_pixels"] = min_pixels
        mm_kwargs["max_pixels"] = max_pixels
    elif "gemma" in model_lower:
        validate_gemma_max_soft_tokens(max_soft_tokens)
        mm_kwargs["max_soft_tokens"] = max_soft_tokens

    request_kwargs: dict[str, Any] = {
        "model": model_name,
        "messages": [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": user_prompt,
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": image_urls[0]},
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": image_urls[1]},
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": image_urls[2]},
                    },
                ],
            },
        ],
        "temperature": temperature,
        "top_p": top_p,
        "seed": seed + sample_idx,
        "max_tokens": max_tokens,
        "extra_body": {
            "mm_processor_kwargs": mm_kwargs,
            "top_k": top_k,
            "repetition_penalty": repetition_penalty,
        },
    }

    if use_response_format:
        dimensions = get_dimensions_for_mode(config, task_name, mode)
        request_kwargs["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": "quality_check_result",
                "schema": build_output_schema(dimensions),
            },
        }

    return request_kwargs


def find_first_json_object(text: str) -> str:
    start = text.find("{")
    if start < 0:
        raise ValueError("No JSON object found in response")

    in_string = False
    escape = False
    depth = 0
    for index in range(start, len(text)):
        char = text[index]
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
                return text[start : index + 1]

    raise ValueError("JSON object braces are not balanced")


def extract_text_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        pieces: list[str] = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text" and "text" in item:
                    pieces.append(str(item["text"]))
                elif "content" in item:
                    pieces.append(str(item["content"]))
            else:
                pieces.append(str(item))
        return "\n".join(pieces)
    return str(content)


def parse_json_response(raw_text: str) -> dict[str, Any]:
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    parsed = json.loads(find_first_json_object(text))
    if not isinstance(parsed, dict):
        raise ValueError("Parsed response is not a JSON object")
    return parsed


def normalize_model_output(
    obj: dict[str, Any],
    dimensions: list[str],
) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    normalized: dict[str, Any] = {}

    is_passed = obj.get("is_passed")
    if not isinstance(is_passed, bool):
        errors.append("is_passed must be a boolean")
        is_passed = False
    normalized["is_passed"] = is_passed

    dim_passes: list[bool] = []
    for dim in dimensions:
        if dim not in obj:
            errors.append(f"missing dimension: {dim}")
            normalized[dim] = {"passed": False, "reason": "", "error_types": []}
            dim_passes.append(False)
            continue
        try:
            dim_result = normalize_dimension_result(obj[dim])
        except ValueError as exc:
            errors.append(f"{dim}: {exc}")
            dim_result = {"passed": False, "reason": "", "error_types": []}
        normalized[dim] = dim_result
        dim_passes.append(dim_result["passed"])

    expected_is_passed = all(dim_passes) if dim_passes else False
    if normalized["is_passed"] != expected_is_passed:
        errors.append(f"is_passed inconsistent with dimensions, expected {expected_is_passed}")
        normalized["is_passed"] = expected_is_passed

    return normalized, errors


def pack_output_record(
    index: int,
    record: dict[str, Any],
    normalized: dict[str, Any],
    dimensions: list[str],
    raw_response: str,
    validation_errors: list[str],
) -> dict[str, Any]:
    output = {
        "index": index,
        "cond_1": record.get("cond_1"),
        "cond_2": record.get("cond_2"),
        "file_name": record.get("file_name"),
        "prompt": record.get("prompt"),
        "is_passed": normalized["is_passed"],
        "raw_response": raw_response,
        "validation_errors": validation_errors,
    }
    for dim in dimensions:
        output[dim] = normalized[dim]
    return output


def make_failure_record(
    index: int,
    record: dict[str, Any],
    dimensions: list[str],
    reason: str,
) -> dict[str, Any]:
    output = {
        "index": index,
        "cond_1": record.get("cond_1"),
        "cond_2": record.get("cond_2"),
        "file_name": record.get("file_name"),
        "prompt": record.get("prompt"),
        "is_passed": False,
        "error": reason,
        "raw_response": "",
        "validation_errors": [reason],
    }
    for dim in dimensions:
        output[dim] = {
            "passed": False,
            "reason": reason,
            "error_types": ["artifact_or_low_quality"],
        }
    return output


def get_client(base_url: str, api_key: str, timeout: float):
    client = getattr(_THREAD_LOCAL, "client", None)
    client_key = getattr(_THREAD_LOCAL, "client_key", None)
    current_key = (base_url, api_key, timeout)
    if client is not None and client_key == current_key:
        return client

    try:
        from openai import OpenAI
    except ModuleNotFoundError as exc:
        raise RuntimeError("The openai package is required: pip install openai") from exc

    client = OpenAI(base_url=base_url, api_key=api_key, timeout=timeout)
    _THREAD_LOCAL.client = client
    _THREAD_LOCAL.client_key = current_key
    return client


def infer_one(
    sample_idx: int,
    record: dict[str, Any],
    args: argparse.Namespace,
    config: PromptAssetConfig,
    dimensions: list[str],
) -> dict[str, Any]:
    image_root = Path(args.image_root) if args.image_root else None
    image_paths = [
        resolve_image_path(str(record["cond_1"]), image_root),
        resolve_image_path(str(record["cond_2"]), image_root),
        resolve_image_path(str(record["file_name"]), image_root),
    ]
    image_urls = [image_path_to_data_url(path) for path in image_paths]

    request_kwargs = build_request_kwargs(
        config=config,
        task_name=args.task,
        mode=args.mode,
        record=record,
        sample_idx=sample_idx,
        model_name=args.model_name,
        image_urls=image_urls,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
        top_p=args.top_p,
        seed=args.seed,
        top_k=args.top_k,
        repetition_penalty=args.repetition_penalty,
        min_pixels=args.min_pixels,
        max_pixels=args.max_pixels,
        max_soft_tokens=args.max_soft_tokens,
        use_response_format=not args.disable_response_format,
    )

    last_error = ""
    for attempt in range(args.max_retries + 1):
        try:
            client = get_client(args.base_url, args.api_key, args.timeout)
            response = client.chat.completions.create(**request_kwargs)
            raw_text = extract_text_content(response.choices[0].message.content)
            parsed = parse_json_response(raw_text)
            normalized, validation_errors = normalize_model_output(parsed, dimensions)
            return pack_output_record(
                sample_idx,
                record,
                normalized,
                dimensions,
                raw_text,
                validation_errors,
            )
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt < args.max_retries:
                time.sleep(min(2**attempt, 5))

    return make_failure_record(sample_idx, record, dimensions, last_error or "inference_failed")


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def run_inference(args: argparse.Namespace) -> list[dict[str, Any]]:
    config = PromptAssetConfig.load(Path(args.config))
    dimensions = get_dimensions_for_mode(config, args.task, args.mode)
    records = load_records(Path(args.input_json))
    if args.limit:
        records = records[: args.limit]

    indexed_records = list(enumerate(records))
    outputs: list[dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        futures = {
            executor.submit(infer_one, idx, record, args, config, dimensions): idx
            for idx, record in indexed_records
        }
        for completed_count, future in enumerate(as_completed(futures), 1):
            output = future.result()
            outputs.append(output)
            if args.log_every and completed_count % args.log_every == 0:
                print(f"[{completed_count}/{len(indexed_records)}] finished")

    outputs.sort(key=lambda item: int(item.get("index", 0)))
    write_jsonl(Path(args.output_jsonl), outputs)

    if args.report_json:
        report = evaluate_offline(
            human_path=Path(args.input_json),
            model_path=Path(args.output_jsonl),
            dimensions=dimensions,
            validate_schema=not args.skip_schema_validation,
        )
        report_path = Path(args.report_json)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    return outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/task_adapter_config.json")
    parser.add_argument("--task", required=True, choices=["human_item", "texture_transfer"])
    parser.add_argument(
        "--mode",
        required=True,
        choices=["original_task_prompt", "universal_only", "universal_adapter"],
    )
    parser.add_argument("--input-json", required=True)
    parser.add_argument("--output-jsonl", required=True)
    parser.add_argument("--report-json")
    parser.add_argument("--image-root", default="")

    parser.add_argument("--base-url", required=True)
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--model-name", required=True)

    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument("--max-tokens", type=int, default=1024)
    parser.add_argument("--temperature", type=float, default=0.1)
    parser.add_argument("--top-p", type=float, default=0.95)
    parser.add_argument("--top-k", type=int, default=32)
    parser.add_argument("--repetition-penalty", type=float, default=1.05)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--max-retries", type=int, default=0)

    parser.add_argument("--min-pixels", type=int, default=199808)
    parser.add_argument("--max-pixels", type=int, default=1048576)
    parser.add_argument(
        "--max-soft-tokens",
        type=int,
        choices=VALID_GEMMA_MAX_SOFT_TOKENS,
        default=280,
        help="max_soft_tokens passed to mm_processor_kwargs for Gemma models.",
    )

    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--log-every", type=int, default=10)
    parser.add_argument("--disable-response-format", action="store_true")
    parser.add_argument("--skip-schema-validation", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    outputs = run_inference(args)
    print(f"Output saved to: {args.output_jsonl}")
    if args.report_json:
        print(f"Report saved to: {args.report_json}")
    print(f"Total outputs: {len(outputs)}")


if __name__ == "__main__":
    main()
