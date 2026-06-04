# auto_eval

## Prompt Orchestrator MVP

`scripts/run_prompt_orchestrator.py` runs a config-driven VLM QC prompt tuning loop.

For each iteration it evaluates the current task prompt version, writes `bad_cases.json`,
builds `optimizer_input.json`, calls an OpenAI-compatible optimizer model, writes the next
prompt version, evaluates it, compares reports, and records the accept/reject decision in
`iteration_log.json`.

Before evaluating a prompt version, the orchestrator also synchronizes
`configs/task_adapter_config.json`: it enables `task_prompt` mode when needed, appends the
prompt version to `task_prompt_versions`, and updates `task_prompt_dimensions` when the
prompt's output JSON fields change.

Copy `configs/prompt_orchestrator.example.json`, fill in the image root, API endpoints,
API keys, and model names, then run:

```powershell
& 'C:\Users\Brian\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' `
  scripts\run_prompt_orchestrator.py `
  --config configs\prompt_orchestrator.example.json
```

Artifacts are written under `artifact_root/<version>/`. Candidate prompts are written to
`prompts/tasks/<task>/<version>/`. Rejected candidate versions are kept for review and are
marked as rejected in `iteration_log.json`.
