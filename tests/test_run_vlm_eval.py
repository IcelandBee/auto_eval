from pathlib import Path

from scripts.prompt_assets import PromptAssetConfig
from scripts.run_vlm_eval import (
    build_output_schema,
    build_request_kwargs,
    normalize_model_output,
)


ROOT = Path(__file__).resolve().parents[1]


def test_build_output_schema_uses_requested_dimensions():
    schema = build_output_schema(["instruction_following", "perceptual_quality"])

    assert schema["required"] == [
        "is_passed",
        "instruction_following",
        "perceptual_quality",
    ]
    assert "perceptual_quality" in schema["properties"]
    assert "reference_fidelity" not in schema["properties"]


def test_normalize_model_output_fixes_overall_flag_from_dimensions():
    raw = {
        "is_passed": True,
        "instruction_following": {"passed": True, "reason": "ok"},
        "perceptual_quality": {"passed": False, "reason": "bad"},
    }

    normalized, errors = normalize_model_output(
        raw,
        ["instruction_following", "perceptual_quality"],
    )

    assert normalized["is_passed"] is False
    assert "is_passed inconsistent with dimensions, expected False" in errors
    assert normalized["perceptual_quality"]["error_types"] == []


def test_build_request_kwargs_uses_task_mode_prompts_and_three_images():
    config = PromptAssetConfig.load(ROOT / "configs" / "task_adapter_config.json")
    record = {
        "cond_1": "source.jpg",
        "cond_2": "reference.jpg",
        "file_name": "edited.jpg",
        "prompt": "Do the edit.",
    }

    request = build_request_kwargs(
        config=config,
        task_name="human_item",
        mode="universal_adapter",
        record=record,
        sample_idx=3,
        model_name="demo-model",
        image_urls=["data:image/jpeg;base64,src", "data:image/jpeg;base64,ref", "data:image/jpeg;base64,edt"],
        max_tokens=1024,
        temperature=0.1,
        top_p=0.95,
        seed=42,
        top_k=32,
        repetition_penalty=1.05,
        min_pixels=1,
        max_pixels=2,
        max_soft_tokens=3,
        use_response_format=True,
    )

    assert request["model"] == "demo-model"
    assert "Task Adapter: human_item" in request["messages"][0]["content"]
    assert request["messages"][1]["content"][0]["text"].find("Do the edit.") >= 0
    assert [item["image_url"]["url"] for item in request["messages"][1]["content"][1:]] == [
        "data:image/jpeg;base64,src",
        "data:image/jpeg;base64,ref",
        "data:image/jpeg;base64,edt",
    ]
    assert "reference_fidelity" in request["response_format"]["json_schema"]["schema"]["properties"]
