from evaluation.failure_analysis import analyze_failures


def test_failure_analysis():
    tasks = [
        {"resolved": True},
        {"resolved": True},
        {"resolved": False, "failure_stage": "editing"},
        {"resolved": False, "failure_stage": "testing"},
        {"resolved": False, "failure_stage": "editing"},
    ]

    result = analyze_failures(tasks)

    assert result["total_tasks"] == 5
    assert result["resolved_tasks"] == 2
    assert result["failed_tasks"] == 3
    assert result["resolution_rate"] == 0.4
    assert result["failure_stages"]["editing"] == 2
    assert result["failure_stages"]["testing"] == 1


def test_empty_task_list():
    result = analyze_failures([])

    assert result["total_tasks"] == 0
    assert result["resolution_rate"] is None