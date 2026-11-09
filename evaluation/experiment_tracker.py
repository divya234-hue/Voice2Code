import json
from pathlib import Path


def update_experiment(
    card_path: Path,
    total_tasks: int,
    resolved_tasks: int,
    elapsed_seconds: float,
):
    card_path = Path(card_path)

    if total_tasks <= 0:
        raise ValueError("total_tasks must be positive")

    if not 0 <= resolved_tasks <= total_tasks:
        raise ValueError("Invalid resolved_tasks count")

    if elapsed_seconds < 0:
        raise ValueError("elapsed_seconds cannot be negative")

    card = json.loads(card_path.read_text(encoding="utf-8"))

    card["evaluation"].update({
        "total_tasks": total_tasks,
        "resolved_tasks": resolved_tasks,
        "resolution_rate": round(resolved_tasks / total_tasks, 4),
        "elapsed_seconds": round(elapsed_seconds, 2),
    })

    card["status"] = "evaluated"

    card_path.write_text(
        json.dumps(card, indent=2),
        encoding="utf-8"
    )

    return card