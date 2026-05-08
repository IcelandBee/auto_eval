# 多任务图像编辑质检 Prompt 通用化设计

## 背景

本项目使用 VLM as a Judge 对图像编辑结果进行自动质检，目标是筛选可作为训练数据的高质量样本。每条样本包含源图 Image A、参考图 Image B、编辑结果 Image C 和编辑指令 P。当前已有 `human_item` 和 `texture_person` 两个任务，后续可能扩展到虚拟试衣、发型迁移、表情迁移、妆容迁移等任务。

当前阶段不追求一次性完成完整自动化系统，而是先验证“Universal Prompt + Task Adapter + 误判驱动优化”的方案是否成立。

## 目标

本轮开发分两步完成一个最小闭环。

第一步固化 Prompt 资产骨架，产出可直接审阅和拼接的 Universal Prompt、任务 Adapter、输出 schema、错误类型库和 Prompt Optimizer 规范。

第二步通用化现有评估脚本，让实验可以通过配置运行三类 Prompt 模式：

- 原始任务 Prompt
- Universal Only
- Universal + Adapter

脚本通用化不要求本地立即跑通远程 VLM API，但必须支持配置校验、prompt 拼接预览、输出 schema 校验、已有模型输出的离线指标计算，为另一台机器上的真实实验提供稳定接口。

## 非目标

本轮不实现完整 Prompt 自动优化闭环，不自动重写 Prompt，不接入新的图像数据下载流程，也不解决另一台机器上的绝对路径和 API 服务可用性问题。

本轮不把 `human_item` 和 `texture_transfer` 的任务细节写入 Universal Prompt。单任务规则必须进入对应 Adapter。

## 资产结构

新增资产目录如下：

```text
prompts/
  universal/
    universal_qc_prompt_v0.txt
    universal_redlines_v0.txt
  adapters/
    human_item_adapter_v0.txt
    texture_transfer_adapter_v0.txt
  user/
    universal_user_prompt_v0.txt

configs/
  output_schema.json
  error_taxonomy.json
  task_adapter_config.json

optimizer/
  prompt_optimizer_skill.md
  prompt_patch_schema.json
```

这些文件形成后续脚本和人工迭代共同依赖的稳定接口。

## Universal Prompt 设计

Universal Prompt 只负责跨任务通用质检流程，不包含袖口、手指握持、发际线、妆容位置等任务特异细节。

Universal Prompt 固定以下输入定义：

- Image A: source image, 原始源图
- Image B: reference image, 参考图
- Image C: edited image, 编辑结果图
- P: edit instruction, 编辑指令

Universal Prompt 使用 6 个通用维度：

- `instruction_following`
- `reference_fidelity`
- `source_preservation`
- `edit_localization`
- `physical_and_structural_realism`
- `image_quality_and_artifacts`

最终 `is_passed` 必须等于所有维度 `passed` 的逻辑与。任何维度失败，整体失败。

Universal Prompt 的判断必须遵循可见证据原则：只根据 Image A、Image B、Image C 和 P 中可见或明确给出的信息判断，不把遮挡、裁切、模糊区域推断成确定错误。

## Redlines 设计

`universal_redlines_v0.txt` 保存跨任务红线，便于单独审阅和后续压缩。红线包括：

- 核心编辑目标缺失
- 编辑目标或区域错误
- 参考内容明显不一致
- 源图中非目标人物、身份、姿态、背景或场景被明显改变
- 编辑越界影响非目标区域
- 明显物理结构错误
- Image B 的背景、人物、环境或无关元素泄露到 Image C
- 明显伪影、破损、模糊、畸形或生成崩坏

红线内容可以被 Universal Prompt 引用或合并，但不得变成某个任务的细节清单。

## Adapter 设计

Adapter 是拼接在 Universal Prompt 后面的轻量任务规则。Adapter 只能补充任务特异标准，不重复 Universal Prompt 的完整通用流程。

`human_item_adapter_v0.txt` 覆盖：

- Image C 中人物应真实持有或携带 Image B 的目标物体
- 目标物类别、数量、主形状、颜色和可见关键特征应与 Image B 一致
- 目标物与手部、手臂、身体的接触、遮挡、支撑关系应物理合理
- 不得出现悬浮、穿模、错位、无支撑或严重比例异常
- 允许为了真实持物对手部和手臂做最小必要修改
- 不得引入严重手部、手指、手臂或肢体结构错误

`texture_transfer_adapter_v0.txt` 覆盖：

- Image C 应将 Image B 纹理迁移到 P 指定的 Image A 衣物区域
- 纹理颜色、图案、密度、尺度和视觉风格应基本一致
- 编辑应仅改变指定目标衣物的表面纹理
- 不得改变衣物结构、版型、长度、边缘、袖口、领口、拉链、纽扣、口袋、裤长或衣摆
- 非目标衣物、人物身份、姿态、背景和其他区域应保持不变
- 不得泄露 Image B 的背景、人物、商品展示环境或无关元素
- 纹理正确但衣物结构明显变化时仍应失败

## 输出 Schema

`configs/output_schema.json` 保存通用输出 schema。顶层字段为：

- `is_passed`
- 6 个通用维度对象

每个维度对象包含：

- `passed`: boolean
- `reason`: string, 中文一句话
- `error_types`: string array, 可以为空

`error_types` 只允许引用 `configs/error_taxonomy.json` 中定义的错误类型。这样后续可以统计 FP/FN 错误分布，而不需要从自然语言原因中硬解析。

## 错误类型库

`configs/error_taxonomy.json` 分为通用错误类型和任务错误类型。

通用错误类型包括：

- `wrong_target`
- `missing_core_edit`
- `reference_mismatch`
- `source_preservation_failure`
- `edit_overreach`
- `physical_implausibility`
- `reference_leakage`
- `artifact_or_low_quality`

`human_item` 任务错误类型包括：

- `object_count_mismatch`
- `object_identity_mismatch`
- `invalid_hand_object_interaction`
- `severe_hand_or_limb_artifact`

`texture_transfer` 任务错误类型包括：

- `texture_not_transferred`
- `texture_mismatch`
- `garment_structure_changed`
- `non_target_garment_changed`

任务错误类型只在对应任务 Adapter 或后处理统计中使用。

## 配置设计

`configs/task_adapter_config.json` 定义任务、Prompt 模式、维度、schema 和文件路径之间的关系。

建议结构：

```json
{
  "tasks": {
    "human_item": {
      "adapter": "prompts/adapters/human_item_adapter_v0.txt",
      "original_prompt_dir": "code/human_item/prompts",
      "prompt_modes": ["original_task_prompt", "universal_only", "universal_adapter"]
    },
    "texture_transfer": {
      "adapter": "prompts/adapters/texture_transfer_adapter_v0.txt",
      "original_prompt_dir": "code/texture_person/prompts",
      "prompt_modes": ["original_task_prompt", "universal_only", "universal_adapter"]
    }
  },
  "universal_prompt": "prompts/universal/universal_qc_prompt_v0.txt",
  "universal_user_prompt": "prompts/user/universal_user_prompt_v0.txt",
  "output_schema": "configs/output_schema.json",
  "error_taxonomy": "configs/error_taxonomy.json"
}
```

配置中的路径相对于项目根目录解析。

## Prompt Optimizer 规范

`optimizer/prompt_optimizer_skill.md` 描述一个受约束的 Prompt 修改助手。它不直接重写完整 Prompt，只根据误判样本输出结构化局部修改建议。

输入包括：

- 任务类型
- 当前 Prompt
- 模型预测结果
- 人工标注结果
- FP/FN 样本
- 模型推理原因
- 人工标注原因
- 当前指标结果
- 历史 Prompt 修改规范

输出包括：

- 问题类型
- 当前 Prompt 问题
- 修改决策
- 防膨胀处理
- 修改后的 Prompt 片段
- 预期影响

允许的修改决策只有：

- 改写已有规则
- 合并已有规则
- 新增通用规则
- 删除低价值规则
- 不修改 Prompt，仅记录案例

新增规则必须说明为什么不是单个 case 过拟合，并同步给出压缩或合并策略。

## 脚本通用化设计

第二步新增或改造脚本时，优先避免直接破坏现有 `code/texture_person/check_and_eval.py`。建议新增 `scripts/` 层作为通用入口，逐步复用现有代码中的稳定函数。

建议新增：

```text
scripts/
  prompt_assets.py
  evaluate_prompt_suite.py
  compare_prompt_reports.py
```

`prompt_assets.py` 负责：

- 读取 `task_adapter_config.json`
- 拼接 Universal + Adapter
- 校验 prompt 文件存在
- 校验 schema 和 error taxonomy
- 输出 prompt 预览

`evaluate_prompt_suite.py` 负责：

- 根据任务和 prompt mode 选择 prompt
- 运行或跳过 VLM 推理
- 支持已有 json/jsonl 输出的离线指标计算
- 输出 report json 和 error cases json

`compare_prompt_reports.py` 负责：

- 汇总 original、universal only、universal + adapter 三组结果
- 输出 Accuracy、Precision、Recall、F1、TP、TN、FP、FN 对比
- 汇总 FP/FN 错误类型变化

现有 `check_and_eval.py` 中的数据加载、JSON 解析、输出校验、指标计算函数可以逐步抽出复用。第一版脚本只需要支持 `human_item` 和 `texture_transfer` 两个任务。

## 数据流

第一阶段数据流：

```text
Universal Prompt
  + optional Task Adapter
  + Universal User Prompt
  + A/B/C/P
  -> VLM JSON
  -> schema validation
  -> metrics and FP/FN analysis
```

第二阶段实验流：

```text
task_adapter_config.json
  -> prompt mode selection
  -> prompt composition
  -> inference or existing output loading
  -> output schema validation
  -> metric report
  -> comparison report
```

## 错误处理

配置错误应在运行前失败，包括缺少文件、未知任务、未知 prompt mode、schema 中维度与 prompt 维度不一致、错误类型不在 taxonomy 中。

模型输出错误应记录为失败样本，并保留原始响应、解析错误和样本 index，不能静默吞掉。

如果本地缺少图片路径或远程 API 不可用，脚本应允许只执行 prompt/config 校验和已有输出离线评估。

## 测试与验证

第一阶段验证：

- 所有新增 JSON 文件可解析
- `task_adapter_config.json` 中引用的文件全部存在
- Universal Prompt 不包含明显任务污染规则
- Adapter 可单独拼接到 Universal Prompt 后使用
- 输出 schema 与 Universal Prompt 的维度一致

第二阶段验证：

- prompt 拼接预览可运行
- 已有输出 JSON/JSONL 可离线计算 overall 和维度指标
- FP/FN 错误 case 可导出
- 三种 Prompt 模式的报告可以被 comparison 脚本汇总

## 验收标准

第一阶段完成时，项目中存在可审阅的 Universal Prompt v0、两个 Adapter v0、schema、error taxonomy、optimizer skill 规范和本设计文档。

第二阶段完成时，脚本可以通过配置识别 `human_item` 和 `texture_transfer`，并支持三种 Prompt 模式的 prompt 选择、拼接预览、schema 校验和离线指标计算。

完整实验是否能连接远程 VLM API 跑通，取决于另一台机器的路径、模型服务和密钥配置，不作为本地第一轮验收条件。
