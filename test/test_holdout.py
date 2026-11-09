import json
from pathlib import Path

from evaluation.holdout import choose_public_holdout


def test_holdout_is_deterministic(tmp_path: Path):
    tasks = [
        {
            "repo": f"repo_{i % 3}",
            "base_commit": f"commit_{i}",
            "instance_id": f"task_{i}"
        }
        for i in range(15)
    ]

    tasks_file = tmp_path / "tasks.jsonl"

    with tasks_file.open("w", encoding="utf-8") as file:
        for task in tasks:
            file.write(json.dumps(task) + "\n")

    first = choose_public_holdout(tasks_file, limit=6)
    second = choose_public_holdout(tasks_file, limit=6)

    assert first == second
    assert len(first) == 6
    assert len(set(first)) == 6


def test_holdout_respects_limit(tmp_path: Path):
    tasks_file = tmp_path / "tasks.jsonl"

    tasks = [
        {
            "repo": "test/repo",
            "base_commit": f"commit_{i}",
            "instance_id": f"task_{i}"
        }
        for i in range(20)
    ]

    tasks_file.write_text(
        "".join(json.dumps(task) + "\n" for task in tasks),
        encoding="utf-8"
    )

    result = choose_public_holdout(tasks_file, limit=5)

    assert len(result) == 5