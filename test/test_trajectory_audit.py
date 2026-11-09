import json

from evaluation.trajectory_audit import audit_trajectory_jsonl


def test_valid_trajectory(tmp_path):
    sample = {
        "source_repo": "example/repo",
        "issue": "Fix incorrect calculation",
        "resolved": True,
        "patch": "diff --git a/main.py b/main.py\n",
        "tool_steps": [
            {
                "tool": "read_file",
                "request": {"path": "main.py"},
                "result": "File contents"
            }
        ]
    }

    path = tmp_path / "trajectories.jsonl"
    path.write_text(json.dumps(sample) + "\n", encoding="utf-8")

    result = audit_trajectory_jsonl(path)

    assert result["accepted"] == 1
    assert result["rejected"] == {}
    assert result["repositories"]["example/repo"] == 1


def test_rejects_unsuccessful_trajectory(tmp_path):
    sample = {
        "source_repo": "example/repo",
        "issue": "Fix bug",
        "resolved": False,
        "patch": "diff --git a/main.py b/main.py\n",
        "tool_steps": [
            {
                "tool": "read_file",
                "request": {},
                "result": "content"
            }
        ]
    }

    path = tmp_path / "trajectories.jsonl"
    path.write_text(json.dumps(sample) + "\n", encoding="utf-8")

    result = audit_trajectory_jsonl(path)

    assert result["accepted"] == 0
    assert result["rejected"]["unsuccessful trajectory"] == 1