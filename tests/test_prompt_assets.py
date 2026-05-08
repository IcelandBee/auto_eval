from pathlib import Path

import pytest

from scripts.prompt_assets import (
    PromptAssetConfig,
    compose_system_prompt,
    get_dimensions_for_mode,
    get_user_prompt_template,
    write_prompt_files,
)


ROOT = Path(__file__).resolve().parents[1]


def test_load_config_knows_two_tasks():
    config = PromptAssetConfig.load(ROOT / "configs" / "task_adapter_config.json")

    assert set(config.tasks.keys()) == {"human_item", "texture_transfer"}


def test_universal_adapter_contains_universal_and_adapter_text():
    config = PromptAssetConfig.load(ROOT / "configs" / "task_adapter_config.json")

    prompt = compose_system_prompt(config, "human_item", "universal_adapter")

    assert "You are a strict image-editing quality inspector." in prompt
    assert "Task Adapter: human_item" in prompt


def test_universal_only_excludes_adapter_text():
    config = PromptAssetConfig.load(ROOT / "configs" / "task_adapter_config.json")

    prompt = compose_system_prompt(config, "texture_transfer", "universal_only")

    assert "Task Adapter: texture_transfer" not in prompt


def test_original_mode_uses_existing_task_user_prompt():
    config = PromptAssetConfig.load(ROOT / "configs" / "task_adapter_config.json")

    user_prompt = get_user_prompt_template(config, "texture_transfer", "original_task_prompt")

    assert "clothing texture transfer sample" in user_prompt


def test_universal_modes_use_universal_user_prompt():
    config = PromptAssetConfig.load(ROOT / "configs" / "task_adapter_config.json")

    user_prompt = get_user_prompt_template(config, "human_item", "universal_adapter")

    assert 'prompt = "{PROMPT}"' in user_prompt
    assert "image editing sample" in user_prompt


def test_original_mode_uses_legacy_dimensions():
    config = PromptAssetConfig.load(ROOT / "configs" / "task_adapter_config.json")

    dimensions = get_dimensions_for_mode(config, "texture_transfer", "original_task_prompt")

    assert dimensions == ["instruction_following", "texture_consistency", "clothes_consistency"]


def test_universal_mode_uses_universal_dimensions():
    config = PromptAssetConfig.load(ROOT / "configs" / "task_adapter_config.json")

    dimensions = get_dimensions_for_mode(config, "texture_transfer", "universal_adapter")

    assert "reference_fidelity" in dimensions
    assert "texture_consistency" not in dimensions


def test_unknown_task_fails():
    config = PromptAssetConfig.load(ROOT / "configs" / "task_adapter_config.json")

    with pytest.raises(KeyError):
        compose_system_prompt(config, "unknown_task", "universal_only")


def test_unknown_mode_fails():
    config = PromptAssetConfig.load(ROOT / "configs" / "task_adapter_config.json")

    with pytest.raises(ValueError):
        compose_system_prompt(config, "human_item", "unknown_mode")


def test_write_prompt_files_exports_system_and_user_prompts(tmp_path):
    config = PromptAssetConfig.load(ROOT / "configs" / "task_adapter_config.json")

    result = write_prompt_files(config, "human_item", "universal_adapter", tmp_path)

    assert result["system_prompt"].is_file()
    assert result["user_prompt"].is_file()
    assert "Task Adapter: human_item" in result["system_prompt"].read_text(encoding="utf-8")
    assert "{PROMPT}" in result["user_prompt"].read_text(encoding="utf-8")
