import json
from pathlib import Path

import pytest

from scripts.init_task_prompt import init_task_prompt


def test_init_task_prompt_copies_source_prompts(tmp_path):
    source_system = tmp_path / "source_system.txt"
    source_user = tmp_path / "source_user.txt"
    source_system.write_text("SYSTEM", encoding="utf-8")
    source_user.write_text('prompt = "{PROMPT}"', encoding="utf-8")

    result = init_task_prompt(
        root=tmp_path,
        task="texture_transfer",
        version="v0",
        source_system=source_system,
        source_user=source_user,
        overwrite=False,
    )

    assert result["system_prompt"].read_text(encoding="utf-8") == "SYSTEM\n"
    assert result["user_prompt"].read_text(encoding="utf-8") == 'prompt = "{PROMPT}"\n'


def test_init_task_prompt_refuses_existing_version(tmp_path):
    target = tmp_path / "prompts" / "tasks" / "texture_transfer" / "v0"
    target.mkdir(parents=True)
    source_system = tmp_path / "source_system.txt"
    source_user = tmp_path / "source_user.txt"
    source_system.write_text("SYSTEM", encoding="utf-8")
    source_user.write_text('prompt = "{PROMPT}"', encoding="utf-8")

    with pytest.raises(FileExistsError):
        init_task_prompt(tmp_path, "texture_transfer", "v0", source_system, source_user, False)
