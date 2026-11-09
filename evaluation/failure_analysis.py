from collections import Counter


STAGES = [
    "localization",
    "diagnosis",
    "editing",
    "testing",
    "submission",
]


def analyze_failures(task_results: list[dict]) -> dict:
    report = Counter()
    total = len(task_results)
    resolved = 0

    for task in task_results:
        if task.get("resolved") is True:
            resolved += 1
            continue

        stage = task.get("failure_stage", "unknown")

        if stage not in STAGES:
            stage = "unknown"

        report[stage] += 1

    return {
        "total_tasks": total,
        "resolved_tasks": resolved,
        "failed_tasks": total - resolved,
        "resolution_rate": (
            round(resolved / total, 4) if total else None
        ),
        "failure_stages": dict(report),
    }