# VLM QC 两个 Skills 使用指南

本文说明如何使用本仓库中的两个 Codex skills：

- `vlm-qc-prompt-initialization`
- `vlm-qc-auto-tuning`

这两个 skills 服务于同一个目标：为图像编辑质检任务构建并迭代 VLM-as-a-judge prompt。前者负责从人工标注和规则中生成任务专用的初始 prompt，后者负责基于评估结果、FP/FN 坏例和优化规则持续迭代 prompt。

## 一句话理解

`vlm-qc-prompt-initialization` 用于从零生成 `v0`。

`vlm-qc-auto-tuning` 用于从已有的 `v0` 或后续版本生成 `v1`、`v2`、`v3` 等迭代版本。

通常可以这样分工：初始化 skill 只负责把第一个版本搭起来；后续版本的评估和修改交给自动调优 skill。

## 基本原则：用户数据不设默认值

这两个 skills 有一个很重要的使用约定：和用户真实任务有关的数据，都不应该由仓库里的样例或旧项目习惯来代替。

也就是说，下面这些信息需要用户明确提供；如果调用 skill 时发现缺少，agent 应该先问清楚，再继续执行：

- 任务名称；
- 人工标注 JSON 或 JSONL 文件路径；
- 图片根目录；
- 初始 prompt 的来源文件或模板；
- prompt 设计规则或优化规则；
- 目标版本号；
- 输出目录；
- Python 运行时；
- VLM API base URL；
- VLM API key 或环境变量；
- VLM model name；
- optimizer LLM 的 API base URL；
- optimizer LLM 的 API key 或环境变量；
- optimizer LLM model name；
- 解码参数；
- 停止条件和验收阈值。

仓库里的示例路径、历史样例、旧项目习惯、命令模板、`code/` 或 `data/` 目录，都不应该被当成真实输入。当前分支已经移除了 `code/` 和 `data/` 下的样例文件，目的就是避免把测试样例误用成默认数据。

## 推荐工作流

完整流程如下：

```text
用户提供任务数据和规则
  -> vlm-qc-prompt-initialization 生成 v0
  -> 用户确认 v0 的任务定义和维度
  -> vlm-qc-auto-tuning 评估 v0
  -> 抽取 FP/FN 坏例
  -> 构建 optimizer_input.json
  -> 生成 v1
  -> 复评 v1
  -> 比较 v0/v1
  -> 按用户提供的停止条件继续或停止
```

如果你只想自动跑固定轮数，可以使用仓库里的 MVP orchestrator：

```text
scripts/run_prompt_orchestrator.py
```

它把 auto-tuning 的评估、坏例抽取、优化输入、下一版 prompt 写入、复评和比较串成配置驱动的循环。

## Skill 1：vlm-qc-prompt-initialization

### 适用场景

当一个任务还没有任务专用的初始质检 prompt 时使用。

典型场景：

- 新增一个图像编辑任务；
- 只有人工标注样本，还没有 task-specific QC prompt；
- 需要从 prompt 字段和人工失败原因中归纳任务定义；
- 需要确定质检维度和红线；
- 需要生成 `prompts/tasks/<task>/<version>/system_prompt.txt` 和 `user_prompt.txt`。

### 必需输入

调用前需要准备：

- `task`：任务名，例如 `texture_transfer`；
- `human_labels`：人工标注 JSON 或 JSONL；
- `source_system_prompt` 或 system prompt 模板；
- `source_user_prompt` 或 user prompt 模板，必须包含 `{PROMPT}`；
- prompt 设计规则文件或明确规则文本；
- 目标版本号，通常是 `v0`；
- 输出目录，通常是 `prompts/tasks/<task>/<version>/`；
- 运行模式：交互模式或明确授权的 batch/non-interactive 模式。

如果缺任何一项，agent 应该先问用户。这里最好不要猜，因为一旦数据、模型或路径错了，后面的评估结果就没有可比性。

### 初始化流程

1. 收集并确认所有输入。
2. 读取人工标注文件。
3. 统计 pass/fail、已有维度、维度级 pass/fail、人类原因和 prompt pattern。
4. 从标注中的 prompt 字段推断任务定义。
5. 提炼候选质检维度、失败红线、容忍规则。
6. 在交互模式下，先把任务定义和维度方案给用户确认。
7. 用户确认后，生成完整 `system_prompt.txt` 和 `user_prompt.txt`。
8. 保存 `annotation_summary.json`，建议同时保存 `prompt_init_proposal.json`。
9. 交给 `vlm-qc-auto-tuning` 继续评估和迭代。

### 交互模式和 batch 模式

交互模式下，建议先让用户确认任务定义和维度方案。agent 应该先展示：

- 推断出的任务目标；
- Image A/B/C/P 的含义；
- 建议的维度；
- 保留、合并、重命名、新增或删除的维度；
- 主要失败红线；
- 容忍规则；
- 不确定点。

batch 模式适合已经确认过任务定义和维度方案的情况。例如用户明确说“按这份已确认方案非交互生成 v0”，agent 就可以直接写文件。否则还是建议先走一次确认。

### 输出要求

初始化完成后，至少应产生：

```text
prompts/tasks/<task>/<version>/system_prompt.txt
prompts/tasks/<task>/<version>/user_prompt.txt
prompts/tasks/<task>/<version>/annotation_summary.json
```

建议额外产生：

```text
prompts/tasks/<task>/<version>/prompt_init_proposal.json
```

`system_prompt.txt` 必须明确输出 JSON 字段。字段应和下游 `configs/task_adapter_config.json` 中的 `task_prompt_dimensions` 保持一致。

## Skill 2：vlm-qc-auto-tuning

### 适用场景

当已有稳定的任务专用 prompt 版本时使用。

典型场景：

- 已有 `prompts/tasks/<task>/v0/`；
- 需要评估当前 prompt；
- 需要从 FP/FN 中找可泛化问题；
- 需要生成 `v1`、`v2`、`v3`；
- 需要比较版本指标；
- 需要按用户给定停止条件自动迭代若干轮。

### 必需输入

每次 auto-tuning run 都必须确认：

- Python 运行时，例如 `<python_executable>` 或 `conda run -n <env> python`；
- 任务名；
- 当前 prompt 版本；
- 下一版 prompt 版本；
- 当前 prompt 目录；
- 人工标注 JSON 或 JSONL；
- 图片根目录；
- VLM API base URL；
- VLM API key 或环境变量；
- VLM model name；
- 解码参数，用于保证可比性；
- 模型输出 JSONL 路径；
- 评估报告 JSON 路径；
- 坏例 JSON 路径；
- 优化规则文件或规则文本；
- optimizer input JSON 路径；
- 对比报告输出路径；
- 停止条件，例如最大迭代轮数、目标 Precision、FP 容忍、FN/Recall 容忍。

如果用户只提供“自动迭代 3 轮”，但没有提供模型、路径、runtime、阈值等信息，agent 需要继续追问缺失项。

### 单轮迭代流程

每一轮包含：

1. 用当前版本运行 VLM 评估。
2. 生成 `model_outputs.jsonl` 和 `eval_report.json`。
3. 生成 `bad_cases.json`，FP 排在 FN 前。
4. 基于 report、bad cases、当前 prompt 和优化规则生成 `optimizer_input.json`。
5. 用 optimizer input 生成下一版完整 prompt。
6. 写入 `prompts/tasks/<task>/<next_version>/`。
7. 用相同数据、模型、解码参数和图片根目录复评下一版。
8. 比较当前版本和下一版。
9. 根据用户确认的验收规则接受、拒绝或停止。

### 指标优先级

默认关注顺序是：

1. Precision；
2. FP；
3. Recall；
4. FN；
5. F1。

FP 是高风险错误，因为它表示人工标注为失败的样本被模型放行。除非用户另有说明，优化应优先减少 FP，而不是单纯追求 Accuracy。

### 修改 prompt 的边界

下一版 prompt 应只针对可见、重复、可泛化的 FP/FN 模式做小幅修改。

尽量不要做：

- 为单个 case 加长 checklist；
- 复制人工原因原文；
- 引入无法从图像中判断的主观标准；
- 对不可见、被裁切、遮挡、模糊、太小或歧义区域变得更严格；
- 覆盖旧版本；
- 在没有明确授权时修改维度结构。

## MVP Orchestrator 使用方法

本仓库提供一个 MVP 自动调优入口：

```text
scripts/run_prompt_orchestrator.py
```

它适合“我已经有 v0，并且想让系统自动迭代 N 轮”的场景。

### 复制配置模板

复制：

```text
configs/prompt_orchestrator.example.json
```

填写后作为自己的运行配置，例如：

```text
configs/prompt_orchestrator.local.json
```

不要把真实 API key 写进仓库。推荐使用环境变量：

```json
{
  "vlm": {
    "api_key_env": "VLM_API_KEY"
  },
  "optimizer": {
    "api_key_env": "OPTIMIZER_API_KEY"
  }
}
```

### 配置字段说明

`python`：用户确认的 Python 可执行文件或运行命令。

`task`：任务名，必须对应 `configs/task_adapter_config.json` 中的 task。

`start_version`：起始 prompt 版本，例如 `v0`。

`max_iterations`：最大自动迭代轮数。

`human_json`：用户提供的人工标注 JSON 或 JSONL 文件。

`image_root`：图片根目录。标注中的图片路径会相对这个目录解析。

`rules`：优化规则文件。

`artifact_root`：每轮评估产物输出目录。

`vlm`：用于真实质检评估的 VLM 配置。

`optimizer`：用于生成下一版 prompt 的 LLM 配置。

`acceptance`：自动接受或停止的策略。

### 运行命令

示例：

```powershell
& '<python_executable>' `
  scripts\run_prompt_orchestrator.py `
  --config configs\prompt_orchestrator.local.json
```

请把 `<python_executable>` 换成用户确认的 Python 路径。

### 输出产物

假设 `artifact_root` 是：

```text
runs/prompt_orchestrator/<task>
```

则每轮会产生：

```text
runs/prompt_orchestrator/<task>/<version>/model_outputs.jsonl
runs/prompt_orchestrator/<task>/<version>/eval_report.json
runs/prompt_orchestrator/<task>/<version>/bad_cases.json
runs/prompt_orchestrator/<task>/<version>/optimizer_input.json
runs/prompt_orchestrator/<task>/<version>/optimizer_response.txt
runs/prompt_orchestrator/<task>/compare_<current>_<next>.md
runs/prompt_orchestrator/<task>/iteration_log.json
```

候选 prompt 会写到：

```text
prompts/tasks/<task>/<next_version>/system_prompt.txt
prompts/tasks/<task>/<next_version>/user_prompt.txt
```

被拒绝的候选版本不会被删除，会留在仓库中供复盘，接受状态记录在 `iteration_log.json`。

## 维度和 task_adapter_config.json

`configs/task_adapter_config.json` 控制下游 schema 和评估维度。

特别是：

```json
"task_prompt_dimensions": [
  "instruction_following",
  "texture_consistency",
  "clothes_consistency"
]
```

这组字段会被用于：

- `run_vlm_eval.py` 构造 `response_format`；
- `evaluate_prompt_suite.py` 计算维度级指标；
- schema 校验和模型输出归一化。

因此，prompt 输出 JSON 字段和 `task_prompt_dimensions` 必须一致。

MVP orchestrator 会在评估前自动同步：

- 启用 `task_prompt` mode；
- 追加 `task_prompt_versions`；
- 如果 prompt 输出 JSON 字段变化，更新 `task_prompt_dimensions`；
- 如果缺少 `default_task_prompt_version`，自动设置。

维度提取是保守规则：只从 prompt 中看起来像输出 JSON 的字段提取维度，并排除 `is_passed`、`passed`、`reason`、`error_types` 等结构字段。如果 prompt 没有清晰写出 JSON 输出格式，orchestrator 不会猜维度。

## 可以直接复制给 agent 的说法

### 初始化 v0

如果你想先走人工确认，可以这样说：

```text
帮我用 vlm-qc-prompt-initialization 给 <task> 这个任务生成 v0。
人工标注文件在 <human_label_json_or_jsonl>。
system prompt 的来源是 <source_system_prompt>。
user prompt 的来源是 <source_user_prompt>，里面有 {PROMPT}。
prompt 设计规则在 <rules_path>。
输出目录用 prompts/tasks/<task>/v0/。
先不要直接写最终 prompt，先把你理解的任务定义、图片含义、维度方案和主要红线整理给我确认。
```

如果任务定义和维度已经确认过，可以这样说：

```text
帮我用 vlm-qc-prompt-initialization 以 batch 模式生成 v0。
这次不用再停下来确认，下面这份任务定义、维度方案和输出目录我已经确认过：...
```

### 自动迭代 N 轮

如果想让 agent 按 skill 流程代跑几轮，可以这样说：

```text
帮我用 vlm-qc-auto-tuning 从 <task> 的 <current_version> 开始自动迭代 3 轮。
Python 用 <python_executable>。
人工标注文件在 <human_label_json_or_jsonl>，图片根目录是 <image_root>。
VLM 的 base URL 是 <base_url>，API key 从环境变量 <env_name> 读，模型用 <model_name>。
optimizer 的 base URL 是 <optimizer_base_url>，API key 从 <optimizer_env_name> 读，模型用 <optimizer_model>。
这次评估的解码参数是 ...
验收规则先按这个来：FP 要下降，FN 不能增加，Precision 不能下降。
```

### 使用 orchestrator

如果要用 MVP orchestrator，可以这样说：

```text
帮我根据 configs/prompt_orchestrator.example.json 配一份本地运行配置。
我来提供 human_json、image_root、VLM endpoint、optimizer endpoint、模型名和环境变量名。
配好以后，用 run_prompt_orchestrator.py 从 v0 开始自动跑 2 轮。
```

## 常见问题

### 为什么不能直接用仓库里的样例数据？

因为样例数据只是开发测试时的截取数据，不代表真实任务输入。skills 的要求是用户必须显式提供真实数据路径。现在分支中也已经删除了 `code/` 和 `data/` 样例资产。

### 如果用户只说“自动迭代 3 轮”够不够？

不够。最大迭代轮数只是停止条件之一。agent 还需要 runtime、任务、版本、标注、图片、模型、API、输出路径、规则和验收阈值等信息。

### 如果 prompt 改了维度，需要手动改 config 吗？

使用 orchestrator 时通常不需要，它会在评估前同步 `task_adapter_config.json`。但 prompt 中必须清晰写出输出 JSON 字段。人工手动跑脚本时，需要自行确保 config 和 prompt 一致。

### 是否建议每轮都改维度？

不建议。自动调优阶段最好保持维度稳定，只调整维度内部规则和红线。维度新增、删除、重命名会改变评估语义，通常应该回到初始化或人工确认环节。

### 为什么 FP 比 FN 更优先？

在训练数据过滤场景里，FP 表示坏样本被放行，风险通常高于好样本被误杀。因此 auto-tuning 默认优先减少 FP 和提高 Precision。

## 交付前检查清单

初始化 prompt 前检查：

- 用户已提供 task；
- 用户已提供人工标注；
- 用户已提供 source prompts 或模板；
- 用户已提供 prompt 设计规则；
- 用户已提供目标版本和输出目录；
- 交互模式下已获得任务定义和维度方案确认。

自动调优前检查：

- 当前 prompt 版本存在；
- `system_prompt.txt` 和 `user_prompt.txt` 存在；
- `user_prompt.txt` 包含 `{PROMPT}`；
- `task_adapter_config.json` 中 task 已存在；
- 用户提供了 Python runtime；
- 用户提供了 human label 和 image root；
- 用户提供了 VLM 和 optimizer 的 endpoint、key source、model；
- 用户提供了解码参数或确认使用配置中的参数；
- 用户提供了最大轮数或其它停止条件；
- 用户提供了 FP/FN/Precision/Recall 验收规则。

推送或交付前检查：

- `python -m pytest` 通过；
- `python scripts/validate_prompt_assets.py` 通过；
- `git ls-files code data` 为空；
- 示例配置没有真实 API key；
- 示例配置没有引用 `code/` 或 `data/`；
- 文档没有把示例路径描述成默认值。
