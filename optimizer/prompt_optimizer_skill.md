# Prompt Optimizer Skill v0

## Purpose

This skill helps improve image-editing QC prompts from model misjudgment cases. It is a constrained prompt patch assistant, not a free-form prompt rewriter.

## Inputs

- `task_type`: task name, such as `human_item` or `texture_transfer`
- `current_prompt`: current Universal Prompt, Adapter, or final task prompt
- `prompt_layer`: one of `universal`, `adapter`, or `final_task_prompt`
- `model_predictions`: model outputs with pass/fail, dimension results, reasons, and error_types when available
- `human_labels`: human pass/fail labels and dimension labels
- `fp_cases`: human fail but model pass cases
- `fn_cases`: human pass but model fail cases
- `model_reasons`: model reasoning text
- `human_reasons`: human annotation reasons
- `metrics`: Accuracy, Precision, Recall, F1, TP, TN, FP, FN, and dimension metrics
- `change_history`: previous prompt changes and rollback records

## Output

Return only a JSON object matching `optimizer/prompt_patch_schema.json`.

## Allowed Decisions

Choose exactly one:

- `rewrite_existing_rule`
- `merge_existing_rules`
- `add_general_rule`
- `delete_low_value_rule`
- `no_prompt_change_record_case`

## Modification Principles

1. Make the smallest useful change.
2. Do not append rules by default.
3. Do not overfit a single case.
4. Prefer rewriting or merging existing rules over adding new rules.
5. Only modify the prompt for frequent, severe, and generalizable errors.
6. If adding a rule, also compress or remove lower-value wording.
7. Low-frequency special cases should go to the error case library, not the main prompt.
8. Cross-task issues modify the Universal Prompt.
9. Task-specific issues modify the Task Adapter.
10. Every accepted change must be verified with before/after regression metrics.

## FP/FN Priority

For training-data filtering, FP is usually more dangerous than FN because bad data enters the training set. Prefer reducing FP and improving Precision, but reject changes that create a large FN increase without a clear reason.

## Required Reasoning

The optimizer must explain:

- why the problem is generalizable
- why the selected prompt layer is correct
- why the decision is smaller than a full rewrite
- what old wording is compressed or replaced
- expected impact on Precision, Recall, FP, and FN

## Forbidden Behavior

- Do not rewrite the whole prompt.
- Do not add a long case-specific checklist for one sample.
- Do not introduce task details into Universal Prompt.
- Do not delete strict redlines only to improve Recall.
- Do not output natural-language suggestions without a structured patch.
