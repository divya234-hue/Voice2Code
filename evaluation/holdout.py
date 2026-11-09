import hashlib
import json
from pathlib import Path


def choose_public_holdout(
    tasks_path: Path,
    limit: int = 12
) -> list[str]:

    groups = {}

    with Path(tasks_path).open(encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue

            row = json.loads(line)

            repo = row["repo"]
            commit = row["base_commit"]
            instance_id = row["instance_id"]

            groups.setdefault((repo, commit), []).append(instance_id)

    by_repo = {}

    for (repo, commit), ids in groups.items():
        priority = hashlib.sha256(
            f"{repo}:{commit}".encode()
        ).hexdigest()

        by_repo.setdefault(repo, []).append(
            (priority, sorted(ids)[0])
        )

    for entries in by_repo.values():
        entries.sort()

    selected = []

    while len(selected) < limit and any(by_repo.values()):
        for repo in sorted(by_repo):
            if by_repo[repo] and len(selected) < limit:
                selected.append(by_repo[repo].pop(0)[1])

    return selected