import json

import pytest

from evaluation.experiment_tracker import update_experiment


def test_updates_experiment_card(tmp_path):
    card = {
        "experiment_id": "test-v1",
        "status": "not_evaluated",
        "evaluation": {
            "total_tasks": 0,
            "resolved_tasks": 0,
            "resolution_rate": None,
            "elapsed_seconds": None
        }
    }

    path = tmp_path / "experiment_card.json"
    path.write_text(json.dumps(card), encoding="utf-8")

    result = update_experiment(
        path,
        total_tasks=12,
        resolved_tasks=8,
        elapsed_seconds=120.5
    )

    assert result["status"] == "evaluated"
    assert result["evaluation"]["resolution_rate"] == 0.6667
    assert result["evaluation"]["elapsed_seconds"] == 120.5


def test_rejects_invalid_task_count(tmp_path):
    path = tmp_path / "experiment_card.json"
    path.write_text(
        json.dumps({"evaluation": {}}),
        encoding="utf-8"
    )

    with pytest.raises(ValueError):
        update_experiment(path, 0, 0, 10)