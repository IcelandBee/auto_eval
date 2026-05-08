#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import base64
import json
import mimetypes
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


from openai import OpenAI


# =========================================================
# 1. Prompt Config
# =========================================================

SYSTEM_PROMPT = """You are a strict image-editing quality inspector.

You will receive:
- image 1: source (A), image 2: reference (B), image 3: edited (C), and a text prompt (P).

Task: Provide a pass/fail judgment on three dimensions.
If any dimension fails, then "is_passed" must be false.

1. instruction_following
- Check whether C applies the requested texture transfer from B to the correct clothing region in A.
- Ensure the edited target clothing matches the object, region, or garment specified in P.
- FAIL if the texture is missing, applied to the wrong region, incomplete, or changes the wrong garment.

2. texture_consistency
- Check whether the transferred texture in C is visually consistent with the texture/pattern/material style in B.
- Consider pattern type, color, density, scale, direction, and material appearance.
- FAIL if the texture is clearly different from B, only weakly transferred, severely distorted, or mixed with the original texture.

3. clothes_consistency
- Check whether the clothing structure from A is preserved after texture transfer.
- The task should mainly change texture, not clothing shape.
- FAIL if C changes garment shape, sleeve length, collar, zipper/button state, hem length, pants/skirt length, clothing category, or removes/adds unrelated clothing parts.
- Also FAIL if non-target clothing or unrelated body/background regions are changed significantly.

Resolution / blur / occlusion:
- Judge only clearly visible evidence.
- Do not fail for details that are too small, blurry, cropped, or occluded to verify.

Reasoning rule:
- If the sample fails, report the most important visible failure in one Chinese sentence.

Output format: Return ONLY a valid JSON object.
{
  "is_passed": true/false,
  "instruction_following": {"passed": true/false, "reason": "中文一句话"},
  "texture_consistency": {"passed": true/false, "reason": "中文一句话"},
  "clothes_consistency": {"passed": true/false, "reason": "中文一句话"}
}
"""

USER_PROMPT_TEMPLATE = """Please perform the evaluation for this clothing texture transfer sample.

Inputs:
- image 1 = source image (A)
- image 2 = reference texture image (B)
- image 3 = edited image (C)
- prompt = "{PROMPT}"

Follow the system rules and output the required JSON only.

Extra reminder:
- instruction_following: check whether the requested target clothing region is edited correctly.
- texture_consistency: check whether the transferred texture matches image B.
- clothes_consistency: check whether the original clothing shape, structure, length, collar, zipper/buttons, and non-target clothing are preserved.
- The task should transfer texture only, not redesign the garment.
- If the sample fails, report the main visible problem in Chinese."""

CORE_DIMENSIONS = (
    "instruction_following",
    "texture_consistency",
    "clothes_consistency",
)

OUTPUT_JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "is_passed",
        "instruction_following",
        "texture_consistency",
        "clothes_consistency",
    ],
    "properties": {
        "is_passed": {"type": "boolean"},
        "instruction_following": {
            "type": "object",
            "additionalProperties": False,
            "required": ["passed", "reason"],
            "properties": {
                "passed": {"type": "boolean"},
                "reason": {"type": "string"},
            },
        },
        "texture_consistency": {
            "type": "object",
            "additionalProperties": False,
            "required": ["passed", "reason"],
            "properties": {
                "passed": {"type": "boolean"},
                "reason": {"type": "string"},
            },
        },
        "clothes_consistency": {
            "type": "object",
            "additionalProperties": False,
            "required": ["passed", "reason"],
            "properties": {
                "passed": {"type": "boolean"},
                "reason": {"type": "string"},
            },
        },
    },
}

_thread_local = threading.local()


# =========================================================
# 2. Basic Helpers
# =========================================================

def str2bool(v):
    if isinstance(v, bool):
        return v
    if v is None:
        return True

    v = str(v).strip().lower()

    if v in {"true", "1", "yes", "y", "t"}:
        return True
    if v in {"false", "0", "no", "n", "f"}:
        return False

    raise argparse.ArgumentTypeError("Boolean value expected: True/False")


def now_str() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


def format_seconds(seconds: float) -> str:
    seconds = int(seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def read_text_file(path: str) -> str:
    if not path:
        return ""

    if not os.path.isfile(path):
        raise FileNotFoundError(f"Prompt txt file not found: {path}")

    with open(path, "r", encoding="utf-8-sig") as f:
        return f.read().strip()


def load_prompt_config(system_prompt_file: str, user_prompt_file: str) -> Tuple[str, str]:
    system_prompt = read_text_file(system_prompt_file) if system_prompt_file else SYSTEM_PROMPT
    user_prompt_template = read_text_file(user_prompt_file) if user_prompt_file else USER_PROMPT_TEMPLATE

    system_prompt = system_prompt.strip()
    user_prompt_template = user_prompt_template.strip()

    if not system_prompt:
        raise ValueError("system prompt is empty")

    if not user_prompt_template:
        raise ValueError("user prompt template is empty")

    if "{PROMPT}" not in user_prompt_template:
        raise ValueError('user prompt template must contain "{PROMPT}" placeholder')

    return system_prompt, user_prompt_template


def get_client(base_url: str, api_key: str, timeout: float) -> OpenAI:
    client = getattr(_thread_local, "client", None)
    client_key = getattr(_thread_local, "client_key", None)
    current_key = (base_url, api_key, timeout)

    if client is None or client_key != current_key:
        client = OpenAI(base_url=base_url, api_key=api_key, timeout=timeout)
        _thread_local.client = client
        _thread_local.client_key = current_key

    return client


def load_data(filepath: str) -> List[Dict[str, Any]]:
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    with open(filepath, "r", encoding="utf-8-sig") as f:
        text = f.read().strip()

    if not text:
        return []

    if filepath.lower().endswith(".jsonl"):
        data = []
        for line_no, line in enumerate(text.splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            try:
                data.append(json.loads(line))
            except Exception as e:
                raise ValueError(f"Invalid JSON on line {line_no} of {filepath}: {e}") from e
        return data

    try:
        obj = json.loads(text)
        if isinstance(obj, list):
            return obj
        if isinstance(obj, dict):
            return [obj]
    except json.JSONDecodeError:
        data = []
        for line_no, line in enumerate(text.splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            try:
                data.append(json.loads(line))
            except Exception as e:
                raise ValueError(f"Invalid JSON on line {line_no} of {filepath}: {e}") from e
        return data

    raise ValueError(f"Unsupported JSON structure in {filepath}")


def image_path_to_data_url(path: str) -> str:
    mime_type, _ = mimetypes.guess_type(path)
    if not mime_type:
        mime_type = "image/jpeg"

    with open(path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")

    return f"data:{mime_type};base64,{encoded}"


def build_user_prompt(prompt: str, user_prompt_template: str) -> str:
    return user_prompt_template.replace("{PROMPT}", str(prompt))


# =========================================================
# 3. Parse / Validate Model Output
# =========================================================

def find_first_json_object(text: str) -> str:
    start = text.find("{")
    if start < 0:
        raise ValueError("No JSON object found in response")

    in_string = False
    escape = False
    depth = 0

    for i in range(start, len(text)):
        ch = text[i]

        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start: i + 1]

    raise ValueError("JSON object braces are not balanced")


def extract_text_content(content: Any) -> str:
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        pieces = []
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


def parse_json_response(raw_text: str) -> Dict[str, Any]:
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

    candidate = find_first_json_object(text)
    parsed = json.loads(candidate)

    if not isinstance(parsed, dict):
        raise ValueError("Parsed response is not a JSON object")

    return parsed


def normalize_and_validate_output(obj: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    errors: List[str] = []

    is_passed = obj.get("is_passed")
    if not isinstance(is_passed, bool):
        errors.append("is_passed must be a boolean")
        is_passed = False

    normalized: Dict[str, Any] = {
        "is_passed": is_passed,
    }

    dim_pass_map: Dict[str, bool] = {}

    for dim_name in CORE_DIMENSIONS:
        item = obj.get(dim_name)

        if not isinstance(item, dict):
            errors.append(f"{dim_name} must be an object")
            normalized[dim_name] = {
                "passed": False,
                "reason": "",
            }
            dim_pass_map[dim_name] = False
            continue

        passed = item.get("passed")
        reason = item.get("reason")

        if not isinstance(passed, bool):
            errors.append(f"{dim_name}.passed must be a boolean")
            passed = False

        if not isinstance(reason, str):
            errors.append(f"{dim_name}.reason must be a string")
            reason = "" if reason is None else str(reason)

        normalized[dim_name] = {
            "passed": passed,
            "reason": reason.strip(),
        }
        dim_pass_map[dim_name] = passed

    expected_is_passed = all(dim_pass_map.get(dim, False) for dim in CORE_DIMENSIONS)

    if is_passed != expected_is_passed:
        errors.append(
            f"is_passed is inconsistent with dimension results, expected {expected_is_passed}"
        )
        normalized["is_passed"] = expected_is_passed

    allowed_keys = {"is_passed", *CORE_DIMENSIONS}
    extra_keys = [k for k in obj.keys() if k not in allowed_keys]
    if extra_keys:
        errors.append(f"unexpected extra keys: {extra_keys}")

    return normalized, errors


# =========================================================
# 4. Output Record Builders
# =========================================================

def make_failure_record(
    index: int,
    cond_1: str,
    cond_2: str,
    file_name: str,
    prompt: str,
    reason: str,
) -> Dict[str, Any]:
    reason = (reason or "接口调用失败").strip()

    output = {
        "index": index,
        "cond_1": cond_1,
        "cond_2": cond_2,
        "file_name": file_name,
        "prompt": prompt,
        "is_passed": False,
    }

    for dim in CORE_DIMENSIONS:
        output[dim] = {
            "passed": False,
            "reason": reason,
        }

    return output


def pack_output_record(
    index: int,
    cond_1: str,
    cond_2: str,
    file_name: str,
    prompt: str,
    result: Dict[str, Any],
) -> Dict[str, Any]:
    output = {
        "index": index,
        "cond_1": cond_1,
        "cond_2": cond_2,
        "file_name": file_name,
        "prompt": prompt,
        "is_passed": result["is_passed"],
    }

    for dim in CORE_DIMENSIONS:
        output[dim] = result[dim]

    return output


def load_existing_output_records(output_jsonl: str) -> Dict[int, Dict[str, Any]]:
    records: Dict[int, Dict[str, Any]] = {}

    if not os.path.isfile(output_jsonl):
        return records

    with open(output_jsonl, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                obj = json.loads(line)
            except Exception:
                continue

            idx = obj.get("index")
            if isinstance(idx, int):
                records[idx] = obj

    return records


def compute_next_write_idx(existing_output_records: Dict[int, Dict[str, Any]], total_count: int) -> int:
    idx = 0
    while idx < total_count and idx in existing_output_records:
        idx += 1
    return idx


def collect_ready_records(
    next_write_idx: int,
    total_count: int,
    result_buffer: Dict[int, Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], int]:
    ready_records: List[Dict[str, Any]] = []

    while next_write_idx < total_count and next_write_idx in result_buffer:
        ready_records.append(result_buffer.pop(next_write_idx))
        next_write_idx += 1

    return ready_records, next_write_idx


def write_records_batch(
    output_path: Path,
    records_batch: List[Dict[str, Any]],
    file_initialized: bool,
) -> bool:
    if not records_batch:
        return file_initialized

    mode = "a" if file_initialized else "w"

    with open(output_path, mode, encoding="utf-8") as fout:
        for record in records_batch:
            fout.write(json.dumps(record, ensure_ascii=False) + "\n")
        fout.flush()
        os.fsync(fout.fileno())

    return True


def rewrite_ordered_jsonl(output_path: Path, records_by_index: Dict[int, Dict[str, Any]], total_count: int) -> None:
    """
    overwrite=False 续跑时，如果已有结果文件里顺序混乱或缺失中间项，
    可以在最终评估前重写为 index 顺序，保证后续人工检查更清晰。
    """
    with open(output_path, "w", encoding="utf-8") as f:
        for idx in range(total_count):
            if idx in records_by_index:
                f.write(json.dumps(records_by_index[idx], ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


# =========================================================
# 5. Inference
# =========================================================

def infer_one(sample_idx: int, record: Dict[str, Any], args) -> Dict[str, Any]:
    cond_1 = record["cond_1"]
    cond_2 = record["cond_2"]
    file_name = record["file_name"]
    prompt = record["prompt"]

    src_url = image_path_to_data_url(cond_1)
    ref_url = image_path_to_data_url(cond_2)
    edt_url = image_path_to_data_url(file_name)

    user_prompt = build_user_prompt(prompt, args.user_prompt_template)

    mm_kwargs = {}
    model_lower = args.model_name.lower()

    if "qwen" in model_lower:
        mm_kwargs["min_pixels"] = args.min_pixels
        mm_kwargs["max_pixels"] = args.max_pixels
    elif "gemma" in model_lower:
        mm_kwargs["max_soft_tokens"] = args.max_soft_tokens

    last_error: Optional[str] = None

    for attempt in range(args.max_retries + 1):
        try:
            client = get_client(args.base_url, args.api_key, args.timeout)

            request_kwargs = dict(
                model=args.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": args.system_prompt,
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
                                "image_url": {
                                    "url": src_url,
                                },
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": ref_url,
                                },
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": edt_url,
                                },
                            },
                        ],
                    },
                ],
                temperature=args.temperature,
                top_p=args.top_p,
                seed=args.seed + sample_idx,
                max_tokens=args.max_tokens,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "quality_check_result",
                        "schema": OUTPUT_JSON_SCHEMA,
                    },
                },
                extra_body={
                    "mm_processor_kwargs": mm_kwargs,
                    "top_k": args.top_k,
                    "repetition_penalty": args.repetition_penalty,
                },
            )

            resp = client.chat.completions.create(**request_kwargs)
            raw_text = extract_text_content(resp.choices[0].message.content)

            parsed = parse_json_response(raw_text)
            normalized, validation_errors = normalize_and_validate_output(parsed)

            success = len(validation_errors) == 0
            error = None if success else "validation_failed"

            return {
                "success": success,
                "error": error,
                "output_record": pack_output_record(
                    sample_idx,
                    cond_1,
                    cond_2,
                    file_name,
                    prompt,
                    normalized,
                ),
            }

        except Exception as e:
            last_error = f"{type(e).__name__}: {e}"

            if attempt < args.max_retries:
                time.sleep(min(2 ** attempt, 5))
                continue

    return {
        "success": False,
        "error": last_error,
        "output_record": make_failure_record(
            sample_idx,
            cond_1,
            cond_2,
            file_name,
            prompt,
            "接口调用失败",
        ),
    }


def run_one(item: Tuple[int, Dict[str, Any]], args):
    idx, record = item

    try:
        out = infer_one(idx, record, args)
    except Exception as e:
        out = {
            "success": False,
            "error": f"{type(e).__name__}: {str(e)}",
            "output_record": make_failure_record(
                idx,
                record.get("cond_1", ""),
                record.get("cond_2", ""),
                record.get("file_name", ""),
                record.get("prompt", ""),
                "接口调用失败",
            ),
        }

    return idx, out


def run_inference(args, records: List[Dict[str, Any]]) -> Dict[str, int]:
    output_path = Path(args.output_jsonl)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if args.overwrite:
        existing_output_records: Dict[int, Dict[str, Any]] = {}
        file_initialized = False
    else:
        existing_output_records = load_existing_output_records(args.output_jsonl)
        existing_output_records = {
            idx: rec
            for idx, rec in existing_output_records.items()
            if 0 <= idx < len(records)
        }
        file_initialized = output_path.exists() and output_path.stat().st_size > 0

    processed_indices = set(existing_output_records.keys())

    pending: List[Tuple[int, Dict[str, Any]]] = []
    for idx, record in enumerate(records):
        if idx in processed_indices:
            continue
        pending.append((idx, record))

    print(f"[{now_str()}] Status: inference starting")
    print(f"Total samples      : {len(records)}")
    print(f"Already processed  : {len(processed_indices)}")
    print(f"Pending samples    : {len(pending)}")
    print(f"Max workers        : {args.max_workers}")
    print(f"Log every          : {args.log_every}")
    print(f"Overwrite          : {args.overwrite}")
    print(f"Model output       : {args.output_jsonl}")

    if not pending and not args.overwrite:
        print("Nothing to infer. Existing model output will be used for evaluation.")
        return {
            "success_count": 0,
            "fail_count": 0,
            "validation_fail_count": 0,
        }

    success_count = 0
    fail_count = 0
    validation_fail_count = 0

    result_buffer: Dict[int, Dict[str, Any]] = {}
    next_write_idx = compute_next_write_idx(existing_output_records, len(records))

    start_time = time.time()

    if pending:
        with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
            futures = {
                executor.submit(run_one, item, args): item[0]
                for item in pending
            }

            for n, future in enumerate(as_completed(futures), 1):
                idx = futures[future]

                try:
                    returned_idx, out = future.result()
                    result_buffer[returned_idx] = out["output_record"]

                    if out["success"]:
                        success_count += 1
                    else:
                        fail_count += 1
                        if out.get("error") == "validation_failed":
                            validation_fail_count += 1
                        print(f"[-] Error on sample {returned_idx}: {out.get('error')}")

                except Exception as e:
                    print(f"[-] Future exception on sample {idx}: {e}")
                    result_buffer[idx] = make_failure_record(
                        idx,
                        records[idx].get("cond_1", ""),
                        records[idx].get("cond_2", ""),
                        records[idx].get("file_name", ""),
                        records[idx].get("prompt", ""),
                        "接口调用失败",
                    )
                    fail_count += 1

                ready_records, next_write_idx = collect_ready_records(
                    next_write_idx=next_write_idx,
                    total_count=len(records),
                    result_buffer=result_buffer,
                )

                file_initialized = write_records_batch(
                    output_path=output_path,
                    records_batch=ready_records,
                    file_initialized=file_initialized,
                )

                if n % args.log_every == 0 or n == len(pending):
                    elapsed = format_seconds(time.time() - start_time)
                    print(
                        f"[{now_str()}] Status: running | "
                        f"progress={n}/{len(pending)} | "
                        f"success={success_count} | "
                        f"fail={fail_count} | "
                        f"validation_fail={validation_fail_count} | "
                        f"written_until={next_write_idx - 1} | "
                        f"elapsed={elapsed}"
                    )

    if result_buffer:
        print(
            f"Warning: {len(result_buffer)} records were not flushed because earlier indices are missing."
        )

    total_elapsed = format_seconds(time.time() - start_time)

    print(f"[{now_str()}] Status: inference finished")
    print(f"Success            : {success_count}")
    print(f"Fail               : {fail_count}")
    print(f"Validation fail    : {validation_fail_count}")
    print(f"Total elapsed      : {total_elapsed}")
    print(f"Saved to           : {args.output_jsonl}")

    return {
        "success_count": success_count,
        "fail_count": fail_count,
        "validation_fail_count": validation_fail_count,
    }


# =========================================================
# 6. Evaluation Metrics
# =========================================================

def get_sample_id(item: Dict[str, Any], fallback_index: int) -> str:
    for key in ["file_name", "id", "image_id", "filename", "name"]:
        if key in item and item.get(key) is not None:
            return os.path.basename(str(item.get(key)))

    return f"index_{fallback_index}"


def parse_label(value: Any) -> bool:
    if isinstance(value, bool):
        return value

    value = str(value).strip().lower()

    if value in {"pass", "true", "1", "yes", "y"}:
        return True

    if value in {"fail", "false", "0", "no", "n"}:
        return False

    return False


def get_model_dim_pass(item: Dict[str, Any], dim: str) -> bool:
    dim_obj = item.get(dim, {})

    if isinstance(dim_obj, dict):
        return parse_label(dim_obj.get("passed"))

    return parse_label(dim_obj)


def get_model_dim_reason(item: Dict[str, Any], dim: str) -> str:
    dim_obj = item.get(dim, {})

    if isinstance(dim_obj, dict):
        return str(dim_obj.get("reason", "")).strip()

    return ""


def get_human_dim_pass(item: Dict[str, Any], dim: str) -> bool:
    return parse_label(item.get(dim))


def get_human_dim_reason(item: Dict[str, Any], dim: str) -> str:
    return str(item.get(f"{dim}_reasoning", "")).strip()


def calculate_metrics(y_true: List[bool], y_pred: List[bool]) -> Dict[str, Any]:
    tp = sum(1 for t, p in zip(y_true, y_pred) if t is True and p is True)
    tn = sum(1 for t, p in zip(y_true, y_pred) if t is False and p is False)
    fp = sum(1 for t, p in zip(y_true, y_pred) if t is False and p is True)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t is True and p is False)

    total = len(y_true)

    accuracy = (tp + tn) / total if total > 0 else 0.0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "Total": total,
        "Human Pass Count": sum(y_true),
        "Model Pass Count": sum(y_pred),
        "TP": tp,
        "TN": tn,
        "FP": fp,
        "FN": fn,
        "Accuracy": accuracy,
        "Precision": precision,
        "Recall": recall,
        "F1": f1,
    }


def format_metrics(name: str, metrics: Dict[str, Any]) -> str:
    lines = []

    lines.append(f"=== {name} ===")
    lines.append(f"Total             : {metrics['Total']}")
    lines.append(f"Human Pass Count  : {metrics['Human Pass Count']}")
    lines.append(f"Model Pass Count  : {metrics['Model Pass Count']}")
    lines.append("-" * 30)
    lines.append("Confusion Matrix:")
    lines.append(f"TP: {metrics['TP']}")
    lines.append(f"TN: {metrics['TN']}")
    lines.append(f"FP: {metrics['FP']}  # 人工 Fail，但模型 Pass")
    lines.append(f"FN: {metrics['FN']}  # 人工 Pass，但模型 Fail")
    lines.append("-" * 30)
    lines.append(f"Accuracy : {metrics['Accuracy']:.4f}")
    lines.append(f"Precision: {metrics['Precision']:.4f}")
    lines.append(f"Recall   : {metrics['Recall']:.4f}")
    lines.append(f"F1       : {metrics['F1']:.4f}")
    lines.append("")

    return "\n".join(lines)


def build_human_map(human_data: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    result = {}

    for i, item in enumerate(human_data):
        sample_id = get_sample_id(item, i)
        result[sample_id] = item

    return result


def build_dimension_details(
    human_item: Dict[str, Any],
    model_item: Dict[str, Any],
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    human_dimensions = {}
    model_dimensions = {}

    for dim in CORE_DIMENSIONS:
        human_dimensions[dim] = {
            "passed": get_human_dim_pass(human_item, dim),
            "reason": get_human_dim_reason(human_item, dim),
        }

        model_dimensions[dim] = {
            "passed": get_model_dim_pass(model_item, dim),
            "reason": get_model_dim_reason(model_item, dim),
        }

    return human_dimensions, model_dimensions


def build_dimension_metric_containers() -> Tuple[Dict[str, List[bool]], Dict[str, List[bool]]]:
    dim_true = {dim: [] for dim in CORE_DIMENSIONS}
    dim_pred = {dim: [] for dim in CORE_DIMENSIONS}

    return dim_true, dim_pred


def append_dimension_labels(
    dim_true: Dict[str, List[bool]],
    dim_pred: Dict[str, List[bool]],
    human_dimensions: Dict[str, Dict[str, Any]],
    model_dimensions: Dict[str, Dict[str, Any]],
) -> None:
    for dim in CORE_DIMENSIONS:
        dim_true[dim].append(human_dimensions[dim]["passed"])
        dim_pred[dim].append(model_dimensions[dim]["passed"])


def build_metric_output(
    human_data_count: int,
    model_data_count: int,
    matched_count: int,
    missing_count: int,
    overall_true: List[bool],
    overall_pred: List[bool],
    dim_true: Dict[str, List[bool]],
    dim_pred: Dict[str, List[bool]],
) -> str:
    output_lines = []

    output_lines.append("Loading data finished.")
    output_lines.append(f"Human records : {human_data_count}")
    output_lines.append(f"Model records : {model_data_count}")
    output_lines.append(f"Matched       : {matched_count}")
    output_lines.append(f"Missing       : {missing_count}")
    output_lines.append("")
    output_lines.append("Core Dimensions:")

    for dim in CORE_DIMENSIONS:
        output_lines.append(f"- {dim}")

    output_lines.append("")

    overall_metrics = calculate_metrics(overall_true, overall_pred)
    output_lines.append(format_metrics("Overall Metrics", overall_metrics))

    for dim in CORE_DIMENSIONS:
        metrics = calculate_metrics(dim_true[dim], dim_pred[dim])
        output_lines.append(format_metrics(f"Dimension Metrics - {dim}", metrics))

    return "\n".join(output_lines)


def build_error_case(
    model_item: Dict[str, Any],
    human_item: Dict[str, Any],
    sample_id: str,
    fallback_index: int,
    h_overall: bool,
    m_overall: bool,
    human_dimensions: Dict[str, Dict[str, Any]],
    model_dimensions: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    error_type = (
        "FP_人工Fail_模型Pass"
        if h_overall is False and m_overall is True
        else "FN_人工Pass_模型Fail"
    )

    return {
        "index": model_item.get("index", fallback_index),
        "id": sample_id,
        "error_type": error_type,

        "file_name": human_item.get("file_name", model_item.get("file_name", "")),
        "cond_1": human_item.get("cond_1", model_item.get("cond_1", "")),
        "cond_2": human_item.get("cond_2", model_item.get("cond_2", "")),
        "prompt": human_item.get("prompt", model_item.get("prompt", "")),

        "human_overall": h_overall,
        "model_overall": m_overall,

        "human_groundtruth": human_item.get("groundtruth", ""),
        "human_groundtruth_reasoning": human_item.get("groundtruth_reasoning", ""),

        "model_is_passed": model_item.get("is_passed", ""),

        "core_dimensions": list(CORE_DIMENSIONS),
        "human_dimensions": human_dimensions,
        "model_dimensions": model_dimensions,
    }


def evaluate_results(
    human_path: str,
    model_path: str,
    metric_output: str,
    error_output: str,
) -> None:
    human_data = load_data(human_path)
    model_data = load_data(model_path)

    human_map = build_human_map(human_data)

    overall_true = []
    overall_pred = []

    dim_true, dim_pred = build_dimension_metric_containers()

    error_cases = []
    matched_count = 0
    missing_count = 0

    for i, model_item in enumerate(model_data):
        sample_id = get_sample_id(model_item, i)
        human_item = human_map.get(sample_id)

        if human_item is None:
            missing_count += 1
            continue

        matched_count += 1

        h_overall = parse_label(human_item.get("groundtruth"))
        m_overall = parse_label(model_item.get("is_passed"))

        overall_true.append(h_overall)
        overall_pred.append(m_overall)

        human_dimensions, model_dimensions = build_dimension_details(
            human_item=human_item,
            model_item=model_item,
        )

        append_dimension_labels(
            dim_true=dim_true,
            dim_pred=dim_pred,
            human_dimensions=human_dimensions,
            model_dimensions=model_dimensions,
        )

        if h_overall != m_overall:
            error_cases.append(
                build_error_case(
                    model_item=model_item,
                    human_item=human_item,
                    sample_id=sample_id,
                    fallback_index=i,
                    h_overall=h_overall,
                    m_overall=m_overall,
                    human_dimensions=human_dimensions,
                    model_dimensions=model_dimensions,
                )
            )

    output_text = build_metric_output(
        human_data_count=len(human_data),
        model_data_count=len(model_data),
        matched_count=matched_count,
        missing_count=missing_count,
        overall_true=overall_true,
        overall_pred=overall_pred,
        dim_true=dim_true,
        dim_pred=dim_pred,
    )

    os.makedirs(os.path.dirname(os.path.abspath(metric_output)), exist_ok=True)
    with open(metric_output, "w", encoding="utf-8") as f:
        f.write(output_text)

    os.makedirs(os.path.dirname(os.path.abspath(error_output)), exist_ok=True)
    with open(error_output, "w", encoding="utf-8") as f:
        json.dump(error_cases, f, ensure_ascii=False, indent=2)

    print("")
    print(f"[{now_str()}] Status: evaluation finished")
    print(output_text)
    print(f"Metric result saved to: {metric_output}")
    print(f"Error cases saved to  : {error_output}")


# =========================================================
# 7. Args / Main
# =========================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description="Run VLM quality inspection and immediately evaluate against human labels."
    )

    # -------------------------
    # VLM Server
    # -------------------------
    parser.add_argument(
        "--base-url",
        default="http://10.154.39.53:8001/v1",
        help="vLLM OpenAI-compatible endpoint",
    )
    parser.add_argument(
        "--api-key",
        default="123456",
        help="API key for the OpenAI-compatible server",
    )
    parser.add_argument(
        "--model-name",
        default="Qwen3.6-27B",
        help="Model name exposed by vLLM, e.g. gemma-4-31B-it, Qwen3.6-27B",
    )

    # -------------------------
    # Input / Human Label
    # -------------------------
    parser.add_argument(
        "--input-json",
        default="/mnt/DATA_71/public/data/testing_sets/real_data_bench/texture_person_v2/texture_person_v2.json",
        help="Input sample json/jsonl path. It should contain cond_1, cond_2, file_name, prompt. Usually this is also the human label file.",
    )
    parser.add_argument(
        "--human-json",
        default="",
        help="Human label json/jsonl path. If empty, use --input-json.",
    )

    # -------------------------
    # Prompt Files
    # -------------------------
    parser.add_argument(
        "--system-prompt-file",
        default="",
        help="External system prompt txt file path. If empty, use built-in SYSTEM_PROMPT.",
    )
    parser.add_argument(
        "--user-prompt-file",
        default="",
        help='External user prompt template txt file path. If empty, use built-in USER_PROMPT_TEMPLATE. Must contain "{PROMPT}".',
    )

    # -------------------------
    # Output Files
    # -------------------------
    parser.add_argument(
        "--output-jsonl",
        default="/mnt/DATA/h30082292/results/vlm_consistency/texture_person_v2/model_output.jsonl",
        help="Model output jsonl path.",
    )
    parser.add_argument(
        "--metric-output",
        default="/mnt/DATA/h30082292/results/vlm_consistency/texture_person_v2/metric.txt",
        help="Metric txt output path.",
    )
    parser.add_argument(
        "--error-output",
        default="/mnt/DATA/h30082292/results/vlm_consistency/texture_person_v2/error_cases.json",
        help="Error cases json output path.",
    )

    # -------------------------
    # Inference Params
    # -------------------------
    parser.add_argument(
        "--max-workers",
        type=int,
        default=16,
        help="Concurrent request workers.",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=1024,
        help="Max output tokens.",
    )
    parser.add_argument(
        "--min-pixels",
        type=int,
        default=446 * 448,
        help="min_pixels passed to mm_processor_kwargs for Qwen3.x.",
    )
    parser.add_argument(
        "--max-pixels",
        type=int,
        default=1024 * 1024,
        help="max_pixels passed to mm_processor_kwargs for Qwen3.x.",
    )
    parser.add_argument(
        "--max-soft-tokens",
        type=int,
        default=280,
        help="max_soft_tokens passed to mm_processor_kwargs for gemma-4. Choices: 70, 140, 280, 560, 1120.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.1,
        help="Sampling temperature.",
    )
    parser.add_argument(
        "--top-p",
        type=float,
        default=0.95,
        help="Top-p sampling.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=32,
        help="Top-k sampling.",
    )
    parser.add_argument(
        "--repetition-penalty",
        type=float,
        default=1.05,
        help="Repetition penalty.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Base request seed; actual seed is seed + sample_index.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=300.0,
        help="Client timeout in seconds.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=0,
        help="Retry times for one sample on request/parse failure.",
    )
    parser.add_argument(
        "--log-every",
        type=int,
        default=1,
        help="Print running status every N processed cases.",
    )
    parser.add_argument(
        "--overwrite",
        type=str2bool,
        default=True,
        help="Whether to overwrite existing model output file, True/False.",
    )

    return parser.parse_args()


def main():
    args = parse_args()

    args.human_json = args.human_json or args.input_json

    args.system_prompt, args.user_prompt_template = load_prompt_config(
        args.system_prompt_file,
        args.user_prompt_file,
    )

    print(f"[{now_str()}] Prompt config loaded")

    if args.system_prompt_file:
        print(f"System prompt file : {args.system_prompt_file}")
    else:
        print("System prompt file : built-in SYSTEM_PROMPT")

    if args.user_prompt_file:
        print(f"User prompt file   : {args.user_prompt_file}")
    else:
        print("User prompt file   : built-in USER_PROMPT_TEMPLATE")

    records = load_data(args.input_json)

    for idx, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"sample {idx} is not a dict")

        for required_key in ["cond_1", "cond_2", "file_name", "prompt"]:
            if required_key not in record:
                raise KeyError(f"sample {idx} missing required key: {required_key}")

    print("")
    print(f"[{now_str()}] Unified quality check started")
    print(f"Input json         : {args.input_json}")
    print(f"Human json         : {args.human_json}")
    print(f"Model output jsonl : {args.output_jsonl}")
    print(f"Metric output      : {args.metric_output}")
    print(f"Error output       : {args.error_output}")
    print("")

    run_inference(args=args, records=records)

    evaluate_results(
        human_path=args.human_json,
        model_path=args.output_jsonl,
        metric_output=args.metric_output,
        error_output=args.error_output,
    )

    print("")
    print(f"[{now_str()}] All done.")
    print("Generated files:")
    print(f"- model output : {args.output_jsonl}")
    print(f"- metric       : {args.metric_output}")
    print(f"- error cases  : {args.error_output}")


if __name__ == "__main__":
    main()