from scripts.evaluate_prompt_suite import (
    build_dimension_metrics,
    calculate_metrics,
    get_human_dimension,
    normalize_dimension_result,
    parse_label,
)


def test_parse_label_accepts_pass_fail_strings():
    assert parse_label("pass") is True
    assert parse_label("fail") is False
    assert parse_label(True) is True
    assert parse_label(False) is False


def test_calculate_metrics_counts_fp_fn():
    y_true = [True, False, True, False]
    y_pred = [True, True, False, False]

    metrics = calculate_metrics(y_true, y_pred)

    assert metrics["TP"] == 1
    assert metrics["FP"] == 1
    assert metrics["FN"] == 1
    assert metrics["TN"] == 1
    assert metrics["Accuracy"] == 0.5
    assert metrics["Precision"] == 0.5
    assert metrics["Recall"] == 0.5
    assert metrics["F1"] == 0.5


def test_normalize_dimension_result_accepts_universal_shape():
    value = {"passed": True, "reason": "ok", "error_types": []}

    result = normalize_dimension_result(value)

    assert result["passed"] is True
    assert result["reason"] == "ok"
    assert result["error_types"] == []


def test_normalize_dimension_result_accepts_legacy_label():
    result = normalize_dimension_result("fail")

    assert result["passed"] is False
    assert result["reason"] == ""
    assert result["error_types"] == []


def test_normalize_dimension_result_converts_single_error_type_string():
    value = {"passed": False, "reason": "bad", "error_types": "wrong_target"}

    result = normalize_dimension_result(value)

    assert result["error_types"] == ["wrong_target"]


def test_empty_dimension_label_is_treated_as_missing():
    record = {
        "file_name": "sample.jpg",
        "instruction_following": "",
        "instruction_following_reasoning": "",
    }

    result = get_human_dimension(record, "instruction_following")

    assert result is None


def test_dimension_metrics_skip_empty_human_labels():
    human_records = [
        {
            "file_name": "a.jpg",
            "groundtruth": "pass",
            "instruction_following": "",
        },
        {
            "file_name": "b.jpg",
            "groundtruth": "fail",
            "instruction_following": "fail",
        },
    ]
    model_records = [
        {
            "file_name": "a.jpg",
            "is_passed": True,
            "instruction_following": {"passed": True, "reason": "ok", "error_types": []},
        },
        {
            "file_name": "b.jpg",
            "is_passed": False,
            "instruction_following": {"passed": False, "reason": "bad", "error_types": []},
        },
    ]

    metrics = build_dimension_metrics(human_records, model_records, ["instruction_following"])

    assert metrics["instruction_following"]["Total"] == 1
    assert metrics["instruction_following"]["TN"] == 1
